"""Regulatory compliance checker for building geometry and simulation data.

Analyzes wall segments, walkable polygons, mesh vertices, and agent trajectories
against Sri Lankan Planning & Development Regulations.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from schemas import ComplianceReport, Violation, ViolationCoordinate

_REGULATIONS_PATH = Path(__file__).parent / "regulations.json"

# Severity weights (also in regulations.json but kept here for quick reference)
_SEVERITY_WEIGHTS = {"critical": 10, "high": 5, "medium": 2, "low": 1}


class ComplianceChecker:
    """Check building geometry and simulation data against regulations."""

    def __init__(self, building_type: str = "residential") -> None:
        with open(_REGULATIONS_PATH) as f:
            self._data = json.load(f)

        valid_types = list(self._data["building_types"].keys())
        if building_type not in valid_types:
            raise ValueError(
                f"Unknown building type '{building_type}'. Valid: {valid_types}"
            )

        self.building_type = building_type
        self.regs = self._data["building_types"][building_type]
        self.scoring = self._data["compliance_scoring"]
        self.sim_params = self._data.get("simulation_parameters", {})
        self._counter = 0

        print(f"[Compliance] Loaded: {self._data['metadata']['standard_name']} "
              f"v{self._data['metadata']['version']}")
        print(f"[Compliance] Building type: {building_type}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter - 1}"

    @staticmethod
    def _build_polygon(coords: list[list[float]]) -> Polygon:
        pts = [tuple(p[:2]) for p in coords]
        if pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        return Polygon(pts)

    @staticmethod
    def _deduplicate_violations(
        violations: list[Violation],
        radius: float = 1.5,
    ) -> list[Violation]:
        """Merge violations whose coordinates are within *radius* metres.

        For each cluster of nearby violations, keep only the one with the
        worst (lowest) measured_value — i.e. the most severe instance.
        """
        if not violations:
            return violations

        kept: list[Violation] = []
        used = [False] * len(violations)

        for i, vi in enumerate(violations):
            if used[i]:
                continue
            # Start a new cluster with this violation
            cluster_idx = [i]
            used[i] = True
            for j in range(i + 1, len(violations)):
                if used[j]:
                    continue
                vj = violations[j]
                dist = math.hypot(
                    vi.coordinate.x - vj.coordinate.x,
                    vi.coordinate.y - vj.coordinate.y,
                )
                if dist < radius:
                    cluster_idx.append(j)
                    used[j] = True

            # Pick the worst violation (lowest measured_value) from cluster
            best = min(cluster_idx, key=lambda k: violations[k].measured_value)
            kept.append(violations[best])

        return kept

    # ------------------------------------------------------------------
    # Check: corridor widths
    # ------------------------------------------------------------------

    def check_corridor_widths(
        self,
        wall_segments: list[list[float]],
        boundary_polygon: Polygon,
    ) -> list[Violation]:
        """Find corridors narrower than regulation minimum.

        Detects parallel wall segment pairs that form corridors and measures
        the perpendicular distance between them.
        """
        min_width = self.regs["min_corridor_width_m"]
        violations: list[Violation] = []

        if len(wall_segments) < 2:
            return violations

        # Precompute direction vectors and midpoints
        segments_info = []
        for seg in wall_segments:
            if len(seg) < 4:
                continue
            x1, y1, x2, y2 = seg[0], seg[1], seg[2], seg[3]
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            if length < 0.1:
                continue
            # Normalized direction
            nx, ny = dx / length, dy / length
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            segments_info.append({
                "seg": seg, "dir": (nx, ny), "mid": (mx, my),
                "length": length, "start": (x1, y1), "end": (x2, y2),
            })

        seen_corridors: set[tuple[int, int]] = set()

        for i in range(len(segments_info)):
            for j in range(i + 1, len(segments_info)):
                si, sj = segments_info[i], segments_info[j]
                di, dj = si["dir"], sj["dir"]

                # Check parallelism via cross product
                cross = abs(di[0] * dj[1] - di[1] * dj[0])
                if cross > 0.3:
                    continue

                # Perpendicular distance between lines
                # Vector from start_i to mid_j
                vmx = sj["mid"][0] - si["start"][0]
                vmy = sj["mid"][1] - si["start"][1]
                # Perpendicular component
                perp_dist = abs(vmx * (-di[1]) + vmy * di[0])

                if perp_dist < 0.2 or perp_dist > 5.0:
                    continue

                # Check overlap: project segment j endpoints onto segment i axis
                def project(px, py):
                    return (px - si["start"][0]) * di[0] + (py - si["start"][1]) * di[1]

                proj_j_start = project(*sj["start"])
                proj_j_end = project(*sj["end"])
                proj_i_start = 0.0
                proj_i_end = si["length"]

                overlap_start = max(min(proj_j_start, proj_j_end), proj_i_start)
                overlap_end = min(max(proj_j_start, proj_j_end), proj_i_end)
                overlap = overlap_end - overlap_start

                if overlap < 0.5:
                    continue

                # This pair forms a corridor
                key = (min(i, j), max(i, j))
                if key in seen_corridors:
                    continue
                seen_corridors.add(key)

                if perp_dist < min_width:
                    # Midpoint of corridor
                    cx = (si["mid"][0] + sj["mid"][0]) / 2
                    cy = (si["mid"][1] + sj["mid"][1]) / 2

                    ratio = perp_dist / min_width
                    severity = "critical" if ratio < 0.5 else "high" if ratio < 0.75 else "medium"

                    violations.append(Violation(
                        id=self._next_id("corridor_width"),
                        type="corridor_width",
                        severity=severity,
                        coordinate=ViolationCoordinate(x=round(cx, 4), y=round(cy, 4)),
                        measured_value=round(perp_dist, 2),
                        required_value=min_width,
                        description=(
                            f"Corridor width {perp_dist:.2f}m is less than "
                            f"required {min_width}m for {self.building_type}"
                        ),
                        regulation=(
                            "Sri Lankan Planning & Development Regulations "
                            f"- Min Corridor Width ({min_width}m)"
                        ),
                    ))

        # Also check narrow passages via polygon negative buffer
        shrunk = boundary_polygon.buffer(-min_width / 2)
        if shrunk.is_empty and boundary_polygon.area > 1.0:
            # Entire polygon is narrower than required corridor
            c = boundary_polygon.centroid
            violations.append(Violation(
                id=self._next_id("corridor_width"),
                type="corridor_width",
                severity="critical",
                coordinate=ViolationCoordinate(x=round(c.x, 4), y=round(c.y, 4)),
                measured_value=0.0,
                required_value=min_width,
                description=(
                    f"Building footprint is too narrow for {min_width}m corridors"
                ),
                regulation=(
                    "Sri Lankan Planning & Development Regulations "
                    f"- Min Corridor Width ({min_width}m)"
                ),
            ))

        # Deduplicate spatially close violations (keep worst per cluster)
        violations = self._deduplicate_violations(violations, radius=1.5)
        return violations

    # ------------------------------------------------------------------
    # Check: door widths
    # ------------------------------------------------------------------

    def check_door_widths(
        self,
        wall_segments: list[list[float]],
        boundary_polygon: Polygon,
    ) -> list[Violation]:
        """Find doors (wall gaps) narrower than regulation minimum."""
        min_width = self.regs["min_door_width_m"]
        violations: list[Violation] = []

        if len(wall_segments) < 2:
            return violations

        # Collect all endpoints
        endpoints: list[tuple[float, float, int]] = []
        for idx, seg in enumerate(wall_segments):
            if len(seg) < 4:
                continue
            endpoints.append((seg[0], seg[1], idx))
            endpoints.append((seg[2], seg[3], idx))

        seen_doors: list[tuple[float, float]] = []

        for a in range(len(endpoints)):
            for b in range(a + 1, len(endpoints)):
                ea, eb = endpoints[a], endpoints[b]
                # Must be from different wall segments
                if ea[2] == eb[2]:
                    continue

                gap = math.hypot(ea[0] - eb[0], ea[1] - eb[1])
                if gap < 0.3 or gap > 2.5:
                    continue

                # Midpoint should be inside the boundary
                mx, my = (ea[0] + eb[0]) / 2, (ea[1] + eb[1]) / 2
                if not boundary_polygon.contains(Point(mx, my)):
                    continue

                # Check this isn't along the same wall direction
                seg_a = wall_segments[ea[2]]
                da = (seg_a[2] - seg_a[0], seg_a[3] - seg_a[1])
                la = math.hypot(*da)
                if la < 0.01:
                    continue
                da_norm = (da[0] / la, da[1] / la)

                gap_dir = (eb[0] - ea[0], eb[1] - ea[1])
                gap_len = math.hypot(*gap_dir)
                if gap_len < 0.01:
                    continue
                gap_norm = (gap_dir[0] / gap_len, gap_dir[1] / gap_len)

                # Dot product — if near 1, they're collinear (same wall), skip
                dot = abs(da_norm[0] * gap_norm[0] + da_norm[1] * gap_norm[1])
                if dot > 0.85:
                    continue

                # Deduplicate: check if we already found a door near this point
                if any(math.hypot(mx - dx, my - dy) < 0.5 for dx, dy in seen_doors):
                    continue
                seen_doors.append((mx, my))

                if gap < min_width:
                    severity = "high" if gap < min_width * 0.85 else "medium"
                    violations.append(Violation(
                        id=self._next_id("door_width"),
                        type="door_width",
                        severity=severity,
                        coordinate=ViolationCoordinate(x=round(mx, 4), y=round(my, 4)),
                        measured_value=round(gap, 2),
                        required_value=min_width,
                        description=(
                            f"Door width {gap:.2f}m is less than "
                            f"required {min_width}m for {self.building_type}"
                        ),
                        regulation=(
                            "Sri Lankan Planning & Development Regulations "
                            f"- Min Door Width ({min_width}m)"
                        ),
                    ))

        return violations

    # ------------------------------------------------------------------
    # Check: turning spaces
    # ------------------------------------------------------------------

    def check_turning_spaces(
        self,
        wall_segments: list[list[float]],
        boundary_polygon: Polygon,
    ) -> list[Violation]:
        """Find locations missing wheelchair turning space."""
        min_turning = self.regs["min_turning_space_m"]
        violations: list[Violation] = []

        # Build walkable area: polygon minus wall buffers
        wall_buffers = []
        for seg in wall_segments:
            if len(seg) < 4:
                continue
            line = LineString([(seg[0], seg[1]), (seg[2], seg[3])])
            wall_buffers.append(line.buffer(0.15))

        walkable = boundary_polygon
        if wall_buffers:
            walls_union = unary_union(wall_buffers)
            walkable = boundary_polygon.difference(walls_union)
            if walkable.is_empty:
                walkable = boundary_polygon

        # Critical points to check: wall endpoints and corridor intersections
        check_points: list[tuple[float, float]] = []
        for seg in wall_segments:
            if len(seg) < 4:
                continue
            check_points.append((seg[0], seg[1]))
            check_points.append((seg[2], seg[3]))

        # Deduplicate check points
        unique_points: list[tuple[float, float]] = []
        for px, py in check_points:
            if not any(math.hypot(px - ux, py - uy) < 0.3 for ux, uy in unique_points):
                unique_points.append((px, py))

        for px, py in unique_points:
            pt = Point(px, py)
            if not boundary_polygon.contains(pt):
                continue

            # Check if a turning circle fits
            turning_circle = pt.buffer(min_turning / 2)
            if not walkable.contains(turning_circle):
                # Measure what diameter actually fits
                dist_to_boundary = pt.distance(walkable.boundary)
                measured = round(dist_to_boundary * 2, 2)

                violations.append(Violation(
                    id=self._next_id("turning_space"),
                    type="turning_space",
                    severity="high",
                    coordinate=ViolationCoordinate(x=round(px, 4), y=round(py, 4)),
                    measured_value=measured,
                    required_value=min_turning,
                    description=(
                        f"Wheelchair turning space {measured}m available, "
                        f"requires {min_turning}m diameter at this location"
                    ),
                    regulation=(
                        "Sri Lankan Planning & Development Regulations "
                        f"- Min Turning Space ({min_turning}m diameter)"
                    ),
                ))

        # Deduplicate spatially close violations (keep worst per cluster)
        violations = self._deduplicate_violations(violations, radius=1.0)
        return violations

    # ------------------------------------------------------------------
    # Check: ramp gradients
    # ------------------------------------------------------------------

    def check_ramp_gradients(
        self,
        mesh_vertices: np.ndarray | list,
    ) -> list[Violation]:
        """Find ramps steeper than regulation maximum.

        Analyzes vertex neighborhoods to detect sloped surfaces.
        """
        max_gradient = self.regs["max_ramp_gradient"]
        violations: list[Violation] = []

        verts = np.asarray(mesh_vertices, dtype=float)
        if verts.shape[0] < 10 or verts.shape[1] < 3:
            return violations

        # Filter to vertices near floor level (ramps are low structures)
        z_range = verts[:, 2].max() - verts[:, 2].min()
        if z_range < 0.1:
            return violations

        # Look for sloped regions: vertices between 0.05m and 2m height
        ramp_candidates = verts[(verts[:, 2] > 0.05) & (verts[:, 2] < 2.0)]
        if len(ramp_candidates) < 5:
            return violations

        # Use KDTree for neighborhood queries
        from scipy.spatial import KDTree
        xy_coords = ramp_candidates[:, :2]
        tree = KDTree(xy_coords)

        # Sample points and compute local gradients
        steep_points: list[tuple[float, float, float, float]] = []
        step = max(1, len(ramp_candidates) // 200)  # sample up to 200 points

        for i in range(0, len(ramp_candidates), step):
            px, py, pz = ramp_candidates[i]
            # Find neighbors within 1m horizontal radius
            neighbors_idx = tree.query_ball_point([px, py], r=1.0)
            if len(neighbors_idx) < 3:
                continue

            # Compute gradient as max dZ / dXY among neighbors
            max_grad = 0.0
            for j in neighbors_idx:
                if j == i:
                    continue
                qx, qy, qz = ramp_candidates[j]
                dxy = math.hypot(qx - px, qy - py)
                if dxy < 0.1:
                    continue
                grad = abs(qz - pz) / dxy
                max_grad = max(max_grad, grad)

            if max_grad > max_gradient:
                steep_points.append((px, py, pz, max_grad))

        if not steep_points:
            return violations

        # Cluster steep points (simple grid-based clustering)
        clusters: list[list[tuple[float, float, float, float]]] = []
        used = [False] * len(steep_points)

        for i, sp in enumerate(steep_points):
            if used[i]:
                continue
            cluster = [sp]
            used[i] = True
            for j in range(i + 1, len(steep_points)):
                if used[j]:
                    continue
                if math.hypot(sp[0] - steep_points[j][0], sp[1] - steep_points[j][1]) < 2.0:
                    cluster.append(steep_points[j])
                    used[j] = True
            clusters.append(cluster)

        for cluster in clusters:
            cx = sum(p[0] for p in cluster) / len(cluster)
            cy = sum(p[1] for p in cluster) / len(cluster)
            cz = sum(p[2] for p in cluster) / len(cluster)
            max_grad = max(p[3] for p in cluster)

            ratio = max_grad / max_gradient
            severity = "critical" if ratio > 2.0 else "high" if ratio > 1.5 else "medium"

            gradient_pct = round(max_grad * 100, 1)
            max_pct = round(max_gradient * 100, 1)

            violations.append(Violation(
                id=self._next_id("ramp_gradient"),
                type="ramp_gradient",
                severity=severity,
                coordinate=ViolationCoordinate(
                    x=round(cx, 4), y=round(cy, 4), z=round(cz, 4)
                ),
                measured_value=round(max_grad, 4),
                required_value=max_gradient,
                description=(
                    f"Ramp gradient {gradient_pct}% exceeds maximum "
                    f"{max_pct}% ({self.regs.get('max_ramp_gradient_ratio', '1:12')})"
                ),
                regulation=(
                    "Sri Lankan Planning & Development Regulations "
                    f"- Max Ramp Gradient ({max_pct}%)"
                ),
            ))

        return violations

    # ------------------------------------------------------------------
    # Check: bottlenecks (from simulation data)
    # ------------------------------------------------------------------

    def check_bottlenecks(
        self,
        trajectories: dict,
        boundary_polygon: Polygon,
        floor_area: float,
    ) -> list[Violation]:
        """Find areas with dangerous agent density during simulation."""
        max_density = self.regs.get("max_safe_density_persons_per_sqm", 2.0)
        duration_threshold = self.regs.get("bottleneck_duration_threshold_sec", 5.0)
        violations: list[Violation] = []

        if not trajectories:
            return violations

        # Grid parameters
        cell_size = 1.0  # 1m x 1m cells
        sim_hz = 10      # frames per second
        frame_threshold = int(duration_threshold * sim_hz)

        minx, miny, maxx, maxy = boundary_polygon.bounds
        nx = max(1, int(math.ceil((maxx - minx) / cell_size)))
        ny = max(1, int(math.ceil((maxy - miny) / cell_size)))

        # Count agents per cell per frame
        # density_time[ix][iy] = number of frames where density > threshold
        density_time = np.zeros((nx, ny), dtype=int)
        peak_density = np.zeros((nx, ny), dtype=float)

        for frame_key, frame_data in trajectories.items():
            # Count agents per cell in this frame
            cell_counts = np.zeros((nx, ny), dtype=int)
            for agent_data in frame_data.values():
                pos = agent_data.get("pos", [0, 0])
                ix = int((pos[0] - minx) / cell_size)
                iy = int((pos[1] - miny) / cell_size)
                ix = max(0, min(nx - 1, ix))
                iy = max(0, min(ny - 1, iy))
                cell_counts[ix, iy] += 1

            # Convert to density (agents per m²)
            cell_area = cell_size * cell_size
            densities = cell_counts / cell_area

            # Track time above threshold
            above_mask = densities > max_density
            density_time += above_mask.astype(int)
            peak_density = np.maximum(peak_density, densities)

        # Find bottleneck cells: density exceeded for longer than threshold
        for ix in range(nx):
            for iy in range(ny):
                if density_time[ix, iy] < frame_threshold:
                    continue

                # Verify the cell center is inside the polygon
                cx = minx + (ix + 0.5) * cell_size
                cy = miny + (iy + 0.5) * cell_size
                if not boundary_polygon.contains(Point(cx, cy)):
                    continue

                pd = peak_density[ix, iy]
                duration_sec = density_time[ix, iy] / sim_hz

                severity = "high" if pd > max_density * 1.5 else "medium"

                violations.append(Violation(
                    id=self._next_id("bottleneck"),
                    type="bottleneck",
                    severity=severity,
                    coordinate=ViolationCoordinate(x=round(cx, 4), y=round(cy, 4)),
                    measured_value=round(pd, 2),
                    required_value=max_density,
                    description=(
                        f"Agent density {pd:.1f} persons/m² exceeds "
                        f"{max_density} persons/m² for {duration_sec:.1f}s"
                    ),
                    regulation=(
                        "Sri Lankan Planning & Development Regulations "
                        f"- Max Safe Density ({max_density} persons/m²)"
                    ),
                ))

        # Deduplicate spatially close violations (keep worst per cluster)
        violations = self._deduplicate_violations(violations, radius=2.0)
        return violations

    # ------------------------------------------------------------------
    # Score computation
    # ------------------------------------------------------------------

    def _compute_score(self, violations: list[Violation]) -> tuple[float, str]:
        """Compute compliance score and pass/fail status."""
        weights = {
            "critical": self.scoring["critical_violations"]["weight"],
            "high": self.scoring["high_violations"]["weight"],
            "medium": self.scoring["medium_violations"]["weight"],
            "low": self.scoring["low_violations"]["weight"],
        }
        total_deduction = sum(weights.get(v.severity, 1) for v in violations)
        score = max(0.0, 100.0 - total_deduction)
        threshold = self.scoring["pass_threshold_percent"]
        status = "pass" if score >= threshold else "fail"
        return round(score, 1), status

    # ------------------------------------------------------------------
    # Full audit
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Context helpers (used by AI recommendation engine)
    # ------------------------------------------------------------------

    @staticmethod
    def find_walls_near_violation(
        wall_segments: list[list[float]],
        coord: tuple[float, float],
        radius: float = 3.0,
    ) -> list[dict]:
        """Return wall segments within *radius* metres of *coord*.

        Delegates to spatial_analyzer for consistent logic.
        """
        from core.spatial_analyzer import find_walls_near_violation
        return find_walls_near_violation(wall_segments, coord, radius)

    def run_full_audit(
        self,
        wall_segments: list[list[float]],
        boundary_coords: list[list[float]],
        mesh_vertices: list | np.ndarray | None = None,
        trajectories: dict | None = None,
        floor_area: float = 0.0,
    ) -> ComplianceReport:
        """Run all compliance checks and return a full report."""
        polygon = self._build_polygon(boundary_coords)

        if not polygon.is_valid or polygon.is_empty:
            print("[Compliance] WARNING: invalid boundary polygon")
            return ComplianceReport(
                standard=self._data["metadata"]["standard_name"],
                building_type=self.building_type,
                total_violations=0,
                violations=[],
                compliance_score=100.0,
                status="pass",
                summary={"critical": 0, "high": 0, "medium": 0, "low": 0},
            )

        violations: list[Violation] = []

        # Geometry-based checks
        violations += self.check_corridor_widths(wall_segments, polygon)
        violations += self.check_door_widths(wall_segments, polygon)
        violations += self.check_turning_spaces(wall_segments, polygon)

        if mesh_vertices is not None:
            verts = np.asarray(mesh_vertices, dtype=float)
            if verts.ndim == 2 and verts.shape[1] >= 3:
                violations += self.check_ramp_gradients(verts)

        # Simulation-based checks
        if trajectories is not None:
            violations += self.check_bottlenecks(trajectories, polygon, floor_area)

        score, status = self._compute_score(violations)
        summary_counter = Counter(v.severity for v in violations)

        report = ComplianceReport(
            standard=self._data["metadata"]["standard_name"],
            building_type=self.building_type,
            total_violations=len(violations),
            violations=[v for v in violations],
            compliance_score=score,
            status=status,
            summary={
                "critical": summary_counter.get("critical", 0),
                "high": summary_counter.get("high", 0),
                "medium": summary_counter.get("medium", 0),
                "low": summary_counter.get("low", 0),
            },
        )

        print(f"[Compliance] Audit complete: {report.total_violations} violations detected")
        print(f"[Compliance] Compliance score: {report.compliance_score}%")
        return report
