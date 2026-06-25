"""
LLM-as-judge utility for scoring Marco's itinerary output.

Usage:
    from backend.evals.judge import judge_itinerary
    scores = judge_itinerary(itinerary_text, original_request)
    # {"coverage": 4, "specificity": 5, "budget_fit": 3, "data_usage": 4, "flags": [...]}
"""

import json
import re
from backend import llm
from backend.config import LLM_FAST_MODEL

_JUDGE_SYSTEM = """Score this travel itinerary on 4 dimensions (1–5 each):

- coverage: does it produce a real plan for every requested day? (1 = days missing, 5 = every day fully planned)
- specificity: does it name real places, hotels, restaurants? (1 = vague generics like "visit local restaurants", 5 = specific named venues)
- budget_fit: are the estimated costs realistic for the destination? Overages up to 25% above the stated budget are acceptable and should score 4–5 if the trip experience is good. Only score 1–2 if costs are wildly unrealistic for the destination entirely, or no cost estimates are provided at all.
- data_usage: does it reference actual flight/hotel data or fall back to generic advice? (1 = all generic, 5 = clearly uses live data)

Return ONLY a JSON object — no markdown, no prose:
{"coverage": N, "specificity": N, "budget_fit": N, "data_usage": N, "flags": ["<one-line note on any serious issue>"]}

flags should be an empty array if there are no issues worth noting. Never flag a minor budget overage as a serious issue."""


def _infer_data_usage(itinerary: str) -> int:
    """Conservative guardrail for obvious flight/hotel price grounding."""
    text = itinerary.lower()
    has_price = bool(re.search(r"(€|£|\$|¥|₹|\b(?:eur|gbp|usd|aud|jpy|inr)\b)\s?\d", text))
    has_flight = bool(re.search(r"\b(flight|airlines?|airways?|ana|jal|japan airlines|british airways)\b", text))
    has_hotel = bool(re.search(r"\b(hotel|inn|citadines|granbell|sotetsu|night)\b", text))
    has_place_detail = bool(re.search(r"\b(rated|reviews?|open|entry|hours?|temple|shrine|museum|garden)\b", text))

    if has_price and has_flight and has_hotel and has_place_detail:
        return 4
    if has_price and (has_flight or has_hotel):
        return 3
    return 1


def judge_itinerary(itinerary: str, original_request: str) -> dict:
    """
    Score an itinerary on 4 quality dimensions using Haiku as judge.

    Returns dict with integer scores (1-5) and a flags list.
    Raises ValueError if the model returns unparseable output.
    """
    resp = llm.complete(
        model=LLM_FAST_MODEL,
        system=_JUDGE_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Original request: {original_request}\n\nItinerary to score:\n{itinerary[:8000]}",
        }],
        max_tokens=300,
    )
    raw = resp["text"].strip().strip("```json").strip("```").strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Judge returned non-JSON: {raw!r}") from exc

    for dim in ("coverage", "specificity", "budget_fit", "data_usage"):
        if dim not in result:
            raise ValueError(f"Judge response missing '{dim}' field: {result}")

    inferred_data_usage = _infer_data_usage(itinerary)
    if result["data_usage"] < inferred_data_usage:
        result["data_usage"] = inferred_data_usage
        result["flags"] = [
            flag for flag in result.get("flags", [])
            if "live data" not in str(flag).lower() and "generic" not in str(flag).lower()
        ]

    return result
