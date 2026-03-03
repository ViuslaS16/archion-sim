"""Domain knowledge base for the hybrid AI recommendation engine.

Provides:
- Sri Lankan UDA + ISO 21542 regulatory citations per violation type / building type
- Safety impact classifications
- Cost data ranges in LKR (used to validate AI estimates)
- Remediation time estimates (used to validate AI estimates)
- Construction context (materials, labour rates, approval process)

Design principle: this module supplies *facts* (regulations, costs, safety data).
It deliberately does NOT contain pre-written solution text — Gemini reasons
from the extracted spatial parameters and produces original analysis.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Regulatory citations per violation type, keyed by building type
# ---------------------------------------------------------------------------

REGULATIONS: dict[str, dict[str, dict]] = {
    "corridor_width": {
        "residential": {
            "minimum_m": 1.2,
            "recommended_m": 1.5,
            "reference": "UDA Planning Regulation Section 3.2.1",
            "iso_clause": "ISO 21542:2011 Clause 13",
            "context": (
                "Residential corridors must provide a clear path for wheelchair "
                "passage (ISO 21542 requires 0.8m minimum clear width) with "
                "manoeuvring clearance on both sides. The 1.2m minimum ensures "
                "a wheelchair user and a pedestrian can pass without contact."
            ),
        },
        "public_buildings": {
            "minimum_m": 1.5,
            "recommended_m": 2.0,
            "reference": "UDA Planning Regulation Section 4.1.3",
            "iso_clause": "ISO 21542:2011 Clause 13",
            "context": (
                "Public building main corridors must allow two wheelchairs to pass "
                "simultaneously (2 × 0.8m = 1.6m, rounded to 2.0m recommended). "
                "The 1.5m minimum enables a wheelchair plus a walking person."
            ),
        },
        "hospital": {
            "minimum_m": 2.0,
            "recommended_m": 2.4,
            "reference": "UDA Planning Regulation Section 5.2.1",
            "iso_clause": "ISO 21542:2011 Clause 13",
            "context": (
                "Hospital corridors must accommodate gurney/bed transport (bed "
                "width ≈ 0.9m) with lateral clearance for passing persons. "
                "Critical-care and surgical-ward corridors require 2.4m."
            ),
        },
        "educational": {
            "minimum_m": 1.8,
            "recommended_m": 2.4,
            "reference": "UDA Planning Regulation Section 4.3.2",
            "iso_clause": "ISO 21542:2011 Clause 13",
            "context": (
                "School corridors must handle simultaneous multi-directional "
                "student movement during class transitions. 2.4m is required "
                "for main corridors connecting classrooms."
            ),
        },
        "commercial": {
            "minimum_m": 1.5,
            "recommended_m": 3.0,
            "reference": "UDA Planning Regulation Section 4.2.1",
            "iso_clause": "ISO 21542:2011 Clause 13",
            "context": (
                "Retail corridors require 3.0m for comfortable bidirectional "
                "pedestrian flow with shopfront displays. Emergency egress "
                "corridors must maintain 1.5m minimum clear width."
            ),
        },
        "industrial": {
            "minimum_m": 1.5,
            "recommended_m": 2.4,
            "reference": "UDA Planning Regulation Section 6.1.2",
            "iso_clause": "ISO 21542:2011 Clause 13",
            "context": (
                "Industrial main aisles must allow safe simultaneous passage of "
                "personnel and material-handling equipment. 2.4m is the practical "
                "minimum where small vehicles or trolleys operate."
            ),
        },
    },

    "door_width": {
        "residential": {
            "minimum_m": 0.75,
            "recommended_m": 0.9,
            "reference": "UDA Planning Regulation Section 3.2.2",
            "iso_clause": "ISO 21542:2011 Clause 15",
            "context": (
                "Residential doors must admit a standard wheelchair (0.8m). "
                "Clear opening width is measured at 90° door-open position. "
                "0.9m is recommended for furniture movement and comfort."
            ),
        },
        "public_buildings": {
            "minimum_m": 0.9,
            "recommended_m": 1.2,
            "reference": "UDA Planning Regulation Section 4.1.4",
            "iso_clause": "ISO 21542:2011 Clause 15",
            "context": (
                "All public building doors require 0.9m clear opening. Emergency "
                "exit doors and main entrance doors require 1.2m. Double-leaf doors "
                "must provide 0.9m from at least one active leaf."
            ),
        },
        "hospital": {
            "minimum_m": 1.1,
            "recommended_m": 1.2,
            "reference": "UDA Planning Regulation Section 5.2.2",
            "iso_clause": "ISO 21542:2011 Clause 15",
            "context": (
                "Hospital patient-room doors must admit a standard hospital bed "
                "(≈ 0.9m wide). 1.1m minimum clear width provides essential "
                "manoeuvring clearance. Operating theatre doors require 1.5m."
            ),
        },
        "educational": {
            "minimum_m": 1.0,
            "recommended_m": 1.2,
            "reference": "UDA Planning Regulation Section 4.3.3",
            "iso_clause": "ISO 21542:2011 Clause 15",
            "context": (
                "Classroom doors must enable rapid emergency egress. 1.2m is "
                "recommended for rooms with occupancy above 30 persons. Doors "
                "must swing in the direction of egress travel."
            ),
        },
        "commercial": {
            "minimum_m": 0.9,
            "recommended_m": 1.2,
            "reference": "UDA Planning Regulation Section 4.2.2",
            "iso_clause": "ISO 21542:2011 Clause 15",
            "context": (
                "Shop entrance doors require 1.2m for shopping trolley/cart access "
                "and accessibility compliance. Minimum 0.9m clear opening applies "
                "to internal doors and service areas."
            ),
        },
        "industrial": {
            "minimum_m": 1.0,
            "recommended_m": 1.2,
            "reference": "UDA Planning Regulation Section 6.1.3",
            "iso_clause": "ISO 21542:2011 Clause 15",
            "context": (
                "Industrial doors must allow emergency evacuation and basic "
                "equipment passage. Loading dock doors are sized separately "
                "(3.0m minimum) and are not covered by this regulation."
            ),
        },
    },

    "ramp_gradient": {
        "standard": {
            "maximum": 0.083,
            "ratio": "1:12",
            "reference": "UDA Planning Regulation Section 7.1",
            "iso_clause": "ISO 21542:2011 Clause 10",
            "context": (
                "1:12 (8.3%) is the maximum gradient for wheelchair-accessible "
                "ramps in all non-hospital buildings. A ramp landing of at least "
                "1.5m is required every 9m of ramp run. Handrails are mandatory "
                "on both sides at 900mm height."
            ),
        },
        "hospital": {
            "maximum": 0.05,
            "ratio": "1:20",
            "reference": "UDA Planning Regulation Section 5.3.1",
            "iso_clause": "ISO 21542:2011 Clause 10",
            "context": (
                "Hospital ramps must use a gentler 1:20 (5%) gradient to ensure "
                "controlled movement of beds, gurneys, and patients in wheelchairs. "
                "This doubles the ramp run length compared to the standard 1:12."
            ),
        },
        "residential": {
            "maximum": 0.083,
            "ratio": "1:12",
            "reference": "UDA Planning Regulation Section 7.1",
            "iso_clause": "ISO 21542:2011 Clause 10",
            "context": (
                "Residential ramps serving accessible entrances must not exceed "
                "1:12. Shorter ramps up to 0.3m height may use 1:10 under "
                "Section 7.1.3 (temporary dispensation)."
            ),
        },
    },

    "turning_space": {
        "standard": {
            "minimum_diameter_m": 1.5,
            "recommended_diameter_m": 1.8,
            "reference": "ISO 21542:2011 Section 4.5",
            "context": (
                "A 1.5m diameter clear circle is required at every corridor "
                "terminus and direction-change point for standard wheelchair "
                "turning. 1.8m is required for powered wheelchairs."
            ),
        },
        "hospital": {
            "minimum_diameter_m": 2.0,
            "reference": "UDA Planning Regulation Section 5.2.3",
            "iso_clause": "ISO 21542:2011 Section 4.5",
            "context": (
                "Hospital turning areas must accommodate hospital-bed turning "
                "(bed length ≈ 2.0m). A 2.0m diameter turning circle is the "
                "minimum at all ward corridor junctions."
            ),
        },
    },

    "bottleneck": {
        "standard": {
            "max_density": 2.0,
            "reference": "UDA Emergency Egress Standards",
            "iso_clause": "Fire Safety Code Section 8.2",
            "context": (
                "Pedestrian crowd density above 2.0 persons/m² significantly "
                "increases evacuation time and pedestrian conflict. Sustained "
                "density above 4.0 persons/m² creates stampede risk."
            ),
        },
        "hospital": {
            "max_density": 1.0,
            "reference": "UDA Emergency Egress Standards / Hospital Safety",
            "context": (
                "Hospital corridors must maintain low density to allow emergency "
                "equipment movement and patient evacuation. 1.0 persons/m² "
                "prevents corridor congestion during emergencies."
            ),
        },
        "educational": {
            "max_density": 2.5,
            "reference": "UDA Emergency Egress Standards",
            "context": (
                "Educational buildings experience density spikes during class "
                "changeovers. 2.5 persons/m² is the operational maximum; "
                "corridor widths must be designed for peak class-change flow."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Safety impact classification
# ---------------------------------------------------------------------------

SAFETY_IMPACT: dict[str, dict] = {
    "corridor_width": {
        "level": "high",
        "description": (
            "Directly restricts emergency evacuation flow rate and denies "
            "wheelchair access to persons with mobility impairments"
        ),
        "affected_populations": ["wheelchair users", "stretcher patients", "emergency evacuees"],
        "failure_consequence": (
            "Blocked evacuation route during fire or emergency, with potential "
            "for crowd crush at the narrowing; wheelchair users unable to self-evacuate"
        ),
    },
    "door_width": {
        "level": "high",
        "description": (
            "Prevents wheelchair access to rooms and reduces emergency egress flow rate"
        ),
        "affected_populations": ["wheelchair users", "mobility-impaired persons", "emergency evacuees"],
        "failure_consequence": (
            "Inaccessible rooms for wheelchair users; reduced egress capacity "
            "during fire leading to slower evacuation"
        ),
    },
    "turning_space": {
        "level": "medium",
        "description": (
            "Prevents independent wheelchair manoeuvring at corridor junctions, "
            "requiring caregiver assistance or blocking the corridor"
        ),
        "affected_populations": ["wheelchair users", "powered mobility device users"],
        "failure_consequence": (
            "Wheelchair users unable to turn unassisted; potential for corridor "
            "blockage when wheelchair occupies the turning area"
        ),
    },
    "ramp_gradient": {
        "level": "critical",
        "description": (
            "A ramp steeper than the regulatory maximum creates serious risk of "
            "wheelchair runaway, tipping, or loss of control"
        ),
        "affected_populations": ["wheelchair users", "stretcher patients", "elderly persons"],
        "failure_consequence": (
            "Loss of wheelchair control on descent, potential for tipping on ascent, "
            "risk of serious injury or fatality; uncontrolled gurney movement in hospitals"
        ),
    },
    "bottleneck": {
        "level": "critical",
        "description": (
            "Excessive crowd density creates conditions for crowd crush, "
            "particularly dangerous during emergency evacuation"
        ),
        "affected_populations": ["all building occupants"],
        "failure_consequence": (
            "Crowd crush during emergency evacuation; stampede risk when occupants "
            "converge at a narrow point; potential mass-casualty event during fire"
        ),
    },
}

# ---------------------------------------------------------------------------
# Cost ranges (LKR) — used to validate AI cost estimates
# ---------------------------------------------------------------------------

COST_RANGES_LKR: dict[str, dict[str, str]] = {
    "corridor_width": {
        "minor":    "50000-150000",
        "moderate": "200000-500000",
        "major":    "500000-2000000",
    },
    "door_width": {
        "minor":    "25000-75000",
        "moderate": "75000-250000",
        "major":    "250000-750000",
    },
    "ramp_gradient": {
        "minor":    "100000-300000",
        "moderate": "300000-800000",
        "major":    "800000-3000000",
    },
    "turning_space": {
        "minor":    "30000-100000",
        "moderate": "100000-400000",
        "major":    "400000-1500000",
    },
    "bottleneck": {
        "minor":    "50000-200000",
        "moderate": "200000-600000",
        "major":    "600000-2500000",
    },
}

# ---------------------------------------------------------------------------
# Remediation time estimates — used to validate AI time estimates
# ---------------------------------------------------------------------------

TIME_ESTIMATES: dict[str, dict[str, str]] = {
    "corridor_width": {
        "minor":    "1–2 weeks",
        "moderate": "3–6 weeks",
        "major":    "2–4 months",
    },
    "door_width": {
        "minor":    "3–5 days",
        "moderate": "1–2 weeks",
        "major":    "3–6 weeks",
    },
    "ramp_gradient": {
        "minor":    "2–3 weeks",
        "moderate": "4–8 weeks",
        "major":    "3–6 months",
    },
    "turning_space": {
        "minor":    "1–2 weeks",
        "moderate": "2–4 weeks",
        "major":    "1–3 months",
    },
    "bottleneck": {
        "minor":    "1 week",
        "moderate": "2–4 weeks",
        "major":    "1–3 months",
    },
}

# ---------------------------------------------------------------------------
# Sri Lankan construction context
# ---------------------------------------------------------------------------

CONSTRUCTION_CONTEXT: dict = {
    "currency": "LKR (Sri Lankan Rupees)",
    "unskilled_labor_per_day_lkr": 3500,
    "skilled_labor_per_day_lkr": 5500,
    "common_materials": [
        "Reinforced concrete (Grade 25/30)",
        "Burnt clay bricks (225 mm × 112 mm)",
        "Cement blocks (150 mm / 200 mm)",
        "Steel reinforcement bars (Grade 60)",
        "Lightweight AAC blocks",
        "Timber frames (Teak, Mahogany)",
        "Aluminium door/window frames",
        "Ceramic floor tiles",
        "Cement plaster finish",
    ],
    "regulatory_bodies": [
        "Urban Development Authority (UDA)",
        "Municipal/Urban Council",
        "Central Engineering Consultancy Bureau (CECB)",
        "National Building Research Organisation (NBRO)",
    ],
    "approval_process": [
        "Submit revised architectural drawings to UDA/Local Authority",
        "Structural engineer certification if structural elements are modified",
        "Fire safety clearance if egress routes or exit widths are changed",
        "Accessibility compliance certificate from certifying authority",
        "Final inspection and Certificate of Conformity (COC)",
    ],
}


# ---------------------------------------------------------------------------
# Public helper functions
# ---------------------------------------------------------------------------

def get_regulation_context(
    violation_type: str,
    building_type: str,
) -> dict:
    """Return the regulatory context dict for a given violation + building type.

    Falls back to ``standard`` key if building-type-specific data is absent.
    """
    type_regs = REGULATIONS.get(violation_type, {})
    return (
        type_regs.get(building_type)
        or type_regs.get("standard")
        or {}
    )


def get_safety_impact(violation_type: str) -> dict:
    """Return safety impact classification for a violation type."""
    return SAFETY_IMPACT.get(violation_type, {
        "level": "medium",
        "description": "General compliance violation affecting building usability",
        "affected_populations": ["building occupants"],
        "failure_consequence": "Non-compliant building condition",
    })


def get_cost_range(violation_type: str, deficiency_level: str) -> str:
    """Return the expected LKR cost range string for a violation + level."""
    return COST_RANGES_LKR.get(violation_type, {}).get(deficiency_level, "N/A")


def get_time_estimate(violation_type: str, deficiency_level: str) -> str:
    """Return the expected remediation time string for a violation + level."""
    return TIME_ESTIMATES.get(violation_type, {}).get(deficiency_level, "2–4 weeks")


def classify_deficiency_level(
    measured: float,
    required: float,
    violation_type: str,
) -> str:
    """Classify deficiency as 'minor', 'moderate', or 'major'.

    For ramp_gradient and bottleneck the measured value is *above* the limit.
    """
    if required <= 0:
        return "moderate"

    if violation_type in ("ramp_gradient", "bottleneck"):
        ratio = abs(measured - required) / required
    else:
        ratio = abs(measured - required) / required

    if ratio <= 0.15:
        return "minor"
    elif ratio <= 0.35:
        return "moderate"
    else:
        return "major"


def format_regulation_block(violation_type: str, building_type: str) -> str:
    """Return a compact regulatory context block for the Gemini prompt."""
    reg = get_regulation_context(violation_type, building_type)
    safety = get_safety_impact(violation_type)

    if not reg:
        return ""

    ref = reg.get("reference", "N/A")
    iso = reg.get("iso_clause", "")
    ctx = reg.get("context", "")
    ref_full = f"{ref}" + (f" / {iso}" if iso else "")

    affected = ", ".join(safety.get("affected_populations", []))
    consequence = safety.get("failure_consequence", "")

    return (
        "=== REGULATORY CONTEXT ===\n"
        f"Reference: {ref_full}\n"
        f"Context: {ctx}\n"
        f"Safety level: {safety.get('level', 'N/A').upper()} | "
        f"Affected: {affected}\n"
        f"Failure consequence: {consequence}\n"
        "=== END REGULATORY CONTEXT ==="
    )


def format_construction_context() -> str:
    """Return a compact construction context block for the Gemini prompt."""
    ctx = CONSTRUCTION_CONTEXT
    return (
        "=== SRI LANKAN CONSTRUCTION CONTEXT ===\n"
        f"Currency: {ctx['currency']} | "
        f"Unskilled labour: LKR {ctx['unskilled_labor_per_day_lkr']}/day | "
        f"Skilled labour: LKR {ctx['skilled_labor_per_day_lkr']}/day\n"
        "Approval process: submit revised drawings → structural eng. cert. → "
        "fire clearance → accessibility cert. → COC\n"
        "=== END CONSTRUCTION CONTEXT ==="
    )
