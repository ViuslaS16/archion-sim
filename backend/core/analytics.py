"""Analytics engine for processing simulation trajectory data into performance metrics."""

from __future__ import annotations

import math

import numpy as np
from scipy.ndimage import gaussian_filter
from shapely.geometry import Point, Polygon

SIM_HZ = 10  # frames per second (must match sim/engine.py)
DT = 1.0 / SIM_HZ  # seconds per frame
SLOW_THRESHOLD = 0.2  # m/s — agents below this are "congested"
EXIT_THRESHOLD = 1.0  # m — distance to boundary edge to count as "exited"
HEATMAP_RESOLUTION = 0.5  # meters per grid cell


class AnalyticsEngine:
    """Process simulation trajectory data into performance metrics."""

    def __init__(
        self,
        trajectories: dict,
        boundary_coords: list,
        exit_pos: list | None = None,
        floor_area: float = 0.0,
    ) -> None:
        self._traj = trajectories
        self._boundary = boundary_coords
        self._exit_pos = exit_pos
        self._floor_area = floor_area
        self._polygon = self._build_polygon(boundary_coords)

        # Parse trajectory into numpy arrays
        self._frame_keys = sorted(trajectories.keys(), key=int)
        self._n_frames = len(self._frame_keys)

        if self._n_frames > 0:
            self._agent_ids = sorted(trajectories[self._frame_keys[0]].keys(), key=int)
        else:
            self._agent_ids = []
        self._n_agents = len(self._agent_ids)

        # Build position array: shape (n_frames, n_agents, 2)
        self._positions = np.zeros((self._n_frames, self._n_agents, 2))
        for fi, fk in enumerate(self._frame_keys):
            frame = trajectories[fk]
            for ai, aid in enumerate(self._agent_ids):
                if aid in frame:
                    self._positions[fi, ai] = frame[aid]["pos"]

        # Compute velocities: shape (n_frames-1, n_agents)
        if self._n_frames > 1:
            deltas = np.diff(self._positions, axis=0)
            self._velocities = np.linalg.norm(deltas, axis=2) / DT
        else:
            self._velocities = np.zeros((0, self._n_agents))

        print(f"[Analytics] Parsed {self._n_frames} frames, {self._n_agents} agents")

    @staticmethod
    def _build_polygon(coords: list) -> Polygon:
        pts = [tuple(p[:2]) for p in coords]
        if pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        if len(pts) < 4:
            return Polygon()
        return Polygon(pts)

    # ------------------------------------------------------------------
    # Flow rate
    # ------------------------------------------------------------------
    def _compute_flow_rate(self) -> list[dict]:
        """Track agents reaching boundary edge per time window."""
        if self._n_frames < 2 or self._n_agents == 0:
            return []

        boundary_np = np.array(self._boundary)
        window_frames = SIM_HZ * 10  # 10-second windows
        results: list[dict] = []

        # Track when each agent first reaches within EXIT_THRESHOLD of boundary
        exited_frame: dict[int, int] = {}

        for fi in range(self._n_frames):
            for ai in range(self._n_agents):
                if ai in exited_frame:
                    continue
                pos = self._positions[fi, ai]
                # Check distance to nearest boundary segment
                min_dist = self._point_to_polygon_boundary_dist(pos)
                if min_dist < EXIT_THRESHOLD:
                    exited_frame[ai] = fi

        # Bin exits into windows
        n_windows = max(1, math.ceil(self._n_frames / window_frames))
        for w in range(n_windows):
            start_frame = w * window_frames
            end_frame = min((w + 1) * window_frames, self._n_frames)
            exits_in_window = sum(
                1 for af in exited_frame.values()
                if start_frame <= af < end_frame
            )
            window_duration_min = (end_frame - start_frame) / SIM_HZ / 60.0
            rate = exits_in_window / window_duration_min if window_duration_min > 0 else 0
            results.append({
                "time_sec": round(start_frame / SIM_HZ, 1),
                "agents_per_minute": round(rate, 2),
            })

        return results

    def _point_to_polygon_boundary_dist(self, pos: np.ndarray) -> float:
        """Distance from a point to the nearest polygon boundary edge."""
        pt = Point(pos[0], pos[1])
        return self._polygon.exterior.distance(pt) if not self._polygon.is_empty else float("inf")

    # ------------------------------------------------------------------
    # Congestion index
    # ------------------------------------------------------------------
    def _compute_congestion_index(self) -> dict:
        """Percentage of agent-frames where velocity < threshold."""
        if self._velocities.size == 0:
            return {"percentage": 0.0, "slow_threshold_ms": SLOW_THRESHOLD}

        slow_count = np.sum(self._velocities < SLOW_THRESHOLD)
        total = self._velocities.size
        pct = float(slow_count / total * 100)

        return {
            "percentage": round(pct, 1),
            "slow_threshold_ms": SLOW_THRESHOLD,
        }

    # ------------------------------------------------------------------
    # Efficiency score
    # ------------------------------------------------------------------
    def _compute_efficiency_score(self) -> dict:
        """Compare ideal path length vs actual path taken."""
        if self._n_frames < 2 or self._n_agents == 0:
            return {"average": 0.0, "per_agent": []}

        per_agent: list[float] = []
        for ai in range(self._n_agents):
            start = self._positions[0, ai]
            end = self._positions[-1, ai]
            ideal = float(np.linalg.norm(end - start))

            # Actual = sum of segment lengths
            segments = np.diff(self._positions[:, ai], axis=0)
            actual = float(np.sum(np.linalg.norm(segments, axis=1)))

            if actual > 0:
                eff = min(ideal / actual, 1.0)
            else:
                eff = 1.0 if ideal < 0.01 else 0.0

            per_agent.append(round(eff, 3))

        avg = float(np.mean(per_agent)) if per_agent else 0.0
        return {
            "average": round(avg, 3),
            "per_agent": per_agent,
        }

    # ------------------------------------------------------------------
    # Density heatmap
    # ------------------------------------------------------------------
    def _compute_density_heatmap(self) -> dict:
        """Generate 2D density grid using histogram2d + gaussian blur."""
        if self._n_frames == 0 or self._n_agents == 0:
            return {"grid": [], "bounds": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
                    "resolution": HEATMAP_RESOLUTION, "shape": [0, 0]}

        # Flatten all positions
        all_pos = self._positions.reshape(-1, 2)
        x_all = all_pos[:, 0]
        y_all = all_pos[:, 1]

        # Bounds from polygon
        if not self._polygon.is_empty:
            bx_min, by_min, bx_max, by_max = self._polygon.bounds
        else:
            bx_min, by_min = float(x_all.min()), float(y_all.min())
            bx_max, by_max = float(x_all.max()), float(y_all.max())

        # Add small padding
        pad = HEATMAP_RESOLUTION
        bx_min -= pad
        by_min -= pad
        bx_max += pad
        by_max += pad

        n_bins_x = max(1, int(math.ceil((bx_max - bx_min) / HEATMAP_RESOLUTION)))
        n_bins_y = max(1, int(math.ceil((by_max - by_min) / HEATMAP_RESOLUTION)))

        hist, _, _ = np.histogram2d(
            y_all, x_all,
            bins=[n_bins_y, n_bins_x],
            range=[[by_min, by_max], [bx_min, bx_max]],
        )

        # Gaussian smooth
        hist = gaussian_filter(hist, sigma=1.0)

        # Normalize 0-1
        max_val = hist.max()
        if max_val > 0:
            grid_norm = hist / max_val
        else:
            grid_norm = hist

        return {
            "grid": grid_norm.tolist(),
            "bounds": {
                "min_x": round(bx_min, 2),
                "min_y": round(by_min, 2),
                "max_x": round(bx_max, 2),
                "max_y": round(by_max, 2),
            },
            "resolution": HEATMAP_RESOLUTION,
            "shape": [n_bins_y, n_bins_x],
            "max_density": round(float(max_val), 1),
        }

    # ------------------------------------------------------------------
    # Congestion timeline
    # ------------------------------------------------------------------
    def _compute_congestion_timeline(self) -> list[dict]:
        """Congestion percentage per 5-second window."""
        if self._velocities.size == 0:
            return []

        window_frames = SIM_HZ * 5  # 5-second windows
        n_windows = max(1, math.ceil(self._velocities.shape[0] / window_frames))
        results: list[dict] = []

        for w in range(n_windows):
            start = w * window_frames
            end = min((w + 1) * window_frames, self._velocities.shape[0])
            chunk = self._velocities[start:end]
            if chunk.size == 0:
                continue
            slow_pct = float(np.sum(chunk < SLOW_THRESHOLD) / chunk.size * 100)
            results.append({
                "time_sec": round(start / SIM_HZ, 1),
                "congestion_pct": round(slow_pct, 1),
            })

        return results

    # ------------------------------------------------------------------
    # Velocity timeline
    # ------------------------------------------------------------------
    def _compute_velocity_timeline(self) -> list[dict]:
        """Average velocity per 1-second bucket."""
        if self._velocities.size == 0:
            return []

        bucket_frames = SIM_HZ  # 10 frames = 1 second
        n_buckets = max(1, math.ceil(self._velocities.shape[0] / bucket_frames))
        results: list[dict] = []

        for b in range(n_buckets):
            start = b * bucket_frames
            end = min((b + 1) * bucket_frames, self._velocities.shape[0])
            chunk = self._velocities[start:end]
            if chunk.size == 0:
                continue
            results.append({
                "time_sec": round(b, 1),
                "avg_velocity_ms": round(float(np.mean(chunk)), 3),
            })

        return results

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _compute_summary(self) -> dict:
        """Aggregate summary metrics."""
        sim_duration = self._n_frames / SIM_HZ if self._n_frames > 0 else 0

        if self._velocities.size > 0:
            avg_vel = float(np.mean(self._velocities))
            peak_congestion = float(
                np.max([
                    np.sum(self._velocities[i] < SLOW_THRESHOLD) / self._n_agents * 100
                    for i in range(self._velocities.shape[0])
                ]) if self._velocities.shape[0] > 0 else 0
            )
        else:
            avg_vel = 0.0
            peak_congestion = 0.0

        # Total distance traveled by all agents
        if self._n_frames > 1:
            segments = np.diff(self._positions, axis=0)
            total_dist = float(np.sum(np.linalg.norm(segments, axis=2)))
        else:
            total_dist = 0.0

        return {
            "total_agents": self._n_agents,
            "simulation_duration_sec": round(sim_duration, 1),
            "avg_velocity_ms": round(avg_vel, 3),
            "peak_congestion_pct": round(peak_congestion, 1),
            "total_distance_m": round(total_dist, 1),
            "floor_area_sqm": round(self._floor_area, 2),
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def compute_all(self) -> dict:
        """Run all analytics and return the full result dict."""
        flow_rate = self._compute_flow_rate()
        congestion = self._compute_congestion_index()
        efficiency = self._compute_efficiency_score()
        heatmap = self._compute_density_heatmap()
        cong_timeline = self._compute_congestion_timeline()
        vel_timeline = self._compute_velocity_timeline()
        summary = self._compute_summary()

        # Compute average flow rate
        avg_flow = (
            sum(p["agents_per_minute"] for p in flow_rate) / len(flow_rate)
            if flow_rate else 0
        )

        print(f"[Analytics] Flow rate: {avg_flow:.1f} agents/min")
        print(f"[Analytics] Congestion index: {congestion['percentage']}%")
        print(f"[Analytics] Efficiency score: {efficiency['average'] * 100:.1f}%")
        print(f"[Analytics] Heatmap: {heatmap['shape'][0]}x{heatmap['shape'][1]} grid")

        return {
            "flow_rate": flow_rate,
            "congestion_index": congestion,
            "efficiency_score": efficiency,
            "density_heatmap": heatmap,
            "congestion_timeline": cong_timeline,
            "velocity_timeline": vel_timeline,
            "summary": summary,
        }


# ---------------------------------------------------------------------------
# Standalone heatmap PNG generation
# ---------------------------------------------------------------------------

def generate_heatmap_png(heatmap_data: dict, output_path: str) -> str:
    """Render heatmap grid as a PNG image using matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    grid = np.array(heatmap_data["grid"])
    if grid.size == 0:
        # Create a blank placeholder
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return output_path

    bounds = heatmap_data["bounds"]
    extent = [bounds["min_x"], bounds["max_x"], bounds["min_y"], bounds["max_y"]]

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(
        grid,
        origin="lower",
        extent=extent,
        cmap="jet",
        alpha=0.85,
        vmin=0,
        vmax=1,
        interpolation="bilinear",
    )
    ax.set_xlabel("X (m)", fontsize=10)
    ax.set_ylabel("Y (m)", fontsize=10)
    ax.set_title("Agent Density Heatmap", fontsize=13, fontweight="bold")
    cbar = plt.colorbar(im, ax=ax, label="Normalized Density", shrink=0.85)
    cbar.ax.tick_params(labelsize=8)

    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[Analytics] Heatmap PNG saved: {output_path}")
    return output_path
