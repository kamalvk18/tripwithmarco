"""
Orchestrator — routes a chat turn through the right pipeline stages.

Flow for a full planning request:
  1. Extract structured trip details from conversation (fast model)
  2. Route: EXTRACT_ONLY | INCREMENTAL | FULL_PLAN
  3. Research: call travel tools in parallel → ResearchEvidence  [FULL_PLAN only]
  4. Assemble PlannerInput and delegate to planner_agent.plan()

Companion mode, eval, and repair are handled upstream (chat() and _sse_stream()).
"""

from __future__ import annotations

from backend.agents.models import ExtractionResult, PlannerInput, ResearchEvidence, WorkflowType
from backend.agents.planning_agent import extract_itinerary, extract_trip_details
from backend.agents.planner_agent import plan
from backend.agents.research_agent import run_research, run_research_stops
from backend.agents.route_agent import assign_stop_dates, derive_route


def _has_existing_itinerary(messages: list) -> bool:
    """True if the conversation already contains a completed day-by-day itinerary."""
    return bool(extract_itinerary(messages))


def _same_trip(extraction: ExtractionResult, trip_data: dict | None) -> bool:
    """
    True if the extracted destination/dates match the saved trip record.

    Used to guard against routing destination-change messages as INCREMENTAL.
    If the user says "let's go to Osaka instead" mid-conversation, we need
    fresh research — the existing itinerary is for a different place.
    """
    if not trip_data:
        return False
    saved_dest = (trip_data.get("destination") or "").lower().strip()
    saved_start = trip_data.get("start_date", "")
    ext_dest = extraction.destination.lower().strip()
    ext_start = extraction.start_date
    dest_match = bool(saved_dest and ext_dest and (saved_dest in ext_dest or ext_dest in saved_dest))
    date_match = not ext_start or not saved_start or ext_start == saved_start
    return dest_match and date_match


def _route(
    extraction: ExtractionResult,
    messages: list,
    trip_data: dict | None,
) -> WorkflowType:
    if not extraction.is_complete:
        return WorkflowType.EXTRACT_ONLY
    if _has_existing_itinerary(messages) and _same_trip(extraction, trip_data):
        return WorkflowType.INCREMENTAL
    return WorkflowType.FULL_PLAN


def _store_side_channel(
    collected: dict | None,
    planner_input: PlannerInput,
    system_base: str,
    workflow: WorkflowType,
) -> None:
    """Store PlannerInput, system_base, and workflow in collected so _sse_stream() can run repair and eval logging."""
    if collected is not None:
        collected["_planner_input"] = planner_input
        collected["_system_base"] = system_base
        collected["_workflow"] = workflow.value


def orchestrate(
    messages: list,
    system_base: str,
    trip_data: dict | None,
    on_tool_call=None,
    collected: dict | None = None,
):
    """
    Generator — yields text chunks for the planning path (non-companion).

    Args:
        messages:     Full conversation history.
        system_base:  SYSTEM_PROMPT + dynamic context assembled by chat().
        trip_data:    Trip record dict (currency, num_travelers, etc.).
        on_tool_call: Callback(tool_name, tool_input) for SSE status events.
        collected:    Mutable dict; hotel_suggestions are merged into it.
    """
    # Step 1 — Extract structured trip state
    extracted = extract_trip_details(messages)
    extraction = ExtractionResult.from_sources(extracted, trip_data)

    # Step 2 — Route
    workflow = _route(extraction, messages, trip_data)
    print(f"🗺️  Orchestrator: {workflow.value}")

    if workflow == WorkflowType.EXTRACT_ONLY:
        # Missing destination or dates — planner asks the user for what's missing
        planner_input = PlannerInput(
            extraction=extraction,
            evidence=ResearchEvidence(),
            messages=messages,
        )
        _store_side_channel(collected, planner_input, system_base, workflow)
        yield from plan(planner_input, system_base, on_tool_call, collected)
        return

    if workflow == WorkflowType.INCREMENTAL:
        # Existing itinerary for the same trip — evidence already in conversation history,
        # no new research needed. Planner answers directly from context.
        planner_input = PlannerInput(
            extraction=extraction,
            evidence=ResearchEvidence(),
            messages=messages,
        )
        _store_side_channel(collected, planner_input, system_base, workflow)
        yield from plan(planner_input, system_base, on_tool_call, collected)
        return

    # Step 3 — FULL_PLAN
    # Multi-stop trips: fix the route before any research fires, since hotel
    # and places parameters are derived per stop.
    if extraction.is_multi_stop:
        if not extraction.stops:
            if on_tool_call:
                on_tool_call("planning_route", {})
            stops, route_label = derive_route(extraction)
            if stops:
                extraction = extraction.model_copy(update={
                    "stops": stops,
                    "destination": route_label or extraction.destination,
                })
        elif not extraction.stops[0].check_in:
            # User named the stops — assign dates deterministically
            extraction = extraction.model_copy(update={
                "stops": assign_stop_dates(extraction.stops, extraction.start_date, extraction.end_date),
            })

    # Research: deterministic per-stop fan-out for multi-stop trips (no LLM),
    # LLM-derived tool parameters otherwise.
    if extraction.is_multi_stop and extraction.stops:
        evidence = run_research_stops(extraction)
    else:
        evidence = run_research(extraction)

    # Surface research tool calls as SSE status events (fires before first text chunk)
    if on_tool_call:
        for tool_name in evidence.tools_called:
            on_tool_call(tool_name, {})

    # Merge hotel suggestions from research into the shared collected dict
    if collected is not None and evidence.hotel_suggestions:
        collected.setdefault("hotel_suggestions", []).extend(evidence.hotel_suggestions)

    print(f"   tools={evidence.tools_called} | days={extraction.num_days} | evidence_empty={evidence.is_empty()}")

    # Step 4 — Delegate to planner
    planner_input = PlannerInput(
        extraction=extraction,
        evidence=evidence,
        messages=messages,
    )
    _store_side_channel(collected, planner_input, system_base, workflow)
    yield from plan(planner_input, system_base, on_tool_call, collected)
