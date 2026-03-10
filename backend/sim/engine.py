"""MARL-powered trajectory engine for pedestrian simulation.

Generates 600 frames (60 s @ 10 Hz) of movement by calling 
the standalone Archion MARL Brain API.
"""

from __future__ import annotations

import json
import math
import random
import threading
import requests
import os
import google.generativeai as genai
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
llm_model = genai.GenerativeModel('gemini-2.5-flash')

SIM_HZ = 10            # steps per second
SIM_DURATION = 60       # seconds
TOTAL_STEPS = 600       # 60s * 10hz

N_STANDARD_MIN, N_STANDARD_MAX = 1, 50
STEP_SIZE = 0.09        # metres per tick (~0.9 m/s at 10 Hz)
TURN_RATE = 0.15        # max radians of heading change per tick
WALL_MARGIN = 0.3       # stay this far from polygon boundary
WALL_THICKNESS = 0.35   # buffer around each wall/furniture segment

# The URL for our new standalone AI Brain
BRAIN_API_URL = "http://127.0.0.1:8001/act_batch"


def _build_polygon(boundaries: list[list[float]]) -> Polygon:
    """Build a Shapely polygon, closing the ring if needed."""
    coords = [tuple(p[:2]) for p in boundaries]
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return Polygon(coords)


def _sample_inside(poly: Polygon, rng: random.Random) -> tuple[float, float]:
    """Rejection-sample a random point inside *poly*."""
    minx, miny, maxx, maxy = poly.bounds
    for _ in range(10_000):
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        if poly.contains(Point(x, y)):
            return x, y
    c = poly.centroid
    return c.x, c.y


