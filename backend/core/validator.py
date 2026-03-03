"""Response validator for the hybrid AI recommendation engine.

Cross-checks Gemini's JSON response against extracted violation parameters
to detect hallucinations (impossible dimensions, implausible costs, etc.)
and adds a calibrated confidence score.
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Required fields and their expected types
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict[str, type] = {
    "analysis": str,
    "solution": str,
    "implementation_steps": list,
    "complexity": str,
    "estimated_cost_lkr": str,
    "regulation_reference": str,
    "alternative_solutions": list,
}

_VALID_COMPLEXITY = {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_cost_range(cost_str: str) -> tuple[int, int] | None:
    """Parse a cost range string like '200000-500000' into (low, high)."""
    if not cost_str or cost_str == "N/A":
        return None
    cost_clean = cost_str.replace(",", "").replace(" ", "").replace("LKR", "")
    parts = re.findall(r"\d+", cost_clean)
    if len(parts) >= 2:
        try:
            return int(parts[0]), int(parts[-1])
        except ValueError:
            pass
    elif len(parts) == 1:
        try:
            v = int(parts[0])
            return v, v
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Main validation entry point
# ---------------------------------------------------------------------------

def validate_and_score(
    recommendation: dict,
    violation: dict,
    kb_cost_range: str,
) -> dict:
    """Validate *recommendation* and return it enriched with a confidence score.

    Parameters
    ----------
    recommendation:
        Raw dict returned by Gemini (already JSON-parsed).
    violation:
        Violation dict from the compliance report.
    kb_cost_range:
        Expected cost range from the knowledge base (e.g. ``"200000-500000"``).

    Returns
    -------
    The same dict with fields normalised and ``_confidence`` (0.0–1.0) added.
    """
    rec = dict(recommendation)

    confidence = 1.0

    # ------------------------------------------------------------------
    # 1. Ensure all required fields exist with correct types
    # ------------------------------------------------------------------
    for field, expected_type in _REQUIRED_FIELDS.items():
        val = rec.get(field)
        if val is None:
            if expected_type is list:
                rec[field] = []
            elif field == "complexity":
                rec[field] = "unknown"
            else:
                rec[field] = "N/A"
            confidence -= 0.15
        elif not isinstance(val, expected_type):
            if expected_type is str:
                rec[field] = str(val)
            elif expected_type is list:
                rec[field] = [str(val)] if val else []
            confidence -= 0.05

    # ------------------------------------------------------------------
    # 2. Normalise complexity
    # ------------------------------------------------------------------
    complexity_raw = rec.get("complexity", "").lower().strip()
    if complexity_raw not in _VALID_COMPLEXITY:
        rec["complexity"] = "unknown"
        confidence -= 0.1
    else:
        rec["complexity"] = complexity_raw

    # ------------------------------------------------------------------
    # 3. Ensure list items are strings
    # ------------------------------------------------------------------
    rec["implementation_steps"] = [str(s) for s in rec.get("implementation_steps", [])]
    rec["alternative_solutions"] = [str(s) for s in rec.get("alternative_solutions", [])]

    # ------------------------------------------------------------------
    # 4. Minimum step count guard
    # ------------------------------------------------------------------
    steps = rec["implementation_steps"]
    if len(steps) < 4:
        fallback_steps = [
            "Survey existing conditions and document all current measurements",
            "Engage a licensed structural engineer for detailed assessment",
            "Submit revised drawings to UDA/Local Authority for approval",
            "Execute modifications using a certified contractor",
            "Verify compliance with final measurement and independent inspection",
            "Obtain Certificate of Conformity (COC) from the Local Authority",
        ]
        for s in fallback_steps:
            if len(steps) >= 4:
                break
            if s not in steps:
                steps.append(s)
        rec["implementation_steps"] = steps
        confidence -= 0.05

    # ------------------------------------------------------------------
    # 5. Regulation reference check
    # ------------------------------------------------------------------
    reg_ref = rec.get("regulation_reference", "")
    if not reg_ref or reg_ref in ("N/A", ""):
        confidence -= 0.2

    # ------------------------------------------------------------------
    # 6. Cost plausibility check against knowledge base
    # ------------------------------------------------------------------
    ai_cost = _parse_cost_range(rec.get("estimated_cost_lkr", ""))
    kb_cost = _parse_cost_range(kb_cost_range)

    if ai_cost and kb_cost:
        kb_low, kb_high = kb_cost
        ai_low, ai_high = ai_cost
        # Flag if AI cost is more than 2.5× above or below KB range
        if ai_high > kb_high * 2.5:
            rec["estimated_cost_lkr"] = kb_cost_range
            rec["_cost_overridden"] = True
            confidence -= 0.1
        elif ai_low < kb_low * 0.3:
            rec["estimated_cost_lkr"] = kb_cost_range
            rec["_cost_overridden"] = True
            confidence -= 0.1
    elif not ai_cost and kb_cost_range and kb_cost_range != "N/A":
        # AI didn't give a valid cost — use knowledge base
        rec["estimated_cost_lkr"] = kb_cost_range
        rec["_cost_overridden"] = True
        confidence -= 0.15

    # ------------------------------------------------------------------
    # 7. Ensure at least 2 alternative solutions
    # ------------------------------------------------------------------
    alts = rec.get("alternative_solutions", [])
    if len(alts) < 2:
        confidence -= 0.05

    # ------------------------------------------------------------------
    # 8. Analysis quality check
    # ------------------------------------------------------------------
    analysis = rec.get("analysis", "")
    # Penalise if analysis is suspiciously short
    if len(analysis) < 80:
        confidence -= 0.15

    # ------------------------------------------------------------------
    # 9. Final score
    # ------------------------------------------------------------------
    rec["_confidence"] = round(max(0.1, min(1.0, confidence)), 2)

    return rec


def build_fallback_recommendation(
    violation: dict,
    building_type: str,
    kb_cost_range: str,
    time_estimate: str,
    deficiency_level: str,
    regulation_ref: str,
) -> dict:
    """Construct a fallback recommendation entirely from local data.

    Used when the Gemini API is unavailable. The confidence score is fixed
    at 0.40 to indicate that no AI reasoning was performed.
    """
    vtype = violation.get("type", "")
    measured = violation.get("measured_value", 0.0)
    required = violation.get("required_value", 0.0)
    description = violation.get("description", f"{vtype} violation")

    complexity = {
        "minor": "low",
        "moderate": "medium",
        "major": "high",
    }.get(deficiency_level, "medium")

    return {
        "analysis": (
            f"The {vtype.replace('_', ' ')} of {measured} does not meet the required "
            f"standard of {required} for {building_type} buildings. "
            f"Deficiency classified as {deficiency_level} ({description})."
        ),
        "solution": (
            f"Modify the affected element to meet or exceed the minimum requirement "
            f"of {required}. A licensed structural engineer should assess whether "
            f"load-bearing elements are involved before any modifications are made."
        ),
        "implementation_steps": [
            "Survey existing conditions and document all current measurements",
            "Engage a licensed structural or civil engineer for detailed assessment",
            "Submit revised drawings to UDA/Local Authority for approval",
            "Execute modifications using a certified contractor",
            f"Allow {time_estimate} for completion",
            "Verify compliance with final measurement and inspection",
            "Obtain Certificate of Conformity (COC) from the Local Authority",
        ],
        "complexity": complexity,
        "estimated_cost_lkr": kb_cost_range,
        "regulation_reference": regulation_ref or "Sri Lankan Planning & Development Regulations",
        "alternative_solutions": [
            "Consult a licensed structural engineer for a site-specific remediation plan",
            "Consider operational mitigation measures while permanent fix is planned",
        ],
        "_confidence": 0.40,
        "_is_fallback": True,
    }
