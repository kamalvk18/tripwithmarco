"""
Streaming chat endpoint.

POST /chat/stream   → Server-Sent Events stream of Marco's response
POST /chat          → Non-streaming, returns full response as JSON (useful for testing)
POST /chat/extract  → Run post-generation extraction (trip metadata + budget)

SSE format:
    data: {"text": "<chunk>"}\n\n        — text chunk
    data: {"tool_call": "<name>"}\n\n    — tool being called (status hint)
    data: [DONE]\n\n                     — end of stream
"""

import asyncio
import json
import queue
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool
from backend.auth.deps import get_current_user
from backend.api.rate_limit import check_chat_limit, check_claude_limit

from backend.agents.planning_agent import (
    chat,
    extract_trip_details,
    extract_itinerary,
    extract_structured_itinerary,
    extract_all_days,
)
from backend.agents import eval_agent
from backend.agents.models import CriticResult
from backend.agents.repair_agent import repair
from backend.evals.judge import judge_itinerary
from backend.tools.weather import get_weather_forecast, format_weather_for_marco
from backend.api.schemas import ChatRequest, ExtractRequest, ExtractResponse


async def _run_judge(text: str, original_request: str) -> dict | None:
    """Run judge_itinerary in a threadpool, returning None on any failure."""
    try:
        return await run_in_threadpool(judge_itinerary, text, original_request)
    except Exception as exc:
        print(f"judge error (non-fatal): {exc}")
        return None

router = APIRouter(prefix="/chat", tags=["chat"])


async def _sse_stream(messages: list, trip_data: dict | None, companion_mode: bool):
    """
    Async SSE generator that wraps the sync chat() generator.

    Tool-call events from the agentic loop are forwarded as SSE events so
    clients can display live status (e.g. "Checking flights...") without
    polling. Events are emitted before the text chunk that follows the tool
    result, so they arrive a few tokens early — good enough for a status label.

    After the stream finishes a single booking_data event is emitted if any
    hotel suggestions were collected during tool calls.
    """
    tool_queue: queue.Queue[str] = queue.Queue()
    collected: dict = {}
    chunks: list[str] = []

    def on_tool_call(tool_name: str, _: dict) -> None:
        """Called from the threadpool thread — push the name into the queue."""
        tool_queue.put_nowait(tool_name)

    raw_messages = [m.model_dump() for m in messages]
    gen = chat(
        raw_messages,
        trip_data=trip_data,
        companion_mode=companion_mode,
        on_tool_call=on_tool_call,
        collected=collected,
    )

    async for chunk in iterate_in_threadpool(gen):
        # Drain any tool events that fired before this text chunk arrives
        while True:
            try:
                tool_name = tool_queue.get_nowait()
                yield f"data: {json.dumps({'tool_call': tool_name})}\n\n"
            except queue.Empty:
                break
        chunks.append(chunk)
        yield f"data: {json.dumps({'text': chunk})}\n\n"

    # Final drain (tool events after the last text chunk, e.g. tail tool calls)
    while True:
        try:
            tool_name = tool_queue.get_nowait()
            yield f"data: {json.dumps({'tool_call': tool_name})}\n\n"
        except queue.Empty:
            break

    # Pop internal side-channel keys before sending booking_data to the client
    planner_input = collected.pop("_planner_input", None)
    system_base = collected.pop("_system_base", None)

    if collected:
        yield f"data: {json.dumps({'booking_data': collected})}\n\n"

    # Eval + judge for planning responses (not companion mode short replies)
    if not companion_mode:
        full_text = "".join(chunks)
        first_user_msg = next(
            (m["content"] for m in raw_messages if m.get("role") == "user"), ""
        )
        num_days = planner_input.extraction.num_days if planner_input else None

        # Run structural eval and LLM judge concurrently; format check is pure Python
        structural, judge_scores = await asyncio.gather(
            run_in_threadpool(eval_agent.check, full_text, trip_data),
            _run_judge(full_text, first_user_msg),
        )
        format_check = eval_agent.check_format(full_text, num_days)

        # Merge into a single CriticResult — all issue sources feed one repair decision
        all_issues = structural.get("issues", []) + format_check["issues"]
        critic_result = CriticResult(
            passed=structural.get("passed", True) and format_check["passed"],
            issues=all_issues,
            criteria=structural.get("criteria", {}),
            scores=judge_scores,
        )

        eval_payload = {
            **critic_result.model_dump(),
            "format": {
                "days_found": format_check["days_found"],
                "days_expected": format_check["days_expected"],
                "has_budget": format_check["has_budget"],
            },
        }
        yield f"data: {json.dumps({'eval_result': eval_payload})}\n\n"

        if not critic_result.passed and critic_result.issues:
            ack = "\n\n*Give me a moment — I spotted an issue with that plan. Let me fix it...*\n\n"
            yield f"data: {json.dumps({'text': ack})}\n\n"
            yield f"data: {json.dumps({'eval_correction': 'starting'})}\n\n"

            correction_collected: dict = {}

            if planner_input and system_base:
                # Repair using existing PlannerInput — no re-extraction, no re-research
                repair_gen = repair(
                    planner_input, full_text, critic_result, system_base,
                    collected=correction_collected,
                )
            else:
                # Fallback: no PlannerInput available
                correction_messages = raw_messages + [
                    {"role": "assistant", "content": full_text},
                    {"role": "user", "content": critic_result.repair_instruction() or "Please fix the issues and regenerate the complete plan."},
                ]
                repair_gen = chat(correction_messages, trip_data=trip_data, companion_mode=False, collected=correction_collected)

            async for chunk in iterate_in_threadpool(repair_gen):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
            if correction_collected:
                yield f"data: {json.dumps({'booking_data': correction_collected})}\n\n"

    yield "data: [DONE]\n\n"


