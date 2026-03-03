"""Chart generation for PDF compliance reports.

Uses matplotlib to render charts as PNG images that are embedded
into the reportlab-generated PDF.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ---------------------------------------------------------------------------
# Color palette (matches frontend)
# ---------------------------------------------------------------------------

_SEVERITY_COLORS = {
    "critical": "#DC2626",
    "high": "#F59E0B",
    "medium": "#FCD34D",
    "low": "#3B82F6",
}

_PRIMARY_BLUE = "#2563EB"
_BG_COLOR = "#FFFFFF"
_TEXT_COLOR = "#1F2937"
_GRID_COLOR = "#E5E7EB"

CHARTS_DIR = Path(__file__).parent.parent / "reports" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def _apply_style(ax: plt.Axes) -> None:
    """Apply consistent styling to chart axes."""
    ax.set_facecolor(_BG_COLOR)
    ax.tick_params(colors=_TEXT_COLOR, labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(_GRID_COLOR)
    ax.spines["bottom"].set_color(_GRID_COLOR)
    ax.grid(axis="y", color=_GRID_COLOR, linewidth=0.5, alpha=0.7)


# ---------------------------------------------------------------------------
# Violations by severity bar chart
# ---------------------------------------------------------------------------

def generate_violations_chart(violations_by_severity: dict) -> str:
    """Generate bar chart of violations by severity.

    Parameters
    ----------
    violations_by_severity : dict
        ``{"critical": 2, "high": 3, "medium": 2, "low": 1}``

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    severities = ["critical", "high", "medium", "low"]
    counts = [violations_by_severity.get(s, 0) for s in severities]
    colors = [_SEVERITY_COLORS[s] for s in severities]
    labels = [s.capitalize() for s in severities]

    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=150)
    fig.patch.set_facecolor(_BG_COLOR)

    bars = ax.bar(labels, counts, color=colors, width=0.55, edgecolor="white", linewidth=0.8)

    # Value labels on bars
    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15,
                str(count), ha="center", va="bottom",
                fontsize=11, fontweight="bold", color=_TEXT_COLOR,
            )

    ax.set_ylabel("Count", fontsize=10, color=_TEXT_COLOR)
    ax.set_title("Violations by Severity", fontsize=12, fontweight="bold", color=_TEXT_COLOR, pad=12)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    _apply_style(ax)

    fig.tight_layout()
    path = str(CHARTS_DIR / "violations_chart.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG_COLOR)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Violations by type bar chart
# ---------------------------------------------------------------------------

def generate_violations_by_type_chart(violations: list[dict]) -> str:
    """Generate horizontal bar chart of violations grouped by type.

    Parameters
    ----------
    violations : list[dict]
        List of violation dicts with a ``type`` field.

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    from collections import Counter

    type_counts = Counter(v.get("type", "unknown") for v in violations)
    if not type_counts:
        type_counts = {"none": 0}

    type_colors = {
        "corridor_width": "#DC2626",
        "door_width": "#F59E0B",
        "turning_space": "#EAB308",
        "ramp_gradient": "#DC2626",
        "bottleneck": "#3B82F6",
    }

    sorted_items = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
    labels = [t.replace("_", " ").title() for t, _ in sorted_items]
    counts = [c for _, c in sorted_items]
    colors = [type_colors.get(t, "#6B7280") for t, _ in sorted_items]

    fig, ax = plt.subplots(figsize=(6, max(2.5, len(labels) * 0.6)), dpi=150)
    fig.patch.set_facecolor(_BG_COLOR)

    bars = ax.barh(labels, counts, color=colors, height=0.5, edgecolor="white", linewidth=0.8)

    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(
                bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
                str(count), ha="left", va="center",
                fontsize=10, fontweight="bold", color=_TEXT_COLOR,
            )

    ax.set_xlabel("Count", fontsize=10, color=_TEXT_COLOR)
    ax.set_title("Violations by Type", fontsize=12, fontweight="bold", color=_TEXT_COLOR, pad=12)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.invert_yaxis()
    _apply_style(ax)

    fig.tight_layout()
    path = str(CHARTS_DIR / "violations_by_type_chart.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG_COLOR)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Performance metrics horizontal bar chart
# ---------------------------------------------------------------------------

def generate_metrics_chart(analytics_data: dict) -> str:
    """Generate horizontal bar chart of key performance metrics.

    Parameters
    ----------
    analytics_data : dict
        Full analytics result from ``AnalyticsEngine.compute_all()``.

    Returns
    -------
    str
        Absolute path to the saved PNG.
    """
    summary = analytics_data.get("summary", {})
    congestion = analytics_data.get("congestion_index", {})
    efficiency = analytics_data.get("efficiency_score", {})

    metrics = [
        ("Avg Velocity", summary.get("avg_velocity_ms", 0) * 100, "m/s scaled"),
        ("Congestion", congestion.get("percentage", 0), "%"),
        ("Efficiency", efficiency.get("average", 0) * 100, "%"),
        ("Peak Congestion", summary.get("peak_congestion_pct", 0), "%"),
    ]

    labels = [m[0] for m in metrics]
    values = [m[1] for m in metrics]

    # Color: green if good, orange if moderate, red if bad
    def _metric_color(name: str, val: float) -> str:
        if "Congestion" in name:
            return "#10B981" if val < 15 else "#F59E0B" if val < 30 else "#DC2626"
        if "Efficiency" in name:
            return "#10B981" if val >= 80 else "#F59E0B" if val >= 60 else "#DC2626"
        return _PRIMARY_BLUE

    colors = [_metric_color(n, v) for n, v in zip(labels, values)]

    fig, ax = plt.subplots(figsize=(6, 3), dpi=150)
    fig.patch.set_facecolor(_BG_COLOR)

    bars = ax.barh(labels, values, color=colors, height=0.5, edgecolor="white", linewidth=0.8)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}", ha="left", va="center",
            fontsize=10, fontweight="bold", color=_TEXT_COLOR,
        )

    ax.set_xlabel("Value", fontsize=10, color=_TEXT_COLOR)
    ax.set_title("Performance Metrics", fontsize=12, fontweight="bold", color=_TEXT_COLOR, pad=12)
    ax.invert_yaxis()
    _apply_style(ax)

    fig.tight_layout()
    path = str(CHARTS_DIR / "metrics_chart.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG_COLOR)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Velocity timeline chart
# ---------------------------------------------------------------------------

def generate_velocity_chart(velocity_timeline: list[dict]) -> str:
    """Generate velocity-over-time line chart."""
    if not velocity_timeline:
        return ""

    times = [p["time_sec"] for p in velocity_timeline]
    velocities = [p["avg_velocity_ms"] for p in velocity_timeline]

    fig, ax = plt.subplots(figsize=(6, 2.5), dpi=150)
    fig.patch.set_facecolor(_BG_COLOR)

    ax.plot(times, velocities, color="#06b6d4", linewidth=1.5)
    ax.fill_between(times, velocities, alpha=0.1, color="#06b6d4")
    ax.axhline(y=0.2, color="#DC2626", linestyle="--", linewidth=0.8, alpha=0.7)

    ax.set_xlabel("Time (s)", fontsize=9, color=_TEXT_COLOR)
    ax.set_ylabel("Avg Velocity (m/s)", fontsize=9, color=_TEXT_COLOR)
    ax.set_title("Velocity Over Time", fontsize=11, fontweight="bold", color=_TEXT_COLOR, pad=8)
    _apply_style(ax)

    fig.tight_layout()
    path = str(CHARTS_DIR / "velocity_chart.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG_COLOR)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Flow rate chart
# ---------------------------------------------------------------------------

def generate_flow_rate_chart(flow_rate: list[dict]) -> str:
    """Generate flow-rate-over-time line chart."""
    if not flow_rate:
        return ""

    times = [p["time_sec"] for p in flow_rate]
    rates = [p["agents_per_minute"] for p in flow_rate]

    fig, ax = plt.subplots(figsize=(6, 2.5), dpi=150)
    fig.patch.set_facecolor(_BG_COLOR)

    ax.plot(times, rates, color="#10B981", linewidth=1.5, marker="o", markersize=3)
    avg_rate = sum(rates) / len(rates) if rates else 0
    ax.axhline(y=avg_rate, color="#EAB308", linestyle="--", linewidth=0.8, alpha=0.7)

    ax.set_xlabel("Time (s)", fontsize=9, color=_TEXT_COLOR)
    ax.set_ylabel("Agents/min", fontsize=9, color=_TEXT_COLOR)
    ax.set_title("Flow Rate Over Time", fontsize=11, fontweight="bold", color=_TEXT_COLOR, pad=8)
    _apply_style(ax)

    fig.tight_layout()
    path = str(CHARTS_DIR / "flow_rate_chart.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=_BG_COLOR)
    plt.close(fig)
    return path
