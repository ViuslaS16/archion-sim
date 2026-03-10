"""Gymnasium environment for building navigation.

Uses actual building geometry extracted from the uploaded 3D model.
Designed for future MARL training (Actor-Critic, PPO, MAPPO, etc.).

Install deps:
    pip install gymnasium shapely numpy
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
    _GYM_AVAILABLE = True
except ImportError:
    _GYM_AVAILABLE = False

try:
    from shapely.geometry import LineString, Point, Polygon
    _SHAPELY_AVAILABLE = True
except ImportError:
    _SHAPELY_AVAILABLE = False


def _require_gym():
    if not _GYM_AVAILABLE:
        raise ImportError(
            "gymnasium not installed. Run: pip install gymnasium"
        )


def _require_shapely():
    if not _SHAPELY_AVAILABLE:
        raise ImportError(
            "shapely not installed. Run: pip install shapely"
        )


class BuildingNavEnv:
    """Multi-agent Gymnasium environment for pedestrian navigation inside buildings.

    Observation per agent (float32, shape = [6 + 8 + 2*(num_agents-1)]):
        [x, y, vx, vy, goal_x, goal_y,   # own state
         wall_dist_0..7,                   # 8 raycasts every 45 deg
         other_agent_dx, other_agent_dy,   # relative position of each peer
         ...]

    Action space: Discrete(5)
        0 — move forward
        1 — turn left (~22.5 deg)
        2 — turn right (~22.5 deg)
        3 — accelerate
        4 — decelerate

    Reward shaping:
        +100   goal reached
        -50    wall collision
        -20    agent-agent collision
        +0.5   got closer to goal
        -0.2   moved away from goal
        -0.01  time penalty per step
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        floor_polygon: "Polygon",
        wall_segments: List[List[float]],
        num_agents: int = 2,
        max_steps: int = 500,
    ):
        _require_gym()
        _require_shapely()

        self.floor_polygon = floor_polygon
        self.wall_segments = wall_segments
        self.num_agents = num_agents
        self.max_steps = max_steps

        minx, miny, maxx, maxy = floor_polygon.bounds
        self.bounds = {"min_x": minx, "max_x": maxx, "min_y": miny, "max_y": maxy}

        # Action / observation spaces
        self.action_space = spaces.Discrete(5)

        obs_dim = 6 + 8 + 2 * max(1, num_agents - 1)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(obs_dim,), dtype=np.float32
        )

        # Physics
        self.max_speed = 1.4       # m/s
        self.collision_radius = 0.3  # m
        self.goal_radius = 0.5     # m
        self.dt = 0.1              # 10 Hz

        # Episode state (initialised in reset)
        self.agent_positions: List[np.ndarray] = []
        self.agent_velocities: List[np.ndarray] = []
        self.agent_headings: List[float] = []
        self.goal_positions: List[np.ndarray] = []
        self.step_count: int = 0

        print(
            f"[BuildingNavEnv] created — "
            f"bounds=({minx:.1f},{miny:.1f})→({maxx:.1f},{maxy:.1f}) "
            f"walls={len(wall_segments)} agents={num_agents}"
        )

    # ------------------------------------------------------------------
    # Gym API
    # ------------------------------------------------------------------

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict] = None,
    ) -> Tuple[np.ndarray, Dict]:
        if seed is not None:
            np.random.seed(seed)

        self.agent_positions = []
        self.agent_velocities = []
        self.agent_headings = []
        self.goal_positions = []

        for _ in range(self.num_agents):
            pos = self._sample_valid_position()
            goal = self._sample_valid_position()
            while np.linalg.norm(goal - pos) < 3.0:
                goal = self._sample_valid_position()

            self.agent_positions.append(pos)
            self.goal_positions.append(goal)
            self.agent_velocities.append(np.zeros(2))
            direction = goal - pos
            self.agent_headings.append(float(np.arctan2(direction[1], direction[0])))

        self.step_count = 0
        obs = np.stack([self._observe(i) for i in range(self.num_agents)])
        return obs, {"step": 0}

    def step(
        self, actions: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, bool, bool, Dict]:
        prev_positions = [p.copy() for p in self.agent_positions]
        rewards = np.zeros(self.num_agents, dtype=np.float32)
        terminated = False

        for i, action in enumerate(actions):
            self._apply_action(i, int(action))

        for i in range(self.num_agents):
            if self._wall_collision(i):
                rewards[i] -= 50.0
                terminated = True
            if self._agent_collision(i):
                rewards[i] -= 20.0
            if self._goal_reached(i):
                rewards[i] += 100.0
                terminated = True

            prev_dist = float(np.linalg.norm(prev_positions[i] - self.goal_positions[i]))
            curr_dist = float(np.linalg.norm(self.agent_positions[i] - self.goal_positions[i]))
            rewards[i] += 0.5 if curr_dist < prev_dist else -0.2
            rewards[i] -= 0.01  # time penalty

        self.step_count += 1
        truncated = self.step_count >= self.max_steps
        obs = np.stack([self._observe(i) for i in range(self.num_agents)])
        info = {
            "step": self.step_count,
            "positions": [p.tolist() for p in self.agent_positions],
        }
        return obs, rewards, terminated, truncated, info

    # ------------------------------------------------------------------
    # Internal physics
    # ------------------------------------------------------------------

    def _apply_action(self, idx: int, action: int):
        accel_map = {0: 0.5, 1: 0.3, 2: 0.3, 3: 1.0, 4: -0.5}
        turn_map  = {0: 0.0, 1: np.pi / 8, 2: -np.pi / 8, 3: 0.0, 4: 0.0}

        self.agent_headings[idx] += turn_map.get(action, 0.0)
        heading = self.agent_headings[idx]

        speed = float(np.linalg.norm(self.agent_velocities[idx]))
        speed = float(np.clip(speed + accel_map.get(action, 0.0) * self.dt, 0.0, self.max_speed))

        self.agent_velocities[idx] = np.array([speed * np.cos(heading), speed * np.sin(heading)])
        self.agent_positions[idx] = self.agent_positions[idx] + self.agent_velocities[idx] * self.dt

    def _observe(self, idx: int) -> np.ndarray:
        pos  = self.agent_positions[idx]
        vel  = self.agent_velocities[idx]
        goal = self.goal_positions[idx]

        own_state = np.concatenate([pos, vel, goal])  # 6 values
        wall_dists = self._raycast_all(idx)            # 8 values

        others: List[float] = []
        for j in range(self.num_agents):
            if j != idx:
                others.extend((self.agent_positions[j] - pos).tolist())
        if not others:
            others = [0.0, 0.0]

        return np.concatenate([own_state, wall_dists, others]).astype(np.float32)

    def _raycast_all(self, idx: int) -> np.ndarray:
        pos = self.agent_positions[idx]
        dists = []
        for k in range(8):
            angle = 2 * np.pi * k / 8
            direction = np.array([np.cos(angle), np.sin(angle)])
            dists.append(self._raycast(pos, direction))
        return np.array(dists, dtype=np.float32)

    def _raycast(self, origin: np.ndarray, direction: np.ndarray, max_dist: float = 5.0) -> float:
        min_dist = max_dist
        for wall in self.wall_segments:
            x1, y1, x2, y2 = wall
            wx, wy = x2 - x1, y2 - y1
            denom = direction[0] * wy - direction[1] * wx
            if abs(denom) < 1e-6:
                continue
            diff = np.array([x1, y1]) - origin
            t1 = (diff[0] * wy - diff[1] * wx) / denom
            t2 = (diff[0] * direction[1] - diff[1] * direction[0]) / denom
            if t1 >= 0 and 0.0 <= t2 <= 1.0 and t1 < min_dist:
                min_dist = t1
        return min_dist

    def _wall_collision(self, idx: int) -> bool:
        pt = Point(self.agent_positions[idx])
        return not self.floor_polygon.contains(pt.buffer(self.collision_radius))

    def _agent_collision(self, idx: int) -> bool:
        pos = self.agent_positions[idx]
        for j in range(self.num_agents):
            if j != idx:
                if float(np.linalg.norm(pos - self.agent_positions[j])) < 2 * self.collision_radius:
                    return True
        return False

    def _goal_reached(self, idx: int) -> bool:
        return float(np.linalg.norm(self.agent_positions[idx] - self.goal_positions[idx])) < self.goal_radius

    def _sample_valid_position(self) -> np.ndarray:
        minx, miny, maxx, maxy = self.floor_polygon.bounds
        for _ in range(200):
            x = float(np.random.uniform(minx, maxx))
            y = float(np.random.uniform(miny, maxy))
            if self.floor_polygon.contains(Point(x, y)):
                return np.array([x, y])
        c = self.floor_polygon.centroid
        return np.array([c.x, c.y])


def make_env(
    boundaries: List[List[float]],
    wall_segments: List[List[float]],
    num_agents: int = 2,
    max_steps: int = 500,
) -> "BuildingNavEnv":
    """Convenience factory used by training scripts."""
    _require_shapely()
    from shapely.geometry import Polygon

    coords = [tuple(p[:2]) for p in boundaries]
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    floor_poly = Polygon(coords)

    return BuildingNavEnv(
        floor_polygon=floor_poly,
        wall_segments=wall_segments,
        num_agents=num_agents,
        max_steps=max_steps,
    )
