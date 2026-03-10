"""Hybrid AI recommendation engine for building compliance violations.

Pipeline
--------
1. Extract violation parameters (spatial geometry + regulations).
2. Build a parameter-grounded prompt — Gemini receives *facts*, not templates.
3. Call Gemini API (with retry logic).
4. Validate and cross-check the response against extracted parameters.
5. Add confidence score; cache result.

Gemini's role: produce original analysis, reasoning, and solution text
from the measured parameters it receives.  It does NOT receive pre-written
template solutions.
"""

from __future__ import annotations

import json
import os
import re
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _extract_json(text: str) -> str:
    """Strip markdown code fences and return the raw JSON string."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ``` wrappers
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a senior Sri Lankan structural architect with 20+ years of experience \
in building compliance, accessibility design, and construction management. \
You specialize in:
- Sri Lankan Urban Development Authority (UDA) Planning & Development Regulations
- ISO 21542:2011 accessibility standards
- Sri Lankan construction materials, methods, and cost estimation in LKR
- Emergency egress, fire safety, and crowd-flow analysis

You will receive MEASURED SPATIAL DATA extracted from an actual 3D building model. \
Your task is to reason from this data to produce a compliance recommendation.

REASONING STEPS (follow in order):
1. ANALYZE the root cause using the measured values and spatial context provided.
   Quantify the deficiency (e.g. "0.31 m below minimum, 25.8% deficiency").
2. ASSESS safety impact — who is affected and what happens if unaddressed.
3. PLAN a primary solution using the actual geometry (wall positions, available \
   space, structural risk).  If wall relocation is feasible per the spatial data, \
   specify which wall to move and by how much.  If not feasible, explain the \
   constraint and propose an alternative approach.
4. ESTIMATE cost in LKR using current Sri Lankan construction rates.
5. LIST at least 4 step-by-step implementation actions.
6. PROVIDE 2–3 alternative approaches with brief cost indications.

OUTPUT FORMAT — respond with a JSON object with these exact keys:
{
  "analysis": "Root cause analysis with quantified deficiency and safety impact",
  "solution": "Primary solution with specific dimensions, materials, and approach",
  "implementation_steps": ["Step 1: ...", "Step 2: ...", ...],
  "complexity": "low | medium | high",
  "estimated_cost_lkr": "range like 200000-500000",
  "regulation_reference": "Specific UDA section and/or ISO clause numbers",
  "alternative_solutions": ["Alternative 1 with cost note", "Alternative 2 ..."]
}

CRITICAL: base your analysis and solution on the measured spatial data provided. \
Do not invent dimensions or constraints that are not in the data."""


# ---------------------------------------------------------------------------
# Severity depth instructions
# ---------------------------------------------------------------------------

_SEVERITY_DEPTH: dict[str, str] = {
    "critical": (
        "\nSEVERITY: CRITICAL — immediate safety risk.  Your response must include:\n"
        "- Detailed safety impact with emergency-scenario analysis\n"
        "- Any interim measures to reduce risk before permanent fix\n"
        "- At least 6 implementation steps\n"
        "- At least 3 alternative solutions\n"
        "- Full regulatory citation chain (UDA section + ISO clause)\n"
    ),
    "high": (
        "\nSEVERITY: HIGH — significant accessibility/safety impairment.  "
        "Provide detailed analysis with specific measurements and at least 5 implementation steps.\n"
    ),
    "medium": (
        "\nSEVERITY: MEDIUM — reduces compliance without immediate danger.  "
        "Provide practical analysis. At least 4 implementation steps.\n"
    ),
    "low": (
        "\nSEVERITY: LOW — minor deviation.  "
        "Provide concise analysis. At least 4 implementation steps.\n"
    ),
}


# ---------------------------------------------------------------------------
# AIConsultant
# ---------------------------------------------------------------------------

_MODEL = "gemini-2.5-flash"


