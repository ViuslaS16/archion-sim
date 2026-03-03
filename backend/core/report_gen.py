"""PDF report generator for architectural compliance audit reports."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
)

# Theme colors
CYAN = HexColor("#06b6d4")
DARK = HexColor("#18181b")
GRAY = HexColor("#71717a")
LIGHT_GRAY = HexColor("#e4e4e7")
RED = HexColor("#DC2626")
GREEN = HexColor("#16a34a")
ORANGE = HexColor("#F59E0B")
YELLOW = HexColor("#EAB308")
BLUE = HexColor("#3B82F6")

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

SEVERITY_COLORS = {
    "critical": RED,
    "high": ORANGE,
    "medium": YELLOW,
    "low": BLUE,
}

PAGE_W, PAGE_H = A4


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=24,
            leading=30, alignment=TA_CENTER, textColor=DARK,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="Helvetica", fontSize=13,
            leading=18, alignment=TA_CENTER, textColor=GRAY,
        ),
        "h1": ParagraphStyle(
            "h1", fontName="Helvetica-Bold", fontSize=16,
            leading=22, textColor=DARK, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", fontName="Helvetica-Bold", fontSize=12,
            leading=16, textColor=DARK, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=10,
            leading=14, textColor=DARK,
        ),
        "caption": ParagraphStyle(
            "caption", fontName="Helvetica", fontSize=8,
            leading=10, textColor=GRAY, alignment=TA_CENTER,
        ),
        "badge_pass": ParagraphStyle(
            "badge_pass", fontName="Helvetica-Bold", fontSize=14,
            leading=18, alignment=TA_CENTER, textColor=GREEN,
        ),
        "badge_fail": ParagraphStyle(
            "badge_fail", fontName="Helvetica-Bold", fontSize=14,
            leading=18, alignment=TA_CENTER, textColor=RED,
        ),
    }


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _fig_to_image(fig: plt.Figure, width: float = 160 * mm, height: float = 80 * mm) -> Image:
    """Convert a matplotlib figure to a reportlab Image."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width, height=height)


def _violations_bar_chart(violations: list[dict]) -> Image:
    """Bar chart of violation counts by type."""
    type_counts: dict[str, int] = {}
    type_severity: dict[str, str] = {}
    for v in violations:
        vt = v.get("type", "unknown").replace("_", " ").title()
        type_counts[vt] = type_counts.get(vt, 0) + 1
        type_severity.setdefault(vt, v.get("severity", "medium"))

    if not type_counts:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "No violations", ha="center", va="center")
        ax.set_axis_off()
        return _fig_to_image(fig)

    sev_colors = {
        "critical": "#DC2626", "high": "#F59E0B",
        "medium": "#EAB308", "low": "#3B82F6",
    }
    labels = list(type_counts.keys())
    counts = list(type_counts.values())
    colors = [sev_colors.get(type_severity.get(l, "medium"), "#6B7280") for l in labels]

    fig, ax = plt.subplots(figsize=(6, 3))
    bars = ax.barh(labels, counts, color=colors, edgecolor="white", height=0.5)
    ax.set_xlabel("Count", fontsize=9)
    ax.set_title("Violations by Type", fontsize=11, fontweight="bold")
    ax.tick_params(labelsize=8)
    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                str(count), va="center", fontsize=8, fontweight="bold")
    ax.invert_yaxis()
    fig.tight_layout()
    return _fig_to_image(fig)


def _velocity_chart(velocity_timeline: list[dict]) -> Image:
    """Line chart of average velocity over time."""
    if not velocity_timeline:
        fig, ax = plt.subplots(figsize=(6, 2.5))
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_axis_off()
        return _fig_to_image(fig, height=60 * mm)

    times = [p["time_sec"] for p in velocity_timeline]
    vels = [p["avg_velocity_ms"] for p in velocity_timeline]

    fig, ax = plt.subplots(figsize=(6, 2.5))
    ax.plot(times, vels, color="#06b6d4", linewidth=1.5)
    ax.axhline(y=0.2, color="#DC2626", linestyle="--", linewidth=0.8, label="Congestion threshold")
    ax.fill_between(times, vels, alpha=0.15, color="#06b6d4")
    ax.set_xlabel("Time (s)", fontsize=9)
    ax.set_ylabel("Avg Velocity (m/s)", fontsize=9)
    ax.set_title("Agent Velocity Over Time", fontsize=11, fontweight="bold")
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    return _fig_to_image(fig, height=60 * mm)


