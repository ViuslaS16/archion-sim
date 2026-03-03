"""Pre-computed trajectory engine for pedestrian simulation.

Generates 600 frames (60 s @ 10 Hz) of random-walk movement
constrained to the building polygon extracted by the geometry pipeline.
The frontend scrubs through the returned trajectory dict.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

SIM_HZ = 10            # steps per second
SIM_DURATION = 60       # seconds
TOTAL_STEPS = SIM_HZ * SIM_DURATION  # 600

N_STANDARD_MIN, N_STANDARD_MAX = 20, 50
STEP_SIZE = 0.09        # metres per tick (~0.9 m/s at 10 Hz — relaxed indoor walk)
EXIT_BIAS = 0.45        # fraction of step biased toward exit
TURN_RATE = 0.15        # max radians of heading change per tick (smooth turning)
BIG_TURN_CHANCE = 0.02  # 2% chance per tick of picking a new random heading
WALL_MARGIN = 0.3       # stay this far from polygon boundary
WALL_THICKNESS = 0.35   # buffer around each wall/furniture segment


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
    """Pre-compute trajectory frames within building bounds.

    Parameters
    ----------
    boundaries : list[list[float]]
        Exterior wall coords [[x, y], …].
    obstacles : list[list[float]]
        Interior obstacles (reserved for future use).
    n_standard : int
        Number of standard agents.
    n_specialist : int
        Number of specialist agents.
    seed : int | None
        Random seed for reproducibility.
    """

    boundaries: list[list[float]]
    obstacles: list[list[float]] = field(default_factory=list)
    exit_pos: list[float] | None = None
    n_standard: int = 30
    n_specialist: int = 3
    seed: int | None = 42

    _trajectories: dict | None = field(default=None, repr=False)

    def run(self) -> dict:
        """Generate pre-computed trajectories with human-like walking.

        Each agent has a persistent heading that turns smoothly over time,
        creating natural-looking paths instead of jittery random walks.

        Returns
        -------
        dict
            ``{ "frame_id": { "agent_id": { "pos": [x, y], "type": str } } }``
        """
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

        for frame in range(TOTAL_STEPS):
            frame_data: dict[str, dict] = {}
            for aid in range(n_total):
                x, y = positions[aid]
                heading = headings[aid]

                # Occasionally pick a completely new heading (simulates
                # a person deciding to walk somewhere different)
                if rng.random() < BIG_TURN_CHANCE:
                    heading = rng.uniform(0, 2 * math.pi)
                else:
                    # Small smooth turn each tick
                    heading += rng.uniform(-TURN_RATE, TURN_RATE)

                # Steer heading toward exit if one is set
                if self.exit_pos is not None:
                    ex, ey = self.exit_pos
                    to_exit = math.atan2(ey - y, ex - x)
                    # Signed angular difference
                    diff = (to_exit - heading + math.pi) % (2 * math.pi) - math.pi
                    heading += diff * EXIT_BIAS

                # Speed variation: people don't walk at a constant speed
                speed = STEP_SIZE * rng.uniform(0.85, 1.15)

                dx = math.cos(heading) * speed
                dy = math.sin(heading) * speed

                nx, ny = x + dx, y + dy

                # Boundary containment with wall bounce
                if walk_area.contains(Point(nx, ny)):
                    positions[aid] = [nx, ny]
                    headings[aid] = heading
                else:
                    # Hit a wall/obstacle — try several escape angles
                    moved = False
                    for offset in (math.pi, math.pi * 0.5, math.pi * 1.5,
                                   math.pi * 0.75, math.pi * 1.25):
                        new_h = heading + offset + rng.uniform(-0.3, 0.3)
                        nx2 = x + math.cos(new_h) * speed
                        ny2 = y + math.sin(new_h) * speed
                        if walk_area.contains(Point(nx2, ny2)):
                            positions[aid] = [nx2, ny2]
                            headings[aid] = new_h
                            moved = True
                            break
                    if not moved:
                        headings[aid] = rng.uniform(0, 2 * math.pi)
                    # else stay put this tick

                frame_data[str(aid)] = {
                    "pos": [round(positions[aid][0], 4),
                            round(positions[aid][1], 4)],
                    "type": agent_types[aid],
                }

            trajectories[str(frame)] = frame_data

        self._trajectories = trajectories
        print(f"[SimEngine] Generated {TOTAL_STEPS} frames for {n_total} agents")
        return trajectories

    def save(self, path) -> Path:
        """Write trajectories to a JSON file and return the path."""
        path = Path(path)
        data = self._trajectories if self._trajectories is not None else {}
        path.write_text(json.dumps(data))
        return path

