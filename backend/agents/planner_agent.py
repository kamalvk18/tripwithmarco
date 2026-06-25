"""
Planner agent — streams an itinerary from the strong model.

Receives PlannerInput (extraction + evidence + messages), injects any
pre-fetched evidence into the system prompt, then delegates to
run_agentic_loop(). The planner still has access to all tools as a fallback;
the evidence preamble instructs it to prefer pre-fetched data first.
"""

from __future__ import annotations

from backend.agents.models import PlannerInput
from backend.agents.planning_agent import run_agentic_loop
from backend.config import LLM_MODEL, PLANNING_MAX_TOKENS

_EVIDENCE_PREAMBLE = (
    "## Pre-fetched Travel Data\n"
    "The following data was fetched live before planning began. "
    "Use it as your primary source for flights, hotels, and places. "
    "Do not call search_flights or search_hotels again unless the user "
    "asks about a different destination or date range.\n\n"
)


def plan(
    planner_input: PlannerInput,
    system_base: str,
    on_tool_call=None,
    collected: dict | None = None,
):
    """
    Stream an itinerary from the strong model.

    Evidence is injected as a system-prompt section so the planner treats it
    as ground truth, not as part of the conversation. If evidence is empty
    (e.g. EXTRACT_ONLY path), planning proceeds without injection and the
    planner asks the user for missing details.

    Args:
        planner_input: Typed context: extraction + evidence + messages.
        system_base:   SYSTEM_PROMPT + dynamic context from chat().
        on_tool_call:  Callback(tool_name, tool_input) for SSE status events.
        collected:     Mutable dict; hotel_suggestions from fallback tool calls
                       are merged into it by run_agentic_loop().
    """
    evidence = planner_input.evidence

    if not evidence.is_empty():
        system = system_base + "\n\n" + _EVIDENCE_PREAMBLE + evidence.as_context_block()
    else:
        system = system_base

    yield from run_agentic_loop(
        planner_input.messages,
        system,
        on_tool_call=on_tool_call,
        collected=collected,
        model=LLM_MODEL,
        max_tokens=PLANNING_MAX_TOKENS,
    )