def _flow_rate_chart(flow_rate: list[dict]) -> Image:
    """Line chart of flow rate over time."""
    if not flow_rate:
        fig, ax = plt.subplots(figsize=(6, 2.5))
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_axis_off()
        return _fig_to_image(fig, height=60 * mm)

    times = [p["time_sec"] for p in flow_rate]
    rates = [p["agents_per_minute"] for p in flow_rate]

    fig, ax = plt.subplots(figsize=(6, 2.5))
    ax.plot(times, rates, color="#10B981", linewidth=1.5, marker="o", markersize=4)
    ax.fill_between(times, rates, alpha=0.15, color="#10B981")
    avg_rate = sum(rates) / len(rates) if rates else 0
    ax.axhline(y=avg_rate, color="#F59E0B", linestyle="--", linewidth=0.8, label=f"Avg: {avg_rate:.1f}")
    ax.set_xlabel("Time (s)", fontsize=9)
    ax.set_ylabel("Agents/min", fontsize=9)
    ax.set_title("Flow Rate", fontsize=11, fontweight="bold")
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    return _fig_to_image(fig, height=60 * mm)


def _severity_pie_chart(violations: list[dict]) -> Image:
    """Pie chart of violation counts by severity."""
    sev_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for v in violations:
        s = v.get("severity", "medium")
        sev_counts[s] = sev_counts.get(s, 0) + 1

    labels = [k.title() for k, c in sev_counts.items() if c > 0]
    counts = [c for c in sev_counts.values() if c > 0]
    colors = ["#DC2626", "#F59E0B", "#EAB308", "#3B82F6"]
    colors = [c for c, cnt in zip(colors, sev_counts.values()) if cnt > 0]

    if not counts:
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.text(0.5, 0.5, "No violations", ha="center", va="center")
        ax.set_axis_off()
        return _fig_to_image(fig, width=120 * mm, height=100 * mm)

    fig, ax = plt.subplots(figsize=(5, 4))
    wedges, texts, autotexts = ax.pie(
        counts, labels=labels, colors=colors, autopct="%1.0f%%",
        startangle=90, textprops={"fontsize": 9},
    )
    for t in autotexts:
        t.set_fontweight("bold")
        t.set_color("white")
    ax.set_title("Violations by Severity", fontsize=12, fontweight="bold")
    fig.tight_layout()
    return _fig_to_image(fig, width=120 * mm, height=100 * mm)


def _compliance_radar_chart(compliance_report: dict, analytics: dict) -> Image:
    """Radar/spider chart of compliance category scores."""
    categories = ["Corridor\nWidth", "Door\nWidth", "Turning\nSpace", "Ramp\nGradient", "Flow\nEfficiency"]
    violations = compliance_report.get("violations", [])

    # Compute per-category scores (100% minus penalty)
    type_map = {"corridor_width": 0, "door_width": 1, "turning_space": 2, "ramp_gradient": 3, "bottleneck": 4}
    penalties = [0.0] * 5
    type_counts = [0] * 5
    for v in violations:
        idx = type_map.get(v.get("type", ""), 4)
        sev_penalty = {"critical": 25, "high": 15, "medium": 8, "low": 3}
        penalties[idx] += sev_penalty.get(v.get("severity", "medium"), 5)
        type_counts[idx] += 1

    scores = [max(0, min(100, 100 - p)) for p in penalties]

    # Add efficiency score
    eff = analytics.get("efficiency_score", {}).get("average", 0.8)
    scores[4] = max(0, min(100, eff * 100))

    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    scores_plot = scores + [scores[0]]
    angles += [angles[0]]

    fig, ax = plt.subplots(figsize=(5, 4), subplot_kw=dict(polar=True))
    ax.fill(angles, scores_plot, color="#06b6d4", alpha=0.25)
    ax.plot(angles, scores_plot, color="#06b6d4", linewidth=2)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100"], fontsize=7, color="#71717a")
    ax.set_title("Compliance Category Scores", fontsize=12, fontweight="bold", pad=20)
    fig.tight_layout()
    return _fig_to_image(fig, width=130 * mm, height=110 * mm)


