"""LLM Brain — Gemini IS the MARL agent policy.

Two call modes
--------------
batch_decide()   -- ONE call returns actions for ALL agents.
                    Used by the simulation engine every BATCH_INTERVAL frames.
                    6 total calls per simulation run → well within free-tier.

make_decision()  -- Single-agent call (kept for AI consultant & tests).

Rate limits (FREE tier): 15 req/min, 1500 req/day
Batch design ensures ≤ 10 calls per 60-second simulation run.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

try:
    from google import genai as _genai_mod
    from google.genai import types as _genai_types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

_VALID_ACTIONS = {"move_forward", "turn_left", "turn_right", "explore_alternative", "wait"}

# Hard cap: 6 batch calls × small buffer. Well under 15/min.
MAX_CALLS_PER_RUN = 12


class LLMBrain:
    """Gemini as the actor policy for MARL building navigation."""

    _MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: Optional[str] = None):
        if not _GENAI_AVAILABLE:
            raise ImportError("google-genai not installed. Run: pip install google-genai")

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set in backend/.env")

        self._client = _genai_mod.Client(api_key=self.api_key)

        # Connection test
        try:
            resp = self._client.models.generate_content(
                model=self._MODEL,
                contents="Reply OK.",
            )
            reply = (resp.text or "").strip()
            print(f"[LLMBrain] Ready — model={self._MODEL}  test={reply!r}")
        except Exception as exc:
            raise RuntimeError(f"Gemini connection failed: {exc}") from exc

        self.api_calls: int = 0
        self._errors: List[str] = []

    # ------------------------------------------------------------------
    # PRIMARY: Batch decide — ONE call for ALL agents
    # ------------------------------------------------------------------

    def batch_decide(
        self,
        agent_states: List[Dict],
        frame: int,
        total_frames: int,
        goal: List[float],
    ) -> Dict[str, str]:
        """Query Gemini for all agents at once.

        Parameters
        ----------
        agent_states : list of dicts with keys id, type, pos, dist_to_goal, heading_deg
        frame        : current simulation frame
        total_frames : total frames in simulation
        goal         : [x, y] exit position

        Returns
        -------
        dict mapping agent_id (str) → action (str)
        Guaranteed to return a complete map; missing agents default to "move_forward".
        """
        if self.api_calls >= MAX_CALLS_PER_RUN:
            print(f"[LLMBrain] Rate cap reached — all agents use fallback")
            return {str(s["id"]): "move_forward" for s in agent_states}

        # Build compact representation
        rows = []
        for s in agent_states:
            rows.append(
                f'  {{"id":"{s["id"]}", "type":"{s["type"]}", '
                f'"pos":[{s["pos"][0]:.1f},{s["pos"][1]:.1f}], '
                f'"dist":{s["dist_to_goal"]:.1f}, '
                f'"heading":{s["heading_deg"]:.0f}}}'
            )

        prompt = f"""You are the collective intelligence of a building evacuation simulation.

Simulation: frame {frame}/{total_frames}
Exit goal: [{goal[0]:.1f}, {goal[1]:.1f}]
Agents ({len(agent_states)} total):
[
{chr(10).join(rows)}
]

For EACH agent decide the best action to evacuate the building:
- "move_forward"       — continue directly toward the exit
- "turn_left"          — turn 45° left and move (use when blocked on right)
- "turn_right"         — turn 45° right and move (use when blocked on left)
- "explore_alternative"— sharp 90° turn, find new route (use when stuck/far)
- "wait"               — pause (use only if very crowded)

Rules:
1. Agents far from exit (dist > 5m) should explore or turn if not closing in.
2. Agents near exit (dist < 2m) must use move_forward.
3. Specialist agents are leaders — give them efficient routes.
4. Spread agents out — avoid all choosing the same direction.

