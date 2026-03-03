"""Parameter extraction for the hybrid AI recommendation engine.

Assembles a complete ``ViolationParameters`` struct from:
- Violation data (type, measured value, required value, severity)
- Spatial analysis (nearby walls, available space, structural risk)
- Regulatory knowledge (citations, safety impact)
- Cost / time estimates (from knowledge base)

The resulting struct is passed verbatim to Gemini as grounding data.
Gemini receives *facts*, not solutions — it reasons from first principles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import Polygon

from core.knowledge_base import (
    classify_deficiency_level,
    format_construction_context,
    format_regulation_block,
    get_cost_range,
    get_regulation_context,
    get_safety_impact,
    get_time_estimate,
)
from core.spatial_analyzer import (
    SpatialContext,
    analyze_spatial_context,
    format_spatial_context_for_prompt,
)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class ViolationParameters:
    """Complete parameter set for a single violation.

    All fields are plain Python scalars / lists / dicts so that
    ``to_prompt_sections()`` can format them without further computation.
    """

    # --- Core ---
    violation_id: str
    violation_type: str
    severity: str
    building_type: str
    floor_area_m2: float

    # --- Measurements ---
    measured_value: float
    required_value: float
    gap_m: float          # how far below minimum (or above maximum)
    gap_pct: float        # percentage gap
    deficiency_level: str  # "minor" | "moderate" | "major"

    # --- Regulatory ---
    regulation_reference: str
    iso_clause: str
    regulation_context: str
    recommended_value: float   # not just minimum

    # --- Safety ---
    safety_level: str
    safety_description: str
    affected_populations: list[str]
    failure_consequence: str

    # --- Spatial (from spatial_analyzer) ---
    spatial_ctx: SpatialContext

    # --- Costs / times ---
    cost_range_lkr: str
    remediation_time: str

    def to_prompt_sections(self) -> str:
        """Return compact parameter sections for the Gemini prompt."""
        lines: list[str] = []

        # Header
        lines += [
            f"Building: {self.building_type} | Floor area: {self.floor_area_m2:.1f} m² | "
            f"Severity: {self.severity.upper()}",
            f"Violation: {self.violation_type} | "
            f"Measured: {self.measured_value} | Required: {self.required_value} | "
            f"Recommended: {self.recommended_value}",
            f"Gap: {self.gap_m:.3f}m ({self.gap_pct:.1f}%) | "
            f"Deficiency: {self.deficiency_level.upper()} (minor≤15% / moderate≤35% / major>35%)",
            f"Cost range (LKR): {self.cost_range_lkr} | Time: {self.remediation_time}",
            "",
        ]

        # Regulatory block (compact)
        lines += [format_regulation_block(self.violation_type, self.building_type), ""]

        # Construction context (compact)
        lines += [format_construction_context(), ""]

        # Spatial analysis (compact)
        lines += [format_spatial_context_for_prompt(self.spatial_ctx), ""]

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def extract_parameters(
    violation: dict,
    building_type: str,
    floor_area_m2: float,
    wall_segments: list[list[float]],
    boundary_polygon: Polygon,
) -> ViolationParameters:
    """Build a ViolationParameters instance from raw violation + geometry data.

    Parameters
    ----------
    violation:
        Violation dict from the compliance report (must contain ``type``,
        ``measured_value``, ``required_value``, ``severity``, ``coordinate``).
    building_type:
        The building type string (e.g. ``"residential"``).
    floor_area_m2:
        Total walkable floor area.
    wall_segments:
        Raw ``[x1, y1, x2, y2]`` wall segments from the geometry pipeline.
    boundary_polygon:
        Shapely Polygon of the walkable floor boundary.
    """
    vtype = violation.get("type", "")
    measured = float(violation.get("measured_value", 0.0))
    required = float(violation.get("required_value", 0.0))
    severity = violation.get("severity", "medium")

    # Deficiency
    deficiency_level = classify_deficiency_level(measured, required, vtype)
    gap_m = abs(measured - required)
    gap_pct = (gap_m / required * 100) if required > 0 else 0.0

    # Regulation
    reg = get_regulation_context(vtype, building_type)
    safety = get_safety_impact(vtype)

    # Cost / time
    cost_range = get_cost_range(vtype, deficiency_level)
    time_est = get_time_estimate(vtype, deficiency_level)

    # Spatial analysis (may fail gracefully if geometry is poor)
    try:
        spatial_ctx = analyze_spatial_context(
            wall_segments=wall_segments,
            violation=violation,
            boundary_polygon=boundary_polygon,
            required_value=required,
        )
    except Exception as exc:
        print(f"[ParameterExtractor] Spatial analysis failed: {exc}")
        # Minimal context so we can still generate a recommendation
        from core.spatial_analyzer import (
            SpatialContext,
            WallRelocationFeasibility,
        )
        spatial_ctx = SpatialContext(
            violation_coord=(0.0, 0.0),
            nearby_walls=[],
            available_corridor_width_m=measured,
            required_width_m=required,
            gap_to_close_m=gap_m,
            gap_pct=gap_pct,
            relocation=WallRelocationFeasibility(
                can_relocate=False,
                required_shift_m=gap_m,
                available_space_m=0.0,
                obstruction_present=True,
                preferred_wall_index=-1,
                confidence=0.3,
            ),
            structural_risk="unknown",
            structural_indicators=[],
            adjacent_space_estimate_m2=0.0,
        )

    # Recommended value (not just minimum)
    recommended_value = reg.get(
        "recommended_m",
        reg.get("recommended_diameter_m", required),
    ) or required

    return ViolationParameters(
        violation_id=violation.get("id", ""),
        violation_type=vtype,
        severity=severity,
        building_type=building_type,
        floor_area_m2=floor_area_m2,

        measured_value=measured,
        required_value=required,
        gap_m=round(gap_m, 3),
        gap_pct=round(gap_pct, 1),
        deficiency_level=deficiency_level,

        regulation_reference=(
            reg.get("reference") or violation.get("regulation", "N/A")
        ),
        iso_clause=reg.get("iso_clause", ""),
        regulation_context=reg.get("context", ""),
        recommended_value=recommended_value,

        safety_level=safety.get("level", "medium"),
        safety_description=safety.get("description", ""),
        affected_populations=safety.get("affected_populations", []),
        failure_consequence=safety.get("failure_consequence", ""),

        spatial_ctx=spatial_ctx,

        cost_range_lkr=cost_range,
        remediation_time=time_est,
    )
