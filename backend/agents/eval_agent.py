"""
Lightweight eval agent that checks itinerary output quality.

Uses the fast model for low-latency, cheap evaluation.
Called after the agentic loop completes — never blocks streaming.
"""

import json
import re
from datetime import date as _date

from backend import llm
from backend.config import LLM_FAST_MODEL

DEFAULT_CRITERIA = ["days_have_content", "no_conflicts"]

_BUDGET_CATEGORIES = {"travel", "accommodation", "food", "activities", "transport"}

_EVAL_SYSTEM = """You are a travel itinerary quality checker. Your job is to verify the itinerary is complete enough to render cleanly — not to police the budget.

Day-by-day coverage (is every Day N present) is checked separately by a deterministic parser — do not evaluate it yourself.

Return ONLY a JSON object with this exact structure:
{
  "passed": true,
  "issues": [],
  "criteria": {
    "days_have_content": true,
    "no_conflicts": true
  }
}

Criteria rules:
- days_have_content: Every day section has real activities — named morning, afternoon, or evening plans. Fail ONLY if a day section is essentially empty (no activities listed, just a heading or "TBD"). Set to null if cannot be determined.
- no_conflicts: No single day has two far-apart locations scheduled at the same time slot. Set to null if cannot be determined.
- passed: true only if every non-null criterion passes and issues is empty.
- issues: Short, specific descriptions of each failure. Empty list if all pass.

Budget rule: Budget overages are NOT failures. An itinerary 10–25% over the stated budget is fine — the user can negotiate cheaper options in follow-up. Never set passed=false because of budget alone.

Check every criterion listed under "Check these criteria" below.
No markdown, no explanation. JSON only."""


def _looks_like_itinerary(text: str) -> bool:
    """Quick guard — skip eval for casual chat responses."""
    return bool(re.search(r'(?i)\bday\s+[12]\b', text)) and len(text) > 400


def check(
    output: str,
    trip_data: dict | None = None,
    criteria: list[str] | None = None,
) -> dict:
    """
    Evaluate itinerary quality using the fast model.

    Args:
        output: The full itinerary text from the agentic loop.
        trip_data: Optional trip context dict (budget, start_date, end_date, currency).
        criteria: Criteria to check. Defaults to DEFAULT_CRITERIA.

    Returns:
        {"passed": bool, "issues": list[str], "criteria": dict[str, bool | None]}
        Returns a passing result without LLM call if output is not an itinerary.
    """
    active_criteria = criteria or DEFAULT_CRITERIA
    empty_result = {"passed": True, "issues": [], "criteria": {c: None for c in active_criteria}}

    if not _looks_like_itinerary(output):
        return empty_result

    context_lines: list[str] = []
    if trip_data:
        start = trip_data.get("start_date", "")
        end = trip_data.get("end_date", "")
        if start and end:
            try:
                days = (_date.fromisoformat(end) - _date.fromisoformat(start)).days + 1
                context_lines.append(f"Trip duration: {days} days ({start} to {end})")
            except ValueError:
                pass

    context_lines.append(f"Check these criteria: {', '.join(active_criteria)}")
    prompt = "\n".join(context_lines) + "\n\n---\n\n" + output[:8000]

    try:
        resp = llm.complete(
            model=LLM_FAST_MODEL,
            system=_EVAL_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        raw = resp["text"].strip().strip("```json").strip("```").strip()
        result = json.loads(raw)
        # Normalise: ensure expected keys exist
        result.setdefault("passed", True)
        result.setdefault("issues", [])
        result.setdefault("criteria", {})
        return result
    except Exception as exc:
        print(f"eval_agent error: {exc}")
        return empty_result


def check_format(text: str, num_days_expected: int | None = None) -> dict:
    """
    Deterministic structural check on itinerary text. No LLM call.

    Counts day sections via extract_all_days() and compares to the expected
    trip length. This is the sole source of truth for day coverage — it uses
    the same regex the UI depends on, so check() does not judge coverage itself.

    Returns:
        {"passed": bool, "issues": list[str], "days_found": int,
         "days_expected": int | None, "has_budget": bool}
    """
    if not _looks_like_itinerary(text):
        return {
            "passed": True, "issues": [],
            "days_found": 0, "days_expected": num_days_expected, "has_budget": False,
        }

    from backend.agents.planning_agent import extract_all_days
    days_found = len(extract_all_days(text))
    has_budget = bool(re.search(r'(?i)(total estimated|estimated total|budget.*\d|\d.*budget)', text))

    issues: list[str] = []
    if num_days_expected is not None and days_found < num_days_expected - 1:
        issues.append(f"itinerary covers {days_found} of {num_days_expected} expected days")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "days_found": days_found,
        "days_expected": num_days_expected,
        "has_budget": has_budget,
    }


def check_budget(breakdown: dict) -> dict:
    """
    Programmatically validate a budget_breakdown dict for BudgetPanel rendering.
    No LLM call — purely structural checks on the extracted numbers.

    Returns {"passed": bool, "issues": list[str], "criteria": dict, "hint": str}
    The "hint" field summarises what was missing, ready to pass back into extraction.
    """
    categories = {
        k: v for k, v in breakdown.items()
        if k in _BUDGET_CATEGORIES and isinstance(v, (int, float)) and v > 0
    }
    total = breakdown.get("total_estimated")

    issues: list[str] = []
    cat_ok = len(categories) >= 2
    total_ok = isinstance(total, (int, float)) and total > 0
    consistent_ok = True

    if not cat_ok:
        missing = _BUDGET_CATEGORIES - categories.keys()
        issues.append(
            f"only {len(categories)} cost categories populated; "
            f"missing estimates for: {', '.join(sorted(missing))}"
        )
    if not total_ok:
        issues.append("total_estimated is missing or zero")
    elif categories:
        cat_sum = sum(categories.values())
        if cat_sum > 0:
            drift = abs(total - cat_sum) / cat_sum
            if drift > 0.15:
                consistent_ok = False
                issues.append(
                    f"total_estimated ({total:.0f}) differs from category sum "
                    f"({cat_sum:.0f}) by {drift:.0%}"
                )

    hint = "; ".join(issues) if issues else ""
    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "hint": hint,
        "criteria": {
            "has_required_categories": cat_ok,
            "total_is_positive": total_ok,
            "total_is_consistent": consistent_ok,
        },
    }