def _heatmap_image(heatmap_data: dict) -> Image:
    """Full-page heatmap image."""
    grid = np.array(heatmap_data.get("grid", []))
    if grid.size == 0:
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.text(0.5, 0.5, "No heatmap data", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
        return _fig_to_image(fig, width=160 * mm, height=140 * mm)

    bounds = heatmap_data["bounds"]
    extent = [bounds["min_x"], bounds["max_x"], bounds["min_y"], bounds["max_y"]]

    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(grid, origin="lower", extent=extent, cmap="jet",
                   alpha=0.85, vmin=0, vmax=1, interpolation="bilinear")
    ax.set_xlabel("X (m)", fontsize=10)
    ax.set_ylabel("Y (m)", fontsize=10)
    ax.set_title("Pedestrian Density Heatmap", fontsize=13, fontweight="bold")
    cbar = plt.colorbar(im, ax=ax, label="Normalized Density", shrink=0.85)
    cbar.ax.tick_params(labelsize=8)
    fig.tight_layout()
    return _fig_to_image(fig, width=160 * mm, height=140 * mm)


# ---------------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Generates a multi-page PDF compliance audit report."""

    def __init__(
        self,
        compliance_report: dict,
        analytics_data: dict,
        building_type: str = "residential",
        floor_area: float = 0.0,
        ai_recommendations: dict | None = None,
    ) -> None:
        self._compliance = compliance_report
        self._analytics = analytics_data
        self._building_type = building_type
        self._floor_area = floor_area
        self._ai_recs = ai_recommendations or {}
        self._s = _styles()

    def generate(self, project_name: str = "Building Compliance Audit") -> str:
        """Generate the PDF and return the file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"archion_report_{timestamp}.pdf"
        filepath = REPORTS_DIR / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=25 * mm,
            bottomMargin=20 * mm,
        )

        story: list = []
        story += self._cover_page(project_name)
        story.append(PageBreak())
        story += self._executive_summary()
        story.append(PageBreak())
        story += self._building_info(project_name)
        story.append(PageBreak())
        story += self._compliance_analysis()
        story.append(PageBreak())
        story += self._compliance_breakdown()
        story.append(PageBreak())
        story += self._ai_recommendations_page()
        story.append(PageBreak())
        story += self._recommendations_summary()
        story.append(PageBreak())
        story += self._performance_metrics()
        story.append(PageBreak())
        story += self._heatmap_page()
        story.append(PageBreak())
        story += self._conclusion()
        story.append(PageBreak())
        story += self._appendix()

        doc.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
        print(f"[Report] PDF generated: {filename} (11 pages)")
        return str(filepath)

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------
    @staticmethod
    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(HexColor("#a1a1aa"))
        canvas.drawString(20 * mm, 10 * mm,
                          f"Archion Sim — Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        canvas.drawRightString(PAGE_W - 20 * mm, 10 * mm,
                               f"Page {doc.page}")
        canvas.restoreState()

    # ------------------------------------------------------------------
    # Page 1 — Cover
    # ------------------------------------------------------------------
    def _cover_page(self, project_name: str) -> list:
        elements: list = []
        elements.append(Spacer(1, 80 * mm))
        elements.append(Paragraph("ARCHION SIM", self._s["title"]))
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph("Building Compliance &amp; Analytics Report", self._s["subtitle"]))
        elements.append(Spacer(1, 20 * mm))
        elements.append(Paragraph(project_name, ParagraphStyle(
            "project", fontName="Helvetica-Bold", fontSize=14,
            alignment=TA_CENTER, textColor=CYAN,
        )))
        elements.append(Spacer(1, 10 * mm))

        score = self._compliance.get("compliance_score", 0)
        status = self._compliance.get("status", "fail").upper()
        color = GREEN if status == "PASS" else RED
        elements.append(Paragraph(
            f"Compliance Score: {score:.0f}% — {status}",
            ParagraphStyle("score", fontName="Helvetica-Bold", fontSize=16,
                           alignment=TA_CENTER, textColor=color),
        ))
        elements.append(Spacer(1, 10 * mm))

        meta_data = [
            ["Building Type", self._building_type.replace("_", " ").title()],
            ["Report Date", datetime.now().strftime("%B %d, %Y")],
            ["Floor Area", f"{self._floor_area:.1f} m²"],
        ]
        meta_table = Table(meta_data, colWidths=[60 * mm, 80 * mm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(meta_table)
        return elements

    # ------------------------------------------------------------------
    # Page 2 — Executive Summary
    # ------------------------------------------------------------------
    def _executive_summary(self) -> list:
        elements: list = []
        elements.append(Paragraph("Executive Summary", self._s["h1"]))
        elements.append(Spacer(1, 4 * mm))

        score = self._compliance.get("compliance_score", 0)
        status = self._compliance.get("status", "fail")
        summary = self._compliance.get("summary", {})
        total = self._compliance.get("total_violations", 0)

        # Score badge
        style_key = "badge_pass" if status == "pass" else "badge_fail"
        elements.append(Paragraph(
            f"Compliance Score: {score:.0f}% — {status.upper()}", self._s[style_key]
        ))
        elements.append(Spacer(1, 6 * mm))

        # Summary table
        cong = self._analytics.get("congestion_index", {})
        eff = self._analytics.get("efficiency_score", {})
        summ = self._analytics.get("summary", {})
        flow = self._analytics.get("flow_rate", [])
        avg_flow = sum(p["agents_per_minute"] for p in flow) / len(flow) if flow else 0

        data = [
            ["Metric", "Value"],
            ["Total Violations", str(total)],
            ["Critical", str(summary.get("critical", 0))],
            ["High", str(summary.get("high", 0))],
            ["Medium", str(summary.get("medium", 0))],
            ["Low", str(summary.get("low", 0))],
            ["Congestion Index", f"{cong.get('percentage', 0):.1f}%"],
            ["Efficiency Score", f"{eff.get('average', 0) * 100:.1f}%"],
            ["Avg Flow Rate", f"{avg_flow:.1f} agents/min"],
            ["Avg Velocity", f"{summ.get('avg_velocity_ms', 0):.2f} m/s"],
        ]

        t = Table(data, colWidths=[80 * mm, 80 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CYAN),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f4f4f5")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 8 * mm))

        # Key findings
        elements.append(Paragraph("Key Findings", self._s["h2"]))
        findings: list[str] = []
        if summary.get("critical", 0) > 0:
            findings.append(f"{summary['critical']} critical violation(s) requiring immediate attention.")
        if cong.get("percentage", 0) > 30:
            findings.append(f"High congestion index ({cong['percentage']:.1f}%) indicates circulation issues.")
        if eff.get("average", 1) < 0.6:
            findings.append(f"Low efficiency score ({eff['average'] * 100:.0f}%) suggests poor wayfinding.")
        if avg_flow < 2:
            findings.append("Low flow rate indicates potential exit capacity issues.")
        if not findings:
            findings.append("Building meets minimum compliance requirements.")

        for f in findings:
            elements.append(Paragraph(f"&#8226; {f}", self._s["body"]))
            elements.append(Spacer(1, 2 * mm))

        return elements

    # ------------------------------------------------------------------
    # Page 3 — Building Information
    # ------------------------------------------------------------------
    def _building_info(self, project_name: str) -> list:
        elements: list = []
        elements.append(Paragraph("Building Information", self._s["h1"]))
        elements.append(Spacer(1, 4 * mm))

        summ = self._analytics.get("summary", {})
        data = [
            ["Property", "Value"],
            ["Project Name", project_name],
            ["Building Type", self._building_type.replace("_", " ").title()],
            ["Floor Area", f"{self._floor_area:.1f} m²"],
            ["Compliance Standard", self._compliance.get("standard", "Sri Lankan Planning Regulations")],
            ["Total Agents", str(summ.get("total_agents", 0))],
            ["Simulation Duration", f"{summ.get('simulation_duration_sec', 0):.0f} seconds"],
            ["Frame Rate", "10 Hz"],
        ]

        t = Table(data, colWidths=[70 * mm, 90 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CYAN),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f4f4f5")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(t)
        return elements

    # ------------------------------------------------------------------
    # Page 4 — Compliance Analysis
    # ------------------------------------------------------------------
    def _compliance_analysis(self) -> list:
        elements: list = []
        elements.append(Paragraph("Compliance Analysis", self._s["h1"]))
        elements.append(Spacer(1, 4 * mm))

        violations = self._compliance.get("violations", [])

        if not violations:
            elements.append(Paragraph("No violations detected.", self._s["body"]))
            return elements

        # Violations table
        header = ["#", "Type", "Severity", "Measured", "Required", "Regulation"]
        rows = [header]
        for i, v in enumerate(violations[:15], 1):  # Cap at 15 rows
            rows.append([
                str(i),
                v.get("type", "").replace("_", " ").title(),
                v.get("severity", "").upper(),
                f"{v.get('measured_value', 0):.2f}",
                f"{v.get('required_value', 0):.2f}",
                v.get("regulation", "")[:40],
            ])

        col_widths = [10 * mm, 30 * mm, 20 * mm, 22 * mm, 22 * mm, 56 * mm]
        t = Table(rows, colWidths=col_widths)

        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), CYAN),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f4f4f5")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]

        # Color severity cells
        for ri, row in enumerate(rows[1:], 1):
            sev = row[2].lower()
            if sev in SEVERITY_COLORS:
                style_cmds.append(("TEXTCOLOR", (2, ri), (2, ri), SEVERITY_COLORS[sev]))
                style_cmds.append(("FONTNAME", (2, ri), (2, ri), "Helvetica-Bold"))

        t.setStyle(TableStyle(style_cmds))
        elements.append(t)
        elements.append(Spacer(1, 8 * mm))

        # Bar chart
        elements.append(Paragraph("Violation Distribution", self._s["h2"]))
        elements.append(Spacer(1, 2 * mm))
        elements.append(_violations_bar_chart(violations))

        return elements

    # ------------------------------------------------------------------
    # Page 5 — AI Recommendations
    # ------------------------------------------------------------------
    def _ai_recommendations_page(self) -> list:
        elements: list = []
        elements.append(Paragraph("AI-Powered Recommendations", self._s["h1"]))
        elements.append(Spacer(1, 4 * mm))

        violations = self._compliance.get("violations", [])

        if not self._ai_recs or not violations:
            elements.append(Paragraph(
                "AI recommendations were not generated for this report. "
                "Use the interactive dashboard to request per-violation recommendations.",
                self._s["body"],
            ))
            return elements

        elements.append(Paragraph(
            f"AI-generated remediation advice for {len(self._ai_recs)} violation(s), "
            f"powered by Gemini 2.0 Flash with domain-specific knowledge.",
            self._s["body"],
        ))
        elements.append(Spacer(1, 4 * mm))

        rec_title = ParagraphStyle(
            "rec_title", fontName="Helvetica-Bold", fontSize=10,
            leading=14, textColor=DARK,
        )
        rec_body = ParagraphStyle(
            "rec_body", fontName="Helvetica", fontSize=9,
            leading=12, textColor=DARK,
        )
        rec_label = ParagraphStyle(
            "rec_label", fontName="Helvetica-Bold", fontSize=9,
            leading=12, textColor=GRAY,
        )

        for v in violations:
            vid = v.get("id", "")
            rec = self._ai_recs.get(vid)
            if not rec:
                continue

            vtype = v.get("type", "unknown").replace("_", " ").title()
            sev = v.get("severity", "medium").upper()
            sev_color = SEVERITY_COLORS.get(v.get("severity", "medium"), GRAY)

            # Violation header
            elements.append(Paragraph(
                f'<font color="{sev_color.hexval()}">[{sev}]</font> {vtype} '
                f'— Measured: {v.get("measured_value", 0):.2f}m '
                f'(Required: {v.get("required_value", 0):.2f}m)',
                rec_title,
            ))
            elements.append(Spacer(1, 2 * mm))

            # Analysis
            analysis = rec.get("analysis", "")
            if analysis:
                elements.append(Paragraph("Analysis:", rec_label))
                elements.append(Paragraph(analysis[:500], rec_body))
                elements.append(Spacer(1, 2 * mm))

            # Solution
            solution = rec.get("solution", "")
            if solution:
                elements.append(Paragraph("Solution:", rec_label))
                elements.append(Paragraph(solution[:400], rec_body))
                elements.append(Spacer(1, 2 * mm))

            # Implementation steps
            steps = rec.get("implementation_steps", [])
            if steps:
                elements.append(Paragraph("Implementation Steps:", rec_label))
                for i, step in enumerate(steps[:6], 1):
                    elements.append(Paragraph(f"{i}. {step}", rec_body))
                elements.append(Spacer(1, 2 * mm))

            # Complexity & Cost row
            complexity = rec.get("complexity", "unknown").upper()
            cost = rec.get("estimated_cost", "")
            meta_parts = [f"Complexity: {complexity}"]
            if cost:
                meta_parts.append(f"Est. Cost: {cost}")
            elements.append(Paragraph(" | ".join(meta_parts), rec_label))
            elements.append(Spacer(1, 2 * mm))

            # Alternatives
            alts = rec.get("alternatives", [])
            if alts:
                elements.append(Paragraph("Alternatives:", rec_label))
                for alt in alts[:3]:
                    elements.append(Paragraph(f"&#8226; {alt}", rec_body))
                elements.append(Spacer(1, 1 * mm))

            # Separator line
            sep = Table([[""]], colWidths=[160 * mm])
            sep.setStyle(TableStyle([
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, LIGHT_GRAY),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            elements.append(sep)
            elements.append(Spacer(1, 3 * mm))

        return elements

    # ------------------------------------------------------------------
    # Page 5 — Compliance Breakdown (NEW)
    # ------------------------------------------------------------------
    def _compliance_breakdown(self) -> list:
        elements: list = []
        elements.append(Paragraph("Compliance Breakdown", self._s["h1"]))
        elements.append(Spacer(1, 4 * mm))

        violations = self._compliance.get("violations", [])

        # Radar chart — category scores
        elements.append(_compliance_radar_chart(self._compliance, self._analytics))
        elements.append(Spacer(1, 6 * mm))

        # Severity distribution pie chart
        elements.append(Paragraph("Severity Distribution", self._s["h2"]))
        elements.append(Spacer(1, 2 * mm))
        elements.append(_severity_pie_chart(violations))
        elements.append(Spacer(1, 4 * mm))

        # Per-category summary table
        elements.append(Paragraph("Category Summary", self._s["h2"]))
        type_stats: dict[str, dict] = {}
        for v in violations:
            vt = v.get("type", "unknown")
            if vt not in type_stats:
                type_stats[vt] = {"count": 0, "critical": 0, "high": 0}
            type_stats[vt]["count"] += 1
            sev = v.get("severity", "medium")
            if sev in ("critical", "high"):
                type_stats[vt][sev] = type_stats[vt].get(sev, 0) + 1

        rows = [["Category", "Total", "Critical", "High", "Status"]]
        for vt, stats in type_stats.items():
            status_text = "FAIL" if stats["critical"] > 0 else ("WARNING" if stats["high"] > 0 else "OK")
            rows.append([
                vt.replace("_", " ").title(),
                str(stats["count"]),
                str(stats["critical"]),
                str(stats["high"]),
                status_text,
            ])

        if len(rows) > 1:
            t = Table(rows, colWidths=[40 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm])
            style_cmds = [
                ("BACKGROUND", (0, 0), (-1, 0), CYAN),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f4f4f5")]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ]
            # Color status cells
            for ri, row in enumerate(rows[1:], 1):
                if row[4] == "FAIL":
                    style_cmds.append(("TEXTCOLOR", (4, ri), (4, ri), RED))
                    style_cmds.append(("FONTNAME", (4, ri), (4, ri), "Helvetica-Bold"))
                elif row[4] == "WARNING":
                    style_cmds.append(("TEXTCOLOR", (4, ri), (4, ri), ORANGE))
                    style_cmds.append(("FONTNAME", (4, ri), (4, ri), "Helvetica-Bold"))
                else:
                    style_cmds.append(("TEXTCOLOR", (4, ri), (4, ri), GREEN))
            t.setStyle(TableStyle(style_cmds))
            elements.append(t)

        return elements

    # ------------------------------------------------------------------
    # Page 7 — Recommendations Summary (NEW)
    # ------------------------------------------------------------------
    def _recommendations_summary(self) -> list:
        elements: list = []
        elements.append(Paragraph("Recommendations Summary", self._s["h1"]))
        elements.append(Spacer(1, 4 * mm))

        violations = self._compliance.get("violations", [])

        if not self._ai_recs:
            elements.append(Paragraph(
                "AI recommendations were not available for this report.",
                self._s["body"],
            ))
            elements.append(Spacer(1, 8 * mm))
        else:
            elements.append(Paragraph(
                f"Summary of {len(self._ai_recs)} AI-generated remediation recommendations:",
                self._s["body"],
            ))
            elements.append(Spacer(1, 4 * mm))

            # Condensed table of all recommendations
            rows = [["Violation", "Severity", "Solution Summary", "Complexity", "Est. Cost"]]
            for v in violations:
                rec = self._ai_recs.get(v.get("id", ""))
                if not rec:
                    continue
                vtype = v.get("type", "").replace("_", " ").title()
                sev = v.get("severity", "medium").upper()
                solution = rec.get("solution", "N/A")[:80]
                if len(rec.get("solution", "")) > 80:
                    solution += "..."
                complexity = rec.get("complexity", "unknown").title()
                cost = rec.get("estimated_cost", "N/A")
                rows.append([vtype, sev, solution, complexity, str(cost)])

            if len(rows) > 1:
                t = Table(rows, colWidths=[28 * mm, 18 * mm, 70 * mm, 22 * mm, 22 * mm])
                style_cmds = [
                    ("BACKGROUND", (0, 0), (-1, 0), CYAN),
                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f4f4f5")]),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
                t.setStyle(TableStyle(style_cmds))
                elements.append(t)
                elements.append(Spacer(1, 6 * mm))

        # Priority action items
        elements.append(Paragraph("Priority Action Items", self._s["h2"]))
        elements.append(Spacer(1, 2 * mm))

        summary = self._compliance.get("summary", {})
        priority_items = []
        if summary.get("critical", 0) > 0:
            priority_items.append(
                f"<b>IMMEDIATE:</b> Address {summary['critical']} critical violation(s) — "
                f"these represent life-safety non-compliance issues."
            )
        if summary.get("high", 0) > 0:
            priority_items.append(
                f"<b>HIGH PRIORITY:</b> Remediate {summary['high']} high-severity violation(s) "
                f"before occupancy certificate application."
            )
        if summary.get("medium", 0) > 0:
            priority_items.append(
                f"<b>RECOMMENDED:</b> Address {summary['medium']} medium-severity issue(s) "
                f"to improve overall compliance score."
            )
        if summary.get("low", 0) > 0:
            priority_items.append(
                f"<b>OPTIONAL:</b> {summary['low']} low-severity advisory note(s) for best-practice compliance."
            )
        if not priority_items:
            priority_items.append("No remediation actions required — building is fully compliant.")

        for item in priority_items:
            elements.append(Paragraph(f"&#8226; {item}", self._s["body"]))
            elements.append(Spacer(1, 2 * mm))

        # Cost estimation summary
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph("Estimated Remediation Effort", self._s["h2"]))
        elements.append(Spacer(1, 2 * mm))

        total_simple = sum(1 for r in self._ai_recs.values() if r.get("complexity", "").lower() in ("low", "simple"))
        total_moderate = sum(1 for r in self._ai_recs.values() if r.get("complexity", "").lower() in ("moderate", "medium"))
        total_complex = sum(1 for r in self._ai_recs.values() if r.get("complexity", "").lower() in ("high", "complex"))

        effort_data = [
            ["Complexity", "Count", "Typical Timeline"],
            ["Simple", str(total_simple), "1-2 weeks"],
            ["Moderate", str(total_moderate), "2-4 weeks"],
            ["Complex", str(total_complex), "4-8 weeks"],
        ]
        t = Table(effort_data, colWidths=[40 * mm, 30 * mm, 50 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CYAN),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)

        return elements

    # ------------------------------------------------------------------
    # Page 8 — Performance Metrics
    # ------------------------------------------------------------------
    def _performance_metrics(self) -> list:
        elements: list = []
        elements.append(Paragraph("Performance Metrics", self._s["h1"]))
        elements.append(Spacer(1, 4 * mm))

        # Velocity chart
        vel_tl = self._analytics.get("velocity_timeline", [])
        elements.append(_velocity_chart(vel_tl))
        elements.append(Spacer(1, 4 * mm))

        # Flow rate chart
        flow = self._analytics.get("flow_rate", [])
        elements.append(_flow_rate_chart(flow))
        elements.append(Spacer(1, 4 * mm))

        # Metrics table
        summ = self._analytics.get("summary", {})
        cong = self._analytics.get("congestion_index", {})
        eff = self._analytics.get("efficiency_score", {})

        data = [
            ["Metric", "Value"],
            ["Average Velocity", f"{summ.get('avg_velocity_ms', 0):.2f} m/s"],
            ["Peak Congestion", f"{summ.get('peak_congestion_pct', 0):.1f}%"],
            ["Congestion Index", f"{cong.get('percentage', 0):.1f}%"],
            ["Path Efficiency", f"{eff.get('average', 0) * 100:.1f}%"],
            ["Total Distance (all agents)", f"{summ.get('total_distance_m', 0):.0f} m"],
        ]
        t = Table(data, colWidths=[80 * mm, 80 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CYAN),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(t)

        return elements

    # ------------------------------------------------------------------
    # Page 7 — Heatmap
    # ------------------------------------------------------------------
    def _heatmap_page(self) -> list:
        elements: list = []
        elements.append(Paragraph("Density Heatmap", self._s["h1"]))
        elements.append(Spacer(1, 4 * mm))

        heatmap = self._analytics.get("density_heatmap", {})
        elements.append(_heatmap_image(heatmap))
        elements.append(Spacer(1, 3 * mm))

        max_density = heatmap.get("max_density", 0)
        res = heatmap.get("resolution", 0.5)
        shape = heatmap.get("shape", [0, 0])
        elements.append(Paragraph(
            f"Grid resolution: {res}m | Grid size: {shape[1]}x{shape[0]} | "
            f"Peak density: {max_density:.0f} agent-frames per cell",
            self._s["caption"],
        ))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(
            "Red zones indicate high pedestrian density and potential bottleneck areas. "
            "Blue zones show low-traffic areas. The heatmap aggregates agent positions "
            "across the entire simulation duration.",
            self._s["body"],
        ))

        return elements

    # ------------------------------------------------------------------
    # Page 8 — Conclusion
    # ------------------------------------------------------------------
    def _conclusion(self) -> list:
        elements: list = []
        elements.append(Paragraph("Conclusion &amp; Next Steps", self._s["h1"]))
        elements.append(Spacer(1, 4 * mm))

        score = self._compliance.get("compliance_score", 0)
        status = self._compliance.get("status", "fail")
        total = self._compliance.get("total_violations", 0)
        summary = self._compliance.get("summary", {})

        if status == "pass":
            verdict = (
                f"The building achieves a compliance score of {score:.0f}%, meeting the "
                f"minimum threshold for {self._building_type.replace('_', ' ')} buildings "
                f"under Sri Lankan Planning and Development Regulations."
            )
        else:
            verdict = (
                f"The building scores {score:.0f}%, falling below the required compliance "
                f"threshold. {total} violation(s) were detected, including "
                f"{summary.get('critical', 0)} critical and {summary.get('high', 0)} high "
                f"severity issues requiring remediation."
            )

        elements.append(Paragraph(verdict, self._s["body"]))
        elements.append(Spacer(1, 6 * mm))

        elements.append(Paragraph("Recommended Next Steps", self._s["h2"]))
        steps = [
            "Address all critical violations as highest priority",
            "Engage a licensed structural engineer for detailed design modifications",
            "Submit revised floor plans to UDA for approval",
            "Obtain fire safety clearance for any corridor or exit changes",
            "Re-run simulation after modifications to verify compliance",
            "Obtain Certificate of Conformity (COC) from local authority",
        ]
        for s in steps:
            elements.append(Paragraph(f"&#8226; {s}", self._s["body"]))
            elements.append(Spacer(1, 1.5 * mm))

        elements.append(Spacer(1, 10 * mm))
        elements.append(Paragraph(
            f"Report generated on {datetime.now().strftime('%B %d, %Y at %H:%M')} "
            f"by Archion Sim v1.0",
            self._s["caption"],
        ))

        return elements

    # ------------------------------------------------------------------
    # Page 11 — Appendix
    # ------------------------------------------------------------------
    def _appendix(self) -> list:
        elements: list = []
        elements.append(Paragraph("Appendix: Methodology &amp; Standards", self._s["h1"]))
        elements.append(Spacer(1, 6 * mm))

        elements.append(Paragraph("Simulation Methodology", self._s["h2"]))
        elements.append(Spacer(1, 2 * mm))
        methodology = [
            "Agent-based pedestrian simulation using a Social Force Model (SFM) to replicate "
            "realistic crowd dynamics within the building floor plan.",
            "Agents are initialized at random interior positions and navigate toward the nearest exit "
            "using A* pathfinding on a discretized navigation mesh.",
            "Social forces include: desired velocity force, agent-agent repulsion, "
            "wall repulsion, and obstacle avoidance.",
            "Simulation runs at 10 Hz (100ms timestep) for 60 seconds of simulated time, "
            "producing 600 frames of trajectory data.",
        ]
        for m in methodology:
            elements.append(Paragraph(f"&#8226; {m}", self._s["body"]))
            elements.append(Spacer(1, 1.5 * mm))

        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph("Compliance Standards Reference", self._s["h2"]))
        elements.append(Spacer(1, 2 * mm))

        standards = [
            ["Standard", "Description"],
            ["SL Planning Regs", "Sri Lankan Planning and Development Regulations"],
            ["NBC SL 2012", "National Building Code of Sri Lanka"],
            ["NFPA 101", "Life Safety Code (Fire egress requirements)"],
            ["ADA / DDA", "Accessibility design standards (corridor width, ramp gradient)"],
        ]
        t = Table(standards, colWidths=[40 * mm, 120 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CYAN),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f4f4f5")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)

        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph("Violation Severity Definitions", self._s["h2"]))
        elements.append(Spacer(1, 2 * mm))

        sev_defs = [
            ["Severity", "Definition", "Action Required"],
            ["Critical", "Life-safety risk or major code violation", "Immediate remediation"],
            ["High", "Significant non-compliance affecting usability", "Remediate before occupancy"],
            ["Medium", "Moderate non-compliance, reduced accessibility", "Recommended fix"],
            ["Low", "Minor advisory, best-practice recommendation", "Optional improvement"],
        ]
        t = Table(sev_defs, colWidths=[25 * mm, 75 * mm, 60 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), CYAN),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f4f4f5")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)

        elements.append(Spacer(1, 8 * mm))
        elements.append(Paragraph("Disclaimer", self._s["h2"]))
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(
            "This report is generated by automated simulation software and is intended "
            "for preliminary assessment purposes only. It does not replace professional "
            "engineering review or regulatory approval. All measurements and recommendations "
            "should be verified by a licensed architect or structural engineer before "
            "implementation. Archion Sim is not responsible for design decisions made "
            "based solely on this report.",
            self._s["body"],
        ))

        return elements