@dataclass
class SimulationEngine:
    """Pre-compute trajectory frames using the MARL Brain API."""

    boundaries: list[list[float]]
    obstacles: list[list[float]] = field(default_factory=list)
    exit_pos: list[float] | None = None
    n_standard: int = 30
    n_specialist: int = 3
    seed: int | None = 42

    _trajectories: dict | None = field(default=None, repr=False)

    def run(self) -> dict:
        # --- FORCE OVERRIDE: Ignore frontend and only spawn 2 agents ---
        self.n_standard = 2
        self.n_specialist = 0
        
        n_std = max(N_STANDARD_MIN, min(N_STANDARD_MAX, self.n_standard))
        n_spc = max(0, self.n_specialist)
        n_total = n_std + n_spc
        rng = random.Random(self.seed)
        poly = _build_polygon(self.boundaries)

        if not poly.is_valid or poly.is_empty:
            print("[SimEngine] WARNING: invalid polygon — using bounding box fallback")
            poly = Polygon([(-5, -5), (5, -5), (5, 5), (-5, 5)])

        # Build walkable area: boundary shrunk by margin, minus wall obstacles
        walk_area = poly.buffer(-WALL_MARGIN)
        if walk_area.is_empty or not walk_area.is_valid:
            walk_area = poly

        # Subtract interior walls from walkable area
        if self.obstacles:
            wall_polys = []
            for seg in self.obstacles:
                if len(seg) >= 4:
                    line = LineString([(seg[0], seg[1]), (seg[2], seg[3])])
                    wall_polys.append(line.buffer(WALL_THICKNESS))
            if wall_polys:
                walls_union = unary_union(wall_polys)
                walk_area = walk_area.difference(walls_union)
                if walk_area.is_empty or not walk_area.is_valid:
                    walk_area = poly.buffer(-WALL_MARGIN)
                print(f"[SimEngine] Walkable area after wall subtraction: "
                      f"{walk_area.area:.2f} m² ({len(self.obstacles)} wall segments)")

        # Agent types: first n_std are standard, rest are specialist
        agent_types: list[str] = (["standard"] * n_std) + (["specialist"] * n_spc)

        # Spawn agents inside the walkable area
        positions: list[list[float]] = []
        headings: list[float] = []
        for _ in range(n_total):
            x, y = _sample_inside(walk_area, rng)
            positions.append([x, y])
            headings.append(rng.uniform(0, 2 * math.pi))

        print(f"[SimEngine] Spawned {n_std} standard + {n_spc} specialist agents "
              f"inside polygon (area={poly.area:.2f} m²)")

        trajectories: dict[str, dict[str, dict]] = {}

        # --- THE NEW MARL BRAIN LOOP ---
        agent_goals = {}
        for frame in range(TOTAL_STEPS):
            frame_data: dict[str, dict] = {}
            
            # --- LLM STRATEGIC BRAIN ---
            if frame % 50 == 0:
                prompt = f"We have {n_total} pedestrian agents in a simulation. Present coordinates: {positions}. Generate a strategic 2D waypoint [x, y] for each agent to navigate toward. Return ONLY a pure JSON list of coordinate pairs, e.g. [[1.0, 2.0], [3.0, 4.0]]. Do not include markdown codeblocks or extra text."
                try:
                    response = llm_model.generate_content(prompt)
                    # Strip any potential markdown formatting the LLM might stubbornly include
                    clean_text = response.text.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
                    goals = json.loads(clean_text)
                    for aid in range(min(n_total, len(goals))):
                        agent_goals[aid] = goals[aid]
                        print(f"\033[95m🧠 [GEMINI STRATEGY] Frame {frame}: Agent {aid} assigned waypoint {goals[aid]}\033[0m", flush=True)
                except Exception as e:
                    print(f"\033[91m[SimEngine] Gemini API failed: {e}\033[0m", flush=True)
                    for aid in range(n_total):
                        agent_goals[aid] = self.exit_pos or [0.0, 0.0]
            
            # 1. Gather what all agents "see" (The State)
            batch_states = []
            for aid in range(n_total):
                x, y = positions[aid]
                
                # --- REAL SENSOR DATA (Raycasting) ---
                current_heading = headings[aid]
                agent_pt = Point(x, y)
                
                def shoot_ray(angle, max_dist):
                    # Draw an invisible line from the agent outward
                    end_x = x + math.cos(angle) * max_dist
                    end_y = y + math.sin(angle) * max_dist
                    ray = LineString([(x, y), (end_x, end_y)])
                    
                    # Check where this line hits the walls (walk_area boundary)
                    hit = ray.intersection(walk_area.boundary)
                    if hit.is_empty:
                        return max_dist # Path is completely clear
                    return agent_pt.distance(hit) # Return distance to the wall

                # Shoot 3 lasers: straight ahead, slightly left, and slightly right
                ray_front = shoot_ray(current_heading, 5.0)
                ray_left = shoot_ray(current_heading + 0.5, 5.0)
                ray_right = shoot_ray(current_heading - 0.5, 5.0)
                
                is_facing_door = 0.0 # (We can leave this as 0.0 until you add physical doors later)
                
                angle_to_exit = 0.0 
                if aid in agent_goals:
                    # Use the LLM Strategic Brain's assigned waypoint!
                    ex, ey = agent_goals[aid]
                    angle_to_exit = math.atan2(ey - y, ex - x)
                elif self.exit_pos is not None:
                    ex, ey = self.exit_pos
                    angle_to_exit = math.atan2(ey - y, ex - x)

                batch_states.append([ray_front, ray_left, ray_right, angle_to_exit, is_facing_door])

            # 2. Ask the Brain API what to do!
            try:
                response = requests.post(BRAIN_API_URL, json={"states": batch_states})
                actions = response.json().get("actions", [])
                if frame % 50 == 0:
                    print(f"\033[96m🤖 [MARL MOTOR] Frame {frame}: Executing physical actions -> {actions}\033[0m", flush=True)
            except Exception as e:
                # If API fails (e.g., server not running), default to moving forward (action 0)
                if frame == 0:
                    print(f"[SimEngine] WARNING: Brain API failed or not running ({e}). Falling back to dummy actions.")
                actions = [0] * n_total

            # 3. Apply the AI's actions to move the agents
            for aid, action in enumerate(actions):
                x, y = positions[aid]
                heading = headings[aid]
                
                # The Brain's decisions translated to movement
                if action == 0:   # Move Forward
                    heading += rng.uniform(-0.05, 0.05) 
                    speed = STEP_SIZE
                elif action == 1: # Turn Left
                    heading += TURN_RATE
                    speed = STEP_SIZE * 0.5 
                elif action == 2: # Turn Right
                    heading -= TURN_RATE
                    speed = STEP_SIZE * 0.5
                elif action == 3: # Interact (Open Door)
                    speed = 0.0 # Stop to open the door
                else:
                    speed = STEP_SIZE
                
                dx = math.cos(heading) * speed
                dy = math.sin(heading) * speed
                nx, ny = x + dx, y + dy

                # Check wall collision using your original Shapely logic
                if walk_area.contains(Point(nx, ny)):
                    positions[aid] = [nx, ny]
                    headings[aid] = heading
                else:
                    # BOUNCE FIX: If they hit a wall, spin them around so they don't freeze!
                    headings[aid] = headings[aid] + math.pi + rng.uniform(-0.5, 0.5)

                # 4. Save ONLY positional data for the frontend
                frame_data[str(aid)] = {
                    "pos": [round(positions[aid][0], 4), round(positions[aid][1], 4)],
                    "type": agent_types[aid],
                    "action": action # Send the action ID so React can play the right animation!
                }

            trajectories[str(frame)] = frame_data

        self._trajectories = trajectories
        print(f"[SimEngine] MARL Brain generated {TOTAL_STEPS} frames for {n_total} agents")
        return trajectories

    def save(self, path) -> Path:
        """Write trajectories to a JSON file and return the path."""
        path = Path(path)
        data = self._trajectories if self._trajectories is not None else {}
        path.write_text(json.dumps(data))
        return path

    def _setup_environment(self):
        """Shared setup logic for both run() and stream()."""
        self.n_standard = 2
        self.n_specialist = 0

        n_std = max(N_STANDARD_MIN, min(N_STANDARD_MAX, self.n_standard))
        n_spc = max(0, self.n_specialist)
        n_total = n_std + n_spc
        rng = random.Random(self.seed)
        poly = _build_polygon(self.boundaries)

        if not poly.is_valid or poly.is_empty:
            poly = Polygon([(-5, -5), (5, -5), (5, 5), (-5, 5)])

        walk_area = poly.buffer(-WALL_MARGIN)
        if walk_area.is_empty or not walk_area.is_valid:
            walk_area = poly

        if self.obstacles:
            wall_polys = []
            for seg in self.obstacles:
                if len(seg) >= 4:
                    line = LineString([(seg[0], seg[1]), (seg[2], seg[3])])
                    wall_polys.append(line.buffer(WALL_THICKNESS))
            if wall_polys:
                walls_union = unary_union(wall_polys)
                walk_area = walk_area.difference(walls_union)
                if walk_area.is_empty or not walk_area.is_valid:
                    walk_area = poly.buffer(-WALL_MARGIN)

        agent_types = (["standard"] * n_std) + (["specialist"] * n_spc)
        positions = []
        headings = []
        for _ in range(n_total):
            x, y = _sample_inside(walk_area, rng)
            positions.append([x, y])
            headings.append(rng.uniform(0, 2 * math.pi))

        print(f"[SimEngine:stream] Spawned {n_std} standard + {n_spc} specialist agents "
              f"inside polygon (area={poly.area:.2f} m²)", flush=True)

        return n_total, rng, walk_area, agent_types, positions, headings

    def _ask_gemini_wall_decision(self, aid: int, ray_front: float, ray_left: float, ray_right: float) -> int:
        """Ask Gemini what an agent should do when facing a wall. Returns action int."""
        prompt = (
            f"You are controlling pedestrian Agent {aid} in a building simulation. "
            f"The agent sees a wall {ray_front:.2f}m directly ahead. "
            f"Turning left gives {ray_left:.2f}m of clearance. "
            f"Turning right gives {ray_right:.2f}m of clearance. "
            f"Reply with ONLY one of these exact words: TURN_LEFT, TURN_RIGHT, or MOVE_FORWARD"
        )
        try:
            resp = llm_model.generate_content(prompt)
            decision = resp.text.strip().upper()
            if "LEFT" in decision:
                print(f"\033[91m🆘 [GEMINI WALL] Agent {aid} at wall ({ray_front:.2f}m) → TURN LEFT\033[0m", flush=True)
                return 1
            elif "RIGHT" in decision:
                print(f"\033[91m🆘 [GEMINI WALL] Agent {aid} at wall ({ray_front:.2f}m) → TURN RIGHT\033[0m", flush=True)
                return 2
            else:
                print(f"\033[91m🆘 [GEMINI WALL] Agent {aid} at wall ({ray_front:.2f}m) → MOVE FORWARD\033[0m", flush=True)
                return 0
        except Exception as e:
            print(f"\033[91m[GEMINI WALL] API failed: {e}\033[0m", flush=True)
            # Fallback: turn toward the most open side
            return 1 if ray_left > ray_right else 2

    def stream(self):
        """Generator: yields frames indefinitely in real-time until the client disconnects.

        Gemini is called:
        1. Every 50 frames for strategic waypoints (every 5 seconds).
        2. When an agent hits a wall < 1.0m — but with a 20-frame cooldown per agent,
           so it only asks Gemini ONCE per wall encounter, not every frame.
        """
        n_total, rng, walk_area, agent_types, positions, headings = self._setup_environment()

        agent_goals = {}
        # Cooldown: tracks the last frame when Gemini was asked for each agent's wall decision
        gemini_wall_last_frame: dict[int, int] = {}
        # Stores the last Gemini wall action per agent so it persists across cooldown frames
        gemini_wall_action: dict[int, int] = {}
        # HISTORY: Tracks the last N wall-turns to break loops (e.g. 3 LEFTs in a row)
        agent_wall_history: dict[int, list[int]] = {}

        WALL_TRIGGER_DIST = 1.2   # metres — start asking Gemini when this close to a wall
        WALL_COOLDOWN = 20        # frames — don't ask again for 2 seconds after last answer
        STRATEGY_INTERVAL = 50    # frames — how often Gemini gives new waypoints

        import time
        import traceback
        
        for frame in range(TOTAL_STEPS):
            try:
                frame_data: dict[str, dict] = {}

                # --- LLM STRATEGIC BRAIN (every STRATEGY_INTERVAL frames) ---
                if frame % STRATEGY_INTERVAL == 0:
                    # Get building bounds so Gemini can pick diverse exploration targets
                    minx, miny, maxx, maxy = walk_area.bounds
                    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
                    prompt = (
                        f"You are guiding {n_total} pedestrian agents to EXPLORE an entire building floor plan.\n"
                        f"Building bounds: X=[{minx:.1f}, {maxx:.1f}], Y=[{miny:.1f}, {maxy:.1f}], Center=[{cx:.1f},{cy:.1f}].\n"
                        f"Agent current positions: {[[round(p[0],2), round(p[1],2)] for p in positions]}.\n"
                        f"RULES:\n"
                        f"- Send each agent to a DIFFERENT area (spread them across the building, not close together).\n"
                        f"- The targets must be within the building bounds above.\n"
                        f"- Vary the targets each time — don't send them to the same places repeatedly.\n"
                        f"- Think of the floor as having zones: top-left, top-right, bottom-left, bottom-right, center.\n"
                        f"Return ONLY a JSON list of [x, y] pairs, one per agent. No markdown, no explanation."
                    )
                    
                    # 📡 Ask Gemini async in background so we NEVER block the frame loop
                    def _fetch_strategy(_prompt=prompt, _frame=frame):
                        try:
                            resp = llm_model.generate_content(_prompt)
                            clean = resp.text.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
                            goals = json.loads(clean)
                            for aid in range(min(n_total, len(goals))):
                                agent_goals[aid] = goals[aid]
                                print(f"\033[95m🧠 [GEMINI STRATEGY] Frame {_frame}: Agent {aid} → waypoint {goals[aid]}\033[0m", flush=True)
                        except Exception as e:
                            print(f"\033[91m[SimEngine] Gemini strategy failed: {e}\033[0m", flush=True)
                    
                    threading.Thread(target=_fetch_strategy, daemon=True).start()

                # --- SENSOR + MARL BATCH ---
                batch_states = []
                per_agent_rays = []

                for aid in range(n_total):
                    x, y = positions[aid]
                    heading = headings[aid]
                    agent_pt = Point(x, y)

                    def shoot_ray(angle, max_dist, _x=x, _y=y, _pt=agent_pt):
                        end_x = _x + math.cos(angle) * max_dist
                        end_y = _y + math.sin(angle) * max_dist
                        ray = LineString([(_x, _y), (end_x, end_y)])
                        hit = ray.intersection(walk_area.boundary)
                        if hit.is_empty:
                            return max_dist
                        return _pt.distance(hit)

                    ray_front = shoot_ray(heading, 5.0)
                    ray_left  = shoot_ray(heading + 0.5, 5.0)
                    ray_right = shoot_ray(heading - 0.5, 5.0)
                    per_agent_rays.append((ray_front, ray_left, ray_right))

                    angle_to_exit = 0.0
                    if aid in agent_goals:
                        ex, ey = agent_goals[aid]
                        angle_to_exit = math.atan2(ey - y, ex - x)
                    elif self.exit_pos:
                        ex, ey = self.exit_pos
                        angle_to_exit = math.atan2(ey - y, ex - x)

                    batch_states.append([ray_front, ray_left, ray_right, angle_to_exit, 0.0])
                
                # --- MARL MOTOR BRAIN ---
                try:
                    resp = requests.post(BRAIN_API_URL, json={"states": batch_states}, timeout=2)
                    actions = resp.json().get("actions", [0] * n_total)
                except Exception:
                    actions = [0] * n_total


                # --- APPLY ACTIONS + GEMINI WALL OVERRIDE (with cooldown) ---
                for aid, action in enumerate(actions):
                    x, y = positions[aid]
                    heading = headings[aid]
                    ray_front, ray_left, ray_right = per_agent_rays[aid]

                    # 🧱 WALL DETECTED — ask Gemini in background, use heuristic immediately
                    if ray_front < WALL_TRIGGER_DIST:
                        frames_since_last_call = frame - gemini_wall_last_frame.get(aid, -9999)

                        if frames_since_last_call >= WALL_COOLDOWN:
                            # ⚡ Immediately use a smart heuristic — NEVER block the frame loop
                            immediate_action = 1 if ray_left > ray_right else 2

                            # --- 🔄 CYCLE BREAKER LOGIC ---
                            history = agent_wall_history.get(aid, [])
                            
                            # Filter history to only keep encounters within 3.0 meters
                            valid_history = []
                            for act, hx, hy in history:
                                if math.hypot(hx - x, hy - y) < 3.0:
                                    valid_history.append((act, hx, hy))
                                    
                            valid_history.append((immediate_action, x, y))
                            valid_history = valid_history[-4:] # Keep up to last 4 local encounters
                            agent_wall_history[aid] = valid_history
                            
                            if len(valid_history) >= 4:
                                # Hit wall 4 times in the same small area -> TRAPPED!
                                print(f"\033[93m⚠️ [CYCLE BREAKER] Agent {aid} stuck in local trap. Reassigning waypoint!\033[0m", flush=True)
                                
                                # Assign a completely new random waypoint to pull them out
                                agent_goals[aid] = list(_sample_inside(walk_area, rng))
                                
                                forced_action = 1 if ray_left > ray_right else 2
                                action = forced_action
                                gemini_wall_action[aid] = forced_action
                                gemini_wall_last_frame[aid] = frame
                                agent_wall_history[aid] = [] # Reset history after breaking out
                            else:
                                gemini_wall_action[aid] = immediate_action
                                gemini_wall_last_frame[aid] = frame
                                action = immediate_action

                                # 📡 Ask Gemini async in background — response updates next encounter
                                _rf, _rl, _rr, _aid = ray_front, ray_left, ray_right, aid
                                def _ask_async(_aid=_aid, _rf=_rf, _rl=_rl, _rr=_rr):
                                    print(f"\033[93m📡 [AGENT {_aid}→GEMINI] Wall {_rf:.2f}m ahead | Left={_rl:.2f}m Right={_rr:.2f}m — asking...\033[0m", flush=True)
                                    result = self._ask_gemini_wall_decision(_aid, _rf, _rl, _rr)
                                    gemini_wall_action[_aid] = result  # update for next encounter
                                threading.Thread(target=_ask_async, daemon=True).start()
                            # ------------------------------
                        else:
                            # Still within cooldown — keep executing last known action
                            action = gemini_wall_action.get(aid, action)

                    elif aid in gemini_wall_action and ray_front >= WALL_TRIGGER_DIST + 0.3:
                        # Agent cleared the wall — MARL takes back over
                        del gemini_wall_action[aid]

                    if action == 0:
                        heading += rng.uniform(-0.05, 0.05)
                        speed = STEP_SIZE
                    elif action == 1:
                        heading += TURN_RATE
                        speed = STEP_SIZE * 0.5
                    elif action == 2:
                        heading -= TURN_RATE
                        speed = STEP_SIZE * 0.5
                    else:
                        speed = 0.0

                    nx = x + math.cos(heading) * speed
                    ny = y + math.sin(heading) * speed

                    if walk_area.contains(Point(nx, ny)):
                        positions[aid] = [nx, ny]
                        headings[aid] = heading
                    else:
                        headings[aid] = heading + math.pi + rng.uniform(-0.5, 0.5)

                    frame_data[str(aid)] = {
                        "pos": [round(positions[aid][0], 4), round(positions[aid][1], 4)],
                        "type": agent_types[aid],
                        "action": action,
                        "rays": [round(ray_front, 2), round(ray_left, 2), round(ray_right, 2)],
                    }

                yield frame, frame_data

                # ⚡ THROTTLE: smooth out the stream so frontend React doesn't get 1000 frames/sec
                time.sleep(0.05)
                
            except Exception as e:
                print(f"\033[91m[SimEngine] Loop crashed: {e}\n{traceback.format_exc()}\033[0m", flush=True)
                break