@router.post("/stream")
async def stream_chat(req: ChatRequest, _: dict = Depends(check_chat_limit)):
    """
    Stream Marco's response as Server-Sent Events.

    Chunk types emitted in the stream:
        data: {"text": "Hello"}           — append to response buffer
        data: {"tool_call": "search_flights"}  — tool status (optional display)
        data: [DONE]                      — stream finished

    Example fetch (JavaScript):
        const res = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({messages}),
        });
        const reader = res.body.getReader();
    """
    return StreamingResponse(
        _sse_stream(req.messages, req.trip_data, req.companion_mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if behind proxy
        },
    )


@router.post("")
async def chat_sync(req: ChatRequest, _: dict = Depends(check_chat_limit)):
    """
    Non-streaming chat — collects the full response and returns it as JSON.
    Useful for testing or clients that don't support SSE.
    """
    raw_messages = [m.model_dump() for m in req.messages]
    full_text = ""
    async for chunk in iterate_in_threadpool(
        chat(raw_messages, trip_data=req.trip_data, companion_mode=req.companion_mode)
    ):
        full_text += chunk
    result: dict = {"response": full_text}
    if not req.companion_mode:
        result["eval_result"] = await run_in_threadpool(
            eval_agent.check, full_text, req.trip_data
        )
    return result


@router.get("/weather")
async def get_weather(city: str, country_code: str = "", _: dict = Depends(get_current_user)):
    """
    Fetch and format a 5-day weather forecast for a given city.
    Requires authentication — weather API quota must not be open to the public.
    Returns: { "weather_text": "<formatted string for Marco>" }
    """
    try:
        data = get_weather_forecast(city, country_code)
        text = format_weather_for_marco(data)
        return {"weather_text": text}
    except Exception as exc:
        print(f"Weather fetch error for city='{city}': {exc}")
        raise HTTPException(status_code=502, detail="Weather service temporarily unavailable")


@router.post("/extract", response_model=ExtractResponse)
async def extract_info(req: ExtractRequest, _: dict = Depends(check_claude_limit)):
    """
    Run post-generation extraction on a completed conversation.

    Makes two Claude Haiku calls:
      1. Structured trip metadata (destination, city, dates, country code)
      2. Structured itinerary: day-by-day plan + budget breakdown via tool_choice
         — forces an exact JSON schema, no regex required.

    Call this after the first itinerary response to populate trip metadata
    before saving to the trip store.
    """
    raw_messages = [m.model_dump() for m in req.messages]
    extracted = extract_trip_details(raw_messages)
    itinerary = extract_itinerary(raw_messages)
    structured = extract_structured_itinerary(itinerary, currency=req.currency)
    raw_budget = extracted.get("budget")
    # Strip null values so the frontend hasBreakdown check works correctly
    raw_breakdown = structured.get("budget_breakdown") or {}
    clean_breakdown = {k: v for k, v in raw_breakdown.items() if v is not None}

    # Eval: if breakdown is under-populated, retry extraction with a targeted hint
    budget_eval = eval_agent.check_budget(clean_breakdown)
    if not budget_eval["passed"] and itinerary:
        print(f"💰 Budget eval failed: {budget_eval['issues']} — retrying extraction")
        retry = extract_structured_itinerary(itinerary, currency=req.currency, issues_hint=budget_eval["hint"])
        retry_breakdown = {k: v for k, v in (retry.get("budget_breakdown") or {}).items() if v is not None}
        if eval_agent.check_budget(retry_breakdown)["passed"]:
            clean_breakdown = retry_breakdown

    raw_is_domestic = extracted.get("is_domestic")
    return ExtractResponse(
        destination=extracted.get("destination", ""),
        city=extracted.get("city", ""),
        country_code=extracted.get("country_code", ""),
        origin_country=extracted.get("origin_country", ""),
        is_domestic=bool(raw_is_domestic) if raw_is_domestic is not None else None,
        start_date=extracted.get("start_date", ""),
        end_date=extracted.get("end_date", ""),
        budget=float(raw_budget) if raw_budget is not None else None,
        days=extract_all_days(itinerary),
        budget_breakdown=clean_breakdown,
    )
