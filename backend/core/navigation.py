"""Grid-based A* navigation graph for pedestrian pathfinding.

Builds a walkable grid from the building boundary polygon, marks obstacle
cells as unwalkable (buffered by agent shoulder width), and provides A*
search to route agents through doors and hallways.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


GRID_RESOLUTION = 0.5   # metres per cell
AGENT_RADIUS = 0.3      # shoulder-width buffer around walls


@dataclass
class NavigationGraph:
    """Grid-based A* navigation over an architectural floor plan.

    Parameters
    ----------
    walkable_polygon : Polygon
        The exterior boundary polygon (already buffered inward by geometry.py).
    obstacle_segments : list[list[float]]
        Wall segments ``[[x1, y1, x2, y2], ...]`` from obstacle extraction.
    resolution : float
        Grid cell size in metres.
    agent_radius : float
        Buffer distance around obstacles to account for agent width.
    """

    walkable_polygon: Polygon
    obstacle_segments: list[list[float]] = field(default_factory=list)
    resolution: float = GRID_RESOLUTION
    agent_radius: float = AGENT_RADIUS

    # Computed grid data
    grid: np.ndarray = field(init=False, repr=False)
    origin_x: float = field(init=False)
    origin_y: float = field(init=False)
    nx: int = field(init=False)
    ny: int = field(init=False)

    def __post_init__(self) -> None:
        self._build_grid()

    # ------------------------------------------------------------------
    # Grid construction
    # ------------------------------------------------------------------

    def _build_grid(self) -> None:
        """Create a boolean walkability grid over the floor plan."""
        bounds = self.walkable_polygon.bounds  # (minx, miny, maxx, maxy)
        self.origin_x = bounds[0]
        self.origin_y = bounds[1]
        self.nx = max(1, int(math.ceil((bounds[2] - bounds[0]) / self.resolution)) + 1)
        self.ny = max(1, int(math.ceil((bounds[3] - bounds[1]) / self.resolution)) + 1)

        # Build a union of buffered obstacle lines (accounts for agent shoulder width)
        obstacle_geom = None
        if self.obstacle_segments:
            buffered = []
            for seg in self.obstacle_segments:
                line = LineString([(seg[0], seg[1]), (seg[2], seg[3])])
                buffered.append(line.buffer(self.agent_radius))
            obstacle_geom = unary_union(buffered)

        # Mark each cell as walkable or not
        self.grid = np.zeros((self.ny, self.nx), dtype=bool)
        for iy in range(self.ny):
            wy = self.origin_y + iy * self.resolution
            for ix in range(self.nx):
                wx = self.origin_x + ix * self.resolution
                pt = Point(wx, wy)
                if not self.walkable_polygon.contains(pt):
                    continue
                if obstacle_geom is not None and obstacle_geom.contains(pt):
                    continue
                self.grid[iy, ix] = True

        n_walkable = int(self.grid.sum())
        print(f"[NAV] Grid {self.nx}x{self.ny} ({self.resolution}m), "
              f"{n_walkable} walkable cells, "
              f"{self.nx * self.ny - n_walkable} blocked")

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def world_to_grid(self, x: float, y: float) -> tuple[int, int]:
        """Convert world coordinates to grid indices (ix, iy)."""
        ix = int(round((x - self.origin_x) / self.resolution))
        iy = int(round((y - self.origin_y) / self.resolution))
        ix = max(0, min(self.nx - 1, ix))
        iy = max(0, min(self.ny - 1, iy))
        return ix, iy

    def grid_to_world(self, ix: int, iy: int) -> tuple[float, float]:
        """Convert grid indices to world coordinates."""
        return (
            self.origin_x + ix * self.resolution,
            self.origin_y + iy * self.resolution,
        )

    def _snap_to_walkable(self, ix: int, iy: int) -> tuple[int, int]:
        """Find the nearest walkable cell to (ix, iy) via BFS."""
        if 0 <= iy < self.ny and 0 <= ix < self.nx and self.grid[iy, ix]:
            return ix, iy

        visited = set()
        queue = [(ix, iy)]
        visited.add((ix, iy))
        while queue:
            cx, cy = queue.pop(0)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx_, ny_ = cx + dx, cy + dy
                if (nx_, ny_) in visited:
                    continue
                visited.add((nx_, ny_))
                if 0 <= ny_ < self.ny and 0 <= nx_ < self.nx:
                    if self.grid[ny_, nx_]:
                        return nx_, ny_
                    queue.append((nx_, ny_))
        # Fallback: return original (will fail gracefully)
        return ix, iy

    # ------------------------------------------------------------------
    # A* pathfinding
    # ------------------------------------------------------------------

    def find_path(
        self,
        start: tuple[float, float],
        goal: tuple[float, float],
    ) -> list[tuple[float, float]]:
        """Find an A* path from *start* to *goal* in world coordinates.

        Returns a list of world-coordinate waypoints. If no path exists,
        returns a direct line ``[start, goal]``.
        """
        six, siy = self._snap_to_walkable(*self.world_to_grid(*start))
        gix, giy = self._snap_to_walkable(*self.world_to_grid(*goal))

        # If start == goal, return immediately
        if (six, siy) == (gix, giy):
            return [start, goal]

        # A* with 8-directional movement
        # Priority queue: (f_score, counter, (ix, iy))
        SQRT2 = math.sqrt(2)
        counter = 0
        open_set: list[tuple[float, int, tuple[int, int]]] = []
        heapq.heappush(open_set, (0.0, counter, (six, siy)))

        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score: dict[tuple[int, int], float] = {(six, siy): 0.0}

        directions = [
            (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
            (-1, -1, SQRT2), (-1, 1, SQRT2), (1, -1, SQRT2), (1, 1, SQRT2),
        ]

        goal_node = (gix, giy)
        found = False

        while open_set:
            _, _, current = heapq.heappop(open_set)
            if current == goal_node:
                found = True
                break

            cx, cy = current
            for ddx, ddy, cost in directions:
                nx_, ny_ = cx + ddx, cy + ddy
                if nx_ < 0 or nx_ >= self.nx or ny_ < 0 or ny_ >= self.ny:
                    continue
                if not self.grid[ny_, nx_]:
                    continue
                # For diagonals, also check that the two cardinal neighbours
                # are walkable (prevent corner-cutting through walls)
                if ddx != 0 and ddy != 0:
                    if not self.grid[cy, cx + ddx] or not self.grid[cy + ddy, cx]:
                        continue

                tentative = g_score[current] + cost
                neighbour = (nx_, ny_)
                if tentative < g_score.get(neighbour, math.inf):
                    came_from[neighbour] = current
                    g_score[neighbour] = tentative
                    h = math.hypot(nx_ - gix, ny_ - giy)
                    counter += 1
                    heapq.heappush(open_set, (tentative + h, counter, neighbour))

        if not found:
            # No path — fall back to direct line
            return [start, goal]

        # Reconstruct path
        path_grid: list[tuple[int, int]] = []
        node = goal_node
        while node in came_from:
            path_grid.append(node)
            node = came_from[node]
        path_grid.append((six, siy))
        path_grid.reverse()

        # Convert to world coordinates and simplify
        path_world = [self.grid_to_world(ix, iy) for ix, iy in path_grid]

        # Simplify: remove intermediate collinear waypoints
        if len(path_world) > 2:
            path_world = self._simplify_path(path_world)

        return path_world

    @staticmethod
    def _simplify_path(path: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Remove collinear intermediate points to reduce waypoint count."""
        if len(path) <= 2:
            return path
        simplified = [path[0]]
        for i in range(1, len(path) - 1):
            px, py = simplified[-1]
            cx, cy = path[i]
            nx, ny = path[i + 1]
            # Cross product to check collinearity
            cross = (cx - px) * (ny - py) - (cy - py) * (nx - px)
            if abs(cross) > 1e-6:
                simplified.append(path[i])
        simplified.append(path[-1])
        return simplified
