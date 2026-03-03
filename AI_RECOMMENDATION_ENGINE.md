# AI Recommendation Engine — Full Documentation

## Overview

The AI recommendation system has **6 files** that work together in a clear pipeline.
Gemini only participates in the very last step — everything else is pure Python and local data.

```
regulations.json       ← Standards database (what the rules are)
compliance.py          ← Geometry scanner (what is wrong)
knowledge_base.py      ← Domain knowledge (why, how to fix, cost)
ai_consultant.py       ← Pipeline controller (assembles everything for Gemini)
main.py                ← API endpoint (glues frontend to backend)
ViolationMonitor.tsx   ← Frontend (renders the result)
```

---

## Stage-by-Stage Flow

### Stage 1 — Upload a GLB Model

`main.py` → `geometry.py` → scans the 3D mesh

- The backend slices the building at **1.5m height** (wall level)
- It finds wall segments as line coordinates: `[x1, y1, x2, y2]`
- It extracts boundary polygon, obstacles, and floor area
- **Output:** list of wall segments + floor polygon

---

### Stage 2 — Compliance Checker Scans the Geometry

**File: `compliance.py`**

Checks 5 violation types using pure geometry maths — no AI involved.

**Example: Corridor width check**

```python
# Takes every pair of parallel wall segments
# Measures the perpendicular distance between them
perp_dist = abs(vmx * (-di[1]) + vmy * di[0])

# Reads the standard from regulations.json
min_width = self.regs["min_corridor_width_m"]  # → 1.2 for residential

# If the gap is too narrow → violation
if perp_dist < min_width:
    measured_value = 0.89   # actual gap between your walls
    required_value = 1.2    # from regulations.json
    severity = "high"       # 0.89 / 1.2 = 0.74, between 0.50 and 0.75
```

The same logic is applied for:

| Violation Type | Detection Method |
|---|---|
| `corridor_width` | Perpendicular distance between parallel wall pairs |
| `door_width` | Opening width between door frame segments |
| `turning_space` | Clear circle radius at corridor intersections |
| `ramp_gradient` | Height rise ÷ horizontal run from mesh vertices |
| `bottleneck` | Agent density (persons/m²) from simulation trajectories |

---

### Stage 3 — Standards Read from `regulations.json`

**File: `regulations.json`**

A local JSON file with all Sri Lankan UDA + ISO 21542 standards hardcoded per building type.

```json
"residential": {
  "min_corridor_width_m": 1.2,
  "min_door_width_m": 0.75,
  "min_turning_space_m": 1.5,
  "max_ramp_gradient": 0.083,
  "max_safe_density_persons_per_sqm": 1.5
}
```

The building type selected in the UI dropdown determines which row is used.
Different building types have different thresholds:

| Building Type | Min Corridor | Min Door | Max Ramp | Max Density |
|---|---|---|---|---|
| Residential | 1.2m | 0.75m | 8.3% | 1.5 p/m² |
| Public Buildings | 1.5m | 0.9m | 8.3% | 2.0 p/m² |
| Hospital | 2.0m | 1.1m | 5.0% | 1.0 p/m² |
| Educational | 1.8m | 1.0m | 8.3% | 2.5 p/m² |
| Commercial | 1.5m | 0.9m | 8.3% | 3.0 p/m² |
| Industrial | 1.5m | 1.0m | 8.3% | 1.0 p/m² |

---

### Stage 4 — Knowledge Base Adds Context

**File: `knowledge_base.py`**

When "Get AI Recommendation" is clicked, this file is read to enrich the prompt with 6 types of pre-written knowledge:

#### ① Regulation Context (per violation type + building type)

```python
"corridor_width" → "residential" → {
    "minimum": 1.2,
    "regulation": "UDA Planning Regulation Section 3.2.1",
    "context": "Residential corridors must accommodate wheelchair passage..."
}
```

#### ② Common Causes (pre-written list)

```
"Structural columns encroaching on corridor space"
"HVAC ducts or plumbing reducing effective width"
"Furniture or equipment placed in corridors"
```