Return ONLY valid JSON, no markdown:
{{"0": "action", "1": "action", ...}}
Include every agent id."""

        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self._MODEL,
                    contents=prompt,
                    config=_genai_types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.8,
                        max_output_tokens=800,
                        thinking_config=_genai_types.ThinkingConfig(
                            thinking_budget=0
                        ),
                    ),
                )
                raw = (response.text or "").strip()

                # Robust JSON extraction — strip markdown fences, find first {...}
                text = re.sub(r"```(?:json)?|```", "", raw).strip()
                m = re.search(r"\{[\s\S]+\}", text)
                if m:
                    text = m.group(0)

                decisions = json.loads(text)

                # Validate — keep only known actions, default rest
                result = {}
                for s in agent_states:
                    aid    = str(s["id"])
                    action = decisions.get(aid, "move_forward")
                    result[aid] = action if action in _VALID_ACTIONS else "move_forward"

                self.api_calls += 1
                time.sleep(1.0)   # 1s gap — comfortably under 15 req/min

                sample = ", ".join(f"{k}:{v}" for k, v in list(result.items())[:5])
                print(f"[LLMBrain] Batch ✓ frame={frame}  [{sample}...]")
                return result

            except json.JSONDecodeError as exc:
                raw_preview = (response.text or "")[:120] if response else "no response"
                print(f"[LLMBrain] Batch JSON error (attempt {attempt+1}): {exc}")
                print(f"[LLMBrain] Raw preview: {raw_preview!r}")
                self._errors.append(f"json:{exc}")
                if attempt == 0:
                    time.sleep(1)
            except Exception as exc:
                self._errors.append(str(exc))
                print(f"[LLMBrain] Batch API error (attempt {attempt+1}): {exc}")
                if attempt == 0:
                    time.sleep(2)

        print("[LLMBrain] Batch failed — using goal-directed fallback for this interval")
        return {str(s["id"]): "move_forward" for s in agent_states}

    # ------------------------------------------------------------------
    # SECONDARY: Single-agent decide (used by AI consultant / tests)
    # ------------------------------------------------------------------

    def make_decision(
        self,
        agent_position: List[float],
        goal_position: List[float],
        nearby_obstacles: List = [],
        other_agents: List = [],
        decision_context: str = "navigation",
    ) -> Dict:
        """Single-agent Gemini decision (kept for compliance AI consultant)."""
        if self.api_calls >= MAX_CALLS_PER_RUN:
            return self._fallback("rate_limit_cap")

        dist = math.sqrt(
            (goal_position[0] - agent_position[0]) ** 2 +
            (goal_position[1] - agent_position[1]) ** 2
        )
        bearing = math.degrees(math.atan2(
            goal_position[1] - agent_position[1],
            goal_position[0] - agent_position[0],
        ))

        prompt = f"""Pedestrian agent navigating a building to the exit.

Position: ({agent_position[0]:.2f}, {agent_position[1]:.2f})
Exit: ({goal_position[0]:.2f}, {goal_position[1]:.2f})  dist={dist:.1f}m  bearing={bearing:.0f}°
Nearby walls: {len(nearby_obstacles)}
Other agents nearby: {len(other_agents)}
Context: {decision_context}

Output ONLY valid JSON (no markdown):
{{"action": "move_forward"|"turn_left"|"turn_right"|"explore_alternative"|"wait",
  "reasoning": "<60 chars>",
  "confidence": 0.0-1.0}}"""

        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self._MODEL,
                    contents=prompt,
                    config=_genai_types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                        max_output_tokens=200,
                        thinking_config=_genai_types.ThinkingConfig(
                            thinking_budget=0
                        ),
                    ),
                )
                raw  = (response.text or "").strip()
                text = re.sub(r"```(?:json)?|```", "", raw).strip()
                m    = re.search(r"\{[\s\S]+\}", text)
                text = m.group(0) if m else text
                d    = json.loads(text)
                if not (d.get("action") in _VALID_ACTIONS and "reasoning" in d):
                    raise ValueError("Invalid structure")

                d.update({"from_cache": False, "timestamp": datetime.now().isoformat()})
                self.api_calls += 1
                time.sleep(1.0)
                return d

            except Exception as exc:
                self._errors.append(str(exc))
                if attempt == 0:
                    time.sleep(2)

        return self._fallback("api_error")

    def get_stats(self) -> Dict:
        return {
            "api_calls": self.api_calls,
            "errors": len(self._errors),
            "calls_remaining": MAX_CALLS_PER_RUN - self.api_calls,
        }

    def _fallback(self, reason: str) -> Dict:
        return {
            "action": "move_forward",
            "reasoning": "LLM unavailable",
            "confidence": 0.3,
            "from_cache": False,
            "fallback": True,
            "fallback_reason": reason,
            "timestamp": datetime.now().isoformat(),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[LLMBrain] = None
_init_attempted: bool = False


def get_llm_brain() -> Optional[LLMBrain]:
    global _instance, _init_attempted
    if _init_attempted:
        return _instance
    _init_attempted = True
    try:
        _instance = LLMBrain()
    except Exception as exc:
        print(f"[LLMBrain] Disabled — {exc}")
        _instance = None
    return _instance


def reset_llm_brain() -> None:
    global _instance, _init_attempted
    _instance = None
    _init_attempted = False