class AIConsultant:
    """Hybrid AI compliance consultant using parameter-based Gemini prompting."""

    def __init__(self) -> None:
        from google import genai
        from google.genai import types as genai_types

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set in environment")

        self._client = genai.Client(api_key=api_key)
        self._types = genai_types
        self._max_retries = 2
        self._retry_base_delay = 1.0
        self._cache: dict[str, dict] = {}
        print(f"[AI Consultant] Initialized — model: {_MODEL} (google-genai SDK)")

    def clear_cache(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        violation: dict,
        building_context: dict,
        wall_segments: list | None,
        boundary_coords: list | None,
    ) -> str:
        """Build a parameter-grounded prompt for a single violation."""
        from core.parameter_extractor import extract_parameters
        from shapely.geometry import Polygon

        building_type = building_context.get("building_type", "residential")
        floor_area = building_context.get("total_floor_area_sqm", 0.0)

        # Build boundary polygon
        if boundary_coords and len(boundary_coords) >= 3:
            try:
                pts = [tuple(p[:2]) for p in boundary_coords]
                if pts[0] != pts[-1]:
                    pts.append(pts[0])
                boundary_polygon = Polygon(pts)
                if not boundary_polygon.is_valid:
                    boundary_polygon = boundary_polygon.buffer(0)
            except Exception:
                boundary_polygon = Polygon()
        else:
            boundary_polygon = Polygon()

        # Extract parameters
        params = extract_parameters(
            violation=violation,
            building_type=building_type,
            floor_area_m2=floor_area,
            wall_segments=wall_segments or [],
            boundary_polygon=boundary_polygon,
        )

        # Assemble prompt
        severity = violation.get("severity", "medium")
        depth_instr = _SEVERITY_DEPTH.get(severity, _SEVERITY_DEPTH["medium"])

        prompt = params.to_prompt_sections()
        prompt += depth_instr
        prompt += (
            f"\nViolation to analyse:\n"
            f"  ID: {violation.get('id', '')}\n"
            f"  Type: {violation.get('type', '')}\n"
            f"  Description: {violation.get('description', '')}\n"
            f"  Regulation cited by compliance checker: {violation.get('regulation', '')}\n\n"
            "Provide your structured JSON recommendation based on the spatial "
            "data and regulatory context above."
        )

        # --- MACHINE LEARNING INSIGHT INJECTION ---
        ml_risk_score = building_context.get("ml_risk_score")
        if ml_risk_score is not None:
            prompt += (
                f"\n\n--- MACHINE LEARNING INSIGHT ---\n"
                f"Our local predictive model analyzed the simulation trajectories and calculated a "
                f"Crowd Crush Risk Score of {ml_risk_score}/10 based on agent density and flow velocity. "
                "Please mention this risk score in your analysis and factor it into the urgency of your solution.\n"
            )

        return prompt

    # ------------------------------------------------------------------
    # Single-violation advice
    # ------------------------------------------------------------------

    def get_compliance_advice(
        self,
        violation: dict,
        building_context: dict,
        wall_segments: list | None = None,
        boundary_coords: list | None = None,
    ) -> dict:
        """Get AI recommendation for a single violation.

        Returns the cached response if the violation was already processed.
        """
        from core.validator import validate_and_score, build_fallback_recommendation
        from core.knowledge_base import get_cost_range, classify_deficiency_level, get_time_estimate, get_regulation_context

        vid = violation.get("id", "")
        if vid in self._cache:
            print(f"[AI Consultant] Cache hit: {vid}")
            return self._cache[vid]

        print(f"[AI Consultant] Processing: {vid}")
        start = time.time()

        building_type = building_context.get("building_type", "residential")
        vtype = violation.get("type", "")
        measured = float(violation.get("measured_value", 0.0))
        required = float(violation.get("required_value", 0.0))
        severity = violation.get("severity", "medium")
        deficiency_level = classify_deficiency_level(measured, required, vtype)
        kb_cost_range = get_cost_range(vtype, deficiency_level)

        prompt = self._build_prompt(
            violation, building_context, wall_segments, boundary_coords
        )
        gen_config = self._types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.25,
            top_p=0.85,
            max_output_tokens=4096,
            response_mime_type="application/json",
            thinking_config=self._types.ThinkingConfig(thinking_budget=0),
        )

        response = None
        for attempt in range(self._max_retries + 1):
            try:
                if attempt > 0:
                    delay = self._retry_base_delay * (2 ** (attempt - 1))
                    print(f"[AI Consultant] Retry {attempt}/{self._max_retries} (delay {delay:.1f}s)")
                    time.sleep(delay)

                response = self._client.models.generate_content(
                    model=_MODEL, contents=prompt, config=gen_config
                )
                elapsed = time.time() - start
                text = _extract_json(response.text)
                recommendation = json.loads(text)
                recommendation = validate_and_score(recommendation, violation, kb_cost_range)

                usage = getattr(response, "usage_metadata", None)
                if usage:
                    print(
                        f"[AI Consultant] Done in {elapsed:.1f}s "
                        f"(in={getattr(usage, 'prompt_token_count', '?')} "
                        f"out={getattr(usage, 'candidates_token_count', '?')} tokens)"
                    )
                else:
                    print(f"[AI Consultant] Done in {elapsed:.1f}s")

                self._cache[vid] = recommendation
                return recommendation

            except json.JSONDecodeError:
                print(f"[AI Consultant] Non-JSON on attempt {attempt + 1}")
                if attempt < self._max_retries:
                    continue
                raw = _extract_json(response.text) if response else ""
                reg = get_regulation_context(vtype, building_type)
                fb = build_fallback_recommendation(
                    violation=violation, building_type=building_type,
                    kb_cost_range=kb_cost_range,
                    time_estimate=get_time_estimate(vtype, deficiency_level),
                    deficiency_level=deficiency_level,
                    regulation_ref=reg.get("reference") or violation.get("regulation", ""),
                )
                if raw:
                    fb["analysis"] = raw
                self._cache[vid] = fb
                return fb

            except Exception as exc:
                exc_str = str(exc)
                print(f"[AI Consultant] Error attempt {attempt + 1}: {exc_str[:120]}")
                if "429" in exc_str or "quota" in exc_str.lower() or "resource_exhausted" in exc_str.lower():
                    print(f"[AI Consultant] Quota limit — falling back immediately")
                    reg = get_regulation_context(vtype, building_type)
                    return build_fallback_recommendation(
                        violation=violation, building_type=building_type,
                        kb_cost_range=kb_cost_range,
                        time_estimate=get_time_estimate(vtype, deficiency_level),
                        deficiency_level=deficiency_level,
                        regulation_ref=reg.get("reference") or violation.get("regulation", ""),
                    )
                if attempt < self._max_retries:
                    continue
                traceback.print_exc()
                reg = get_regulation_context(vtype, building_type)
                return build_fallback_recommendation(
                    violation=violation, building_type=building_type,
                    kb_cost_range=kb_cost_range,
                    time_estimate=get_time_estimate(vtype, deficiency_level),
                    deficiency_level=deficiency_level,
                    regulation_ref=reg.get("reference") or violation.get("regulation", ""),
                )

        reg = get_regulation_context(vtype, building_type)
        return build_fallback_recommendation(
            violation=violation, building_type=building_type,
            kb_cost_range=kb_cost_range,
            time_estimate=get_time_estimate(vtype, deficiency_level),
            deficiency_level=deficiency_level,
            regulation_ref=reg.get("reference") or violation.get("regulation", ""),
        )

    # ------------------------------------------------------------------
    # Batch processing
    # ------------------------------------------------------------------

    def get_batch_compliance_advice(
        self,
        violations: list[dict],
        building_context: dict,
        wall_segments: list | None = None,
        boundary_coords: list | None = None,
    ) -> dict[str, dict]:
        """Process multiple violations, sorted by severity.

        Returns ``{violation_id: recommendation}`` dict.
        """
        if not violations:
            return {}

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_violations = sorted(
            violations,
            key=lambda v: severity_order.get(v.get("severity", "medium"), 2),
        )

        print(f"[AI Consultant] Batch: {len(sorted_violations)} violations")
        batch_start = time.time()
        max_batch_secs = 90
        results: dict[str, dict] = {}

        building_type = building_context.get("building_type", "residential")

        gen_config = self._types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.25,
            top_p=0.85,
            max_output_tokens=4096,
            response_mime_type="application/json",
            thinking_config=self._types.ThinkingConfig(thinking_budget=0),
        )

        from core.validator import validate_and_score, build_fallback_recommendation
        from core.knowledge_base import get_cost_range, classify_deficiency_level, get_time_estimate, get_regulation_context

        for i, violation in enumerate(sorted_violations):
            vid = violation.get("id", "")

            if time.time() - batch_start > max_batch_secs:
                print(f"[AI Consultant] Batch timeout after {i} violations")
                break

            if vid in self._cache:
                results[vid] = self._cache[vid]
                continue

            print(f"[AI Consultant] [{i+1}/{len(sorted_violations)}] {vid}")

            vtype = violation.get("type", "")
            measured = float(violation.get("measured_value", 0.0))
            required = float(violation.get("required_value", 0.0))
            deficiency_level = classify_deficiency_level(measured, required, vtype)
            kb_cost_range = get_cost_range(vtype, deficiency_level)

            prompt = self._build_prompt(
                violation, building_context, wall_segments, boundary_coords
            )

            response = None
            for attempt in range(self._max_retries + 1):
                try:
                    if attempt > 0:
                        time.sleep(self._retry_base_delay * (2 ** (attempt - 1)))
                    response = self._client.models.generate_content(
                        model=_MODEL, contents=prompt, config=gen_config
                    )
                    recommendation = json.loads(_extract_json(response.text))
                    recommendation = validate_and_score(
                        recommendation, violation, kb_cost_range
                    )
                    self._cache[vid] = recommendation
                    results[vid] = recommendation
                    break
                except json.JSONDecodeError:
                    if attempt < self._max_retries:
                        continue
                    reg = get_regulation_context(vtype, building_type)
                    fb = build_fallback_recommendation(
                        violation, building_type, kb_cost_range,
                        get_time_estimate(vtype, deficiency_level),
                        deficiency_level,
                        reg.get("reference") or violation.get("regulation", ""),
                    )
                    self._cache[vid] = fb
                    results[vid] = fb
                except Exception as exc:
                    exc_str = str(exc)
                    if "429" in exc_str or "quota" in exc_str.lower() or "resource_exhausted" in exc_str.lower():
                        print(f"[AI Consultant] Quota limit hit — stopping batch")
                        reg = get_regulation_context(vtype, building_type)
                        fb = build_fallback_recommendation(
                            violation, building_type, kb_cost_range,
                            get_time_estimate(vtype, deficiency_level),
                            deficiency_level,
                            reg.get("reference") or violation.get("regulation", ""),
                        )
                        results[vid] = fb
                        # No point continuing the batch if quota is exhausted
                        break
                    if attempt < self._max_retries:
                        continue
                    reg = get_regulation_context(vtype, building_type)
                    fb = build_fallback_recommendation(
                        violation, building_type, kb_cost_range,
                        get_time_estimate(vtype, deficiency_level),
                        deficiency_level,
                        reg.get("reference") or violation.get("regulation", ""),
                    )
                    results[vid] = fb

        elapsed = time.time() - batch_start
        print(f"[AI Consultant] Batch done: {len(results)} recs in {elapsed:.1f}s")
        return results


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_consultant: AIConsultant | None = None


def get_consultant() -> AIConsultant:
    global _consultant
    if _consultant is None:
        _consultant = AIConsultant()
    return _consultant