#### ③ Solutions by Deficiency Level

Deficiency ratio is calculated: `|measured - required| / required`

| Ratio | Level | Example Solution |
|---|---|---|
| ≤ 15% | minor | Relocate obstructions, reroute surface-mounted services |
| 15–35% | moderate | Remove non-structural partitions and rebuild at correct offset |
| > 35% | major | Full structural redesign required |

#### ④ Cost Ranges (hardcoded LKR values)

```python
"corridor_width": {
    "cost_ranges_lkr": {
        "minor":    "50000-150000",
        "moderate": "200000-500000",
        "major":    "500000-2000000"
    }
}
```

#### ⑤ Safety Impact (hardcoded per violation type)

```python
"corridor_width": {
    "level": "high",
    "description": "Directly affects emergency evacuation capacity and wheelchair accessibility",
    "affected_populations": ["wheelchair users", "stretcher patients", "emergency evacuees"],
    "failure_consequence": "Blocked evacuation route, potential casualties during fire/emergency"
}
```

#### ⑥ Few-Shot Examples

Pre-written example question-and-answer pairs stored in `FEW_SHOT_EXAMPLES`.
Gemini is shown a completed example for the same violation type and closest severity
**before** being asked to answer the actual violation — this ensures consistent format and depth.

---

### Stage 5 — Prompt Assembled and Sent to Gemini

**File: `ai_consultant.py` → `_build_prompt()`**

Everything from Stage 4 is combined into one large text prompt.

**Example prompt for a corridor width violation:**

```
[SYSTEM PROMPT]
You are a senior Sri Lankan architect with 20+ years of experience...
Building type context — residential:
  - corridor_width: UDA Section 3.2.1. Residential corridors must accommodate wheelchair...
Sri Lankan approval process:
  1. Submit revised drawings to UDA/Local Authority
  2. Structural engineer certification (if structural changes)
  ...

[USER PROMPT]
Building type: residential
Total floor area: 60.85 m²

Relevant domain knowledge:
  Regulation: UDA Planning Regulation Section 3.2.1
  Context: Residential corridors must accommodate wheelchair passage...
  Common causes: Structural columns encroaching; HVAC ducts; Furniture
  Recommended approach (moderate): Remove non-structural partitions and rebuild...
  Typical cost range: LKR 200,000–500,000

Safety impact level: HIGH
  Impact: Directly affects emergency evacuation capacity
  Affected: wheelchair users, stretcher patients, emergency evacuees
  Failure consequence: Blocked evacuation route, potential casualties...

Comparative analysis:
  Measured 0.89m vs required 1.2m.
  Deficiency: 0.31m (25.8% below minimum)

--- Reference example (similar violation) ---
  Input:  { corridor_width, medium, residential, 1.1m measured, 1.2m required }
  Output: { "analysis": "The corridor width of 1.1m is 0.1m (8.3%) below..." }
--- End reference ---

SEVERITY: HIGH — provide at least 5 implementation steps.

Violation to analyze:
  Type:             corridor_width
  Severity:         high
  Measured value:   0.89
  Required value:   1.2
  Description:      Corridor width 0.89m less than required 1.2m for residential
  Regulation:       UDA Section 3.2.1
  Location (x,y):   (-1.23, 2.45)
  Remediation time: 3-6 weeks

Provide your structured JSON recommendation.
```

**Gemini returns JSON with this exact schema:**

```json
{
  "analysis": "...",
  "solution": "...",
  "implementation_steps": ["Step 1...", "Step 2...", "..."],
  "complexity": "low | medium | high",
  "estimated_cost_lkr": "200000-500000",
  "regulation_reference": "UDA Section 3.2.1, ISO 21542:2011 Clause 13",
  "alternative_solutions": ["Alternative 1...", "Alternative 2..."]
}
```

---

### Stage 6 — Post-Processing Before Sending to Frontend

**File: `ai_consultant.py` → `_validate_response()` and `_post_process()`**

After Gemini responds, the code automatically:

1. **Validates** — all 7 required fields exist with correct types
2. **Cross-checks cost** — if Gemini's cost is more than 2.5× above or below the knowledge base range, it is replaced with the knowledge base value
3. **Pads steps** — if fewer than 4 implementation steps, standard fallback steps are appended
4. **Adds confidence score** — 0.0 to 1.0 based on regulation reference completeness, step count, and complexity classification
5. **Caches the result** — same violation ID will return cached response on repeated clicks

---

## Complete Data Flow Diagram

```
Your GLB file
     │
     ▼
[geometry.py]
  Slice at 1.5m height
  Find parallel wall pairs
  Measure perpendicular gap = 0.89m
     │
     ▼
[regulations.json]
  residential.min_corridor_width_m = 1.2
  0.89 < 1.2 → VIOLATION
  0.89 / 1.2 = 0.74 → severity = "high"
     │
     ▼
[knowledge_base.py]
  Regulation text  → "UDA Section 3.2.1"
  Common causes    → ["Structural columns...", "HVAC ducts..."]
  Solution text    → "Remove partitions and rebuild at correct offset..."
  Cost range       → "LKR 200,000–500,000"
  Safety impact    → "wheelchair users, emergency evacuees"
  Few-shot example → pre-written sample for same violation type + severity
     │
     ▼
[ai_consultant.py]
  Assembles all of the above into a single structured prompt
     │
     ▼
[Gemini API]
  Reads all pre-supplied facts
  Writes the analysis, solution, and steps in professional English
  Returns JSON
     │
     ▼
[ai_consultant.py]
  Validates all 7 fields exist
  Cross-checks cost against knowledge base
  Pads implementation steps if fewer than 4
  Adds confidence score
     │
     ▼
[main.py]
  Sends JSON response to frontend
     │
     ▼
[ViolationMonitor.tsx]
  Renders the AI Recommendation card
```

---

## What Gemini Decides vs What the Code Decides

| Output Item | Decided By |
|---|---|
| `0.89m` measured value | `compliance.py` — geometric scan of GLB |
| `1.2m` required standard | `regulations.json` — hardcoded |
| `severity: high` | Python ratio calculation (`0.89 / 1.2 = 0.74`) |
| `UDA Section 3.2.1` | `knowledge_base.py` — hardcoded |
| `LKR 200,000–500,000` | `knowledge_base.py` (overrides Gemini if wrong) |
| `3–6 weeks` remediation time | `knowledge_base.py` — hardcoded |
| Common causes list | `knowledge_base.py` — hardcoded |
| `wheelchair users, evacuees` | `knowledge_base.py` — hardcoded |
| Written **analysis** paragraph | **Gemini** |
| Written **solution** paragraph | **Gemini** |
| **Implementation steps** wording | **Gemini** |
| **Alternative solutions** wording | **Gemini** |

---

## Fallback Behaviour (When Gemini is Unavailable)

If the Gemini API call fails (network error, quota exceeded, invalid key), the system does **not** crash.
Instead, `ai_consultant.py → _fallback()` generates a recommendation entirely from `knowledge_base.py`
with no AI involvement. The output looks identical but uses pre-written template text.

The fallback result is clearly marked with a confidence score of `0.4` (vs. `0.8–1.0` for Gemini responses).

---

## Files Reference Summary

| File | Location | Role |
|---|---|---|
| `regulations.json` | `backend/core/regulations.json` | All UDA + ISO 21542 numeric standards per building type |
| `compliance.py` | `backend/core/compliance.py` | Geometry scanner — detects violations from wall segments |
| `knowledge_base.py` | `backend/core/knowledge_base.py` | Regulation text, causes, solutions, costs, few-shot examples |
| `ai_consultant.py` | `backend/core/ai_consultant.py` | Prompt builder, Gemini client, validator, post-processor |
| `main.py` | `backend/main.py` | FastAPI endpoint `/api/ai-consultant` |
| `ViolationMonitor.tsx` | `frontend/src/components/ViolationMonitor.tsx` | React UI card that renders the recommendation |
