"""Spatial analysis for the AI recommendation engine.

Analyses wall geometry around each violation point to extract:
- Which walls are responsible for the violation
- Available space for wall relocation
- Structural risk indicators
- Feasibility of different solution approaches

This data grounds Gemini's reasoning in actual measured geometry rather
than generic templates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class NearbyWall:
    """A wall segment near a violation, with spatial metrics."""
    index: int
    x1: float
    y1: float
    x2: float
    y2: float
    length: float
    distance_to_violation: float
    available_space_beyond_m: float   # space the wall could shift outward


@dataclass
class WallRelocationFeasibility:
    """Feasibility of relocating a wall to fix a violation."""
    can_relocate: bool
    required_shift_m: float
    available_space_m: float
    obstruction_present: bool
    preferred_wall_index: int     # index into nearby_walls list
    confidence: float             # 0.0–1.0


@dataclass
class SpatialContext:
    """Full spatial analysis around a violation point."""
    violation_coord: tuple[float, float]
    nearby_walls: list[NearbyWall]
    available_corridor_width_m: float
    required_width_m: float
    gap_to_close_m: float
    gap_pct: float                     # percentage below minimum
    relocation: WallRelocationFeasibility
    structural_risk: str               # "low" | "medium" | "high"
    structural_indicators: list[str]
    adjacent_space_estimate_m2: float


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def find_walls_near_violation(
    wall_segments: list[list[float]],
    coord: tuple[float, float],
    radius: float = 3.0,
) -> list[dict]:
    """Return wall segments within *radius* metres of *coord*, sorted by distance.

    Each entry is a plain dict with keys:
    ``index``, ``x1``, ``y1``, ``x2``, ``y2``, ``length``, ``distance``,
    ``midpoint``.
    """
    cx, cy = coord
    nearby: list[dict] = []

    for i, seg in enumerate(wall_segments):
        if len(seg) < 4:
            continue
        x1, y1, x2, y2 = seg[0], seg[1], seg[2], seg[3]

        line = LineString([(x1, y1), (x2, y2)])
        dist = Point(cx, cy).distance(line)

        if dist <= radius:
            length = math.hypot(x2 - x1, y2 - y1)
            nearby.append({
                "index": i,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "length": round(length, 3),
                "distance": round(dist, 3),
                "midpoint": (
                    round((x1 + x2) / 2, 3),
                    round((y1 + y2) / 2, 3),
                ),
            })

    return sorted(nearby, key=lambda w: w["distance"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _available_space_beyond(
    wall: dict,
    violation_coord: tuple[float, float],
    boundary_polygon: Polygon,
    all_segments: list[list[float]],
    search_dist: float = 5.0,
) -> float:
    """Estimate how far the wall could be shifted outward (away from violation).

    Casts a ray from the wall midpoint outward and finds the closest obstacle
    (another wall segment or the boundary).
    """
    cx, cy = violation_coord
    wmx, wmy = wall["midpoint"]

    vec_x = wmx - cx
    vec_y = wmy - cy
    vec_len = math.hypot(vec_x, vec_y)
    if vec_len < 0.01:
        return 0.0

    # Unit vector pointing outward from violation through wall midpoint
    ux = vec_x / vec_len
    uy = vec_y / vec_len

    # Ray origin just past the wall surface
    ox, oy = wmx + ux * 0.05, wmy + uy * 0.05
    ray = LineString([(ox, oy), (ox + ux * search_dist, oy + uy * search_dist)])

    min_dist = search_dist

    # Boundary intersection
    try:
        if not boundary_polygon.exterior.is_empty:
            bd_int = ray.intersection(boundary_polygon.exterior)
            if not bd_int.is_empty:
                min_dist = min(min_dist, Point(ox, oy).distance(bd_int))
    except Exception:
        pass

    # Other wall intersections
    for seg in all_segments:
        if len(seg) < 4:
            continue
        other = LineString([(seg[0], seg[1]), (seg[2], seg[3])])
        if ray.intersects(other):
            try:
                inter = ray.intersection(other)
                if not inter.is_empty:
                    d = Point(ox, oy).distance(inter)
                    if d > 0.05:  # ignore the wall itself
                        min_dist = min(min_dist, d)
            except Exception:
                pass

    return round(min(min_dist, search_dist), 3)


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def analyze_spatial_context(
    wall_segments: list[list[float]],
    violation: dict,
    boundary_polygon: Polygon,
    required_value: float,
) -> SpatialContext:
    """Build a complete SpatialContext for *violation*.

    Parameters
    ----------
    wall_segments:
        Raw ``[x1, y1, x2, y2]`` wall segments from the geometry pipeline.
    violation:
        Violation dict (from compliance report) with ``coordinate``,
        ``measured_value``, ``required_value``, ``type``.
    boundary_polygon:
        Shapely Polygon of the walkable floor boundary.
    required_value:
        Regulatory minimum (or maximum for ramp/bottleneck violations).
    """
    coord: tuple[float, float] = (
        float(violation.get("coordinate", {}).get("x", 0.0)),
        float(violation.get("coordinate", {}).get("y", 0.0)),
    )
    measured = float(violation.get("measured_value", 0.0))

    # Gap: how far below minimum (or above maximum for ramp/bottleneck)
    vtype = violation.get("type", "")
    if vtype in ("ramp_gradient", "bottleneck"):
        gap_to_close = max(0.0, measured - required_value)
    else:
        gap_to_close = max(0.0, required_value - measured)

    gap_pct = (gap_to_close / required_value * 100) if required_value > 0 else 0.0

    # Nearby walls
    raw_nearby = find_walls_near_violation(wall_segments, coord, radius=3.0)
    nearby_walls: list[NearbyWall] = []
    for w in raw_nearby[:6]:
        avail = _available_space_beyond(
            w, coord, boundary_polygon, wall_segments
        )
        nearby_walls.append(NearbyWall(
            index=w["index"],
            x1=w["x1"], y1=w["y1"], x2=w["x2"], y2=w["y2"],
            length=w["length"],
            distance_to_violation=w["distance"],
            available_space_beyond_m=avail,
        ))

    # Structural risk
    structural_indicators: list[str] = []
    structural_risk = "low"
    for nw in nearby_walls:
        if nw.length > 3.0:
            structural_indicators.append(
                f"Wall segment {nw.length:.1f}m long at {nw.distance_to_violation:.2f}m "
                f"from violation — longer walls are more likely to be load-bearing"
            )
            if structural_risk == "low":
                structural_risk = "medium"
        if nw.length > 6.0:
            structural_risk = "high"
            structural_indicators.append(
                f"Very long wall ({nw.length:.1f}m) — high probability of structural role"
            )

    # Relocation feasibility
    if nearby_walls:
        best = max(nearby_walls, key=lambda w: w.available_space_beyond_m)
        can_relocate = best.available_space_beyond_m >= gap_to_close
        relocation = WallRelocationFeasibility(
            can_relocate=can_relocate,
            required_shift_m=round(gap_to_close, 3),
            available_space_m=round(best.available_space_beyond_m, 3),
            obstruction_present=not can_relocate,
            preferred_wall_index=nearby_walls.index(best),
            confidence=0.75 if can_relocate else 0.5,
        )
    else:
        relocation = WallRelocationFeasibility(
            can_relocate=False,
            required_shift_m=round(gap_to_close, 3),
            available_space_m=0.0,
            obstruction_present=True,
            preferred_wall_index=-1,
            confidence=0.3,
        )

    # Adjacent space estimate
    try:
        adj_circle = Point(coord).buffer(2.0)
        adj_area = round(boundary_polygon.intersection(adj_circle).area, 2)
    except Exception:
        adj_area = 0.0

    return SpatialContext(
        violation_coord=coord,
        nearby_walls=nearby_walls,
        available_corridor_width_m=measured,
        required_width_m=required_value,
        gap_to_close_m=round(gap_to_close, 3),
        gap_pct=round(gap_pct, 1),
        relocation=relocation,
        structural_risk=structural_risk,
        structural_indicators=structural_indicators,
        adjacent_space_estimate_m2=adj_area,
    )


def format_spatial_context_for_prompt(ctx: SpatialContext) -> str:
    """Return a compact spatial analysis block for the Gemini prompt."""
    lines: list[str] = ["=== SPATIAL ANALYSIS ==="]

    lines.append(
        f"Location: ({ctx.violation_coord[0]:.2f}, {ctx.violation_coord[1]:.2f}) | "
        f"Measured: {ctx.available_corridor_width_m:.3f} | "
        f"Required: {ctx.required_width_m:.3f} | "
        f"Gap: {ctx.gap_to_close_m:.3f}m ({ctx.gap_pct:.1f}%)"
    )

    if ctx.nearby_walls:
        lines.append(f"Nearby walls ({len(ctx.nearby_walls)} within 3m):")
        for i, nw in enumerate(ctx.nearby_walls[:4]):  # cap at 4
            lines.append(
                f"  W{i+1}: len={nw.length:.1f}m  dist={nw.distance_to_violation:.2f}m  "
                f"space_beyond={nw.available_space_beyond_m:.2f}m"
            )
    else:
        lines.append("No wall segments found within 3m.")

    rel = ctx.relocation
    lines.append(
        f"Relocation: need {rel.required_shift_m:.3f}m shift | "
        f"best available {rel.available_space_m:.3f}m | "
        f"{'FEASIBLE' if rel.can_relocate else 'NOT FEASIBLE'}"
    )
    lines.append(f"Structural risk: {ctx.structural_risk.upper()}")
    if ctx.structural_indicators:
        lines.append(f"  {ctx.structural_indicators[0]}")

    lines.append(f"Adjacent area: {ctx.adjacent_space_estimate_m2:.1f} m²")
    lines.append("=== END SPATIAL ANALYSIS ===")

    return "\n".join(lines)
