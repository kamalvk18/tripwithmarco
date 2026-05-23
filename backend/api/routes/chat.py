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

import json
import queue
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool

from backend.agents.planning_agent import (
    chat,
    extract_trip_details,
    extract_itinerary,
    extract_budget_breakdown,
)
from backend.api.schemas import ChatRequest, ExtractRequest, ExtractResponse

router = APIRouter(prefix="/chat", tags=["chat"])


async def _sse_stream(messages: list, trip_data: dict | None, companion_mode: bool):
    """
    Async SSE generator that wraps the sync chat() generator.

    Tool-call events from the agentic loop are forwarded as SSE events so
    clients can display live status (e.g. "Checking flights...") without
    polling. Events are emitted before the text chunk that follows the tool
    result, so they arrive a few tokens early — good enough for a status label.
    """
    tool_queue: queue.Queue[str] = queue.Queue()

    def on_tool_call(tool_name: str, _: dict) -> None:
        """Called from the threadpool thread — push the name into the queue."""
        tool_queue.put_nowait(tool_name)

    raw_messages = [m.model_dump() for m in messages]
    gen = chat(
        raw_messages,
        trip_data=trip_data,
        companion_mode=companion_mode,
        on_tool_call=on_tool_call,
    )

    async for chunk in iterate_in_threadpool(gen):
        # Drain any tool events that fired before this text chunk arrives
        while True:
            try:
                tool_name = tool_queue.get_nowait()
                yield f"data: {json.dumps({'tool_call': tool_name})}\n\n"
            except queue.Empty:
                break
        yield f"data: {json.dumps({'text': chunk})}\n\n"

    # Final drain (tool events after the last text chunk, e.g. tail tool calls)
    while True:
        try:
            tool_name = tool_queue.get_nowait()
            yield f"data: {json.dumps({'tool_call': tool_name})}\n\n"
        except queue.Empty:
            break

    yield "data: [DONE]\n\n"


@router.post("/stream")
async def stream_chat(req: ChatRequest):
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
async def chat_sync(req: ChatRequest):
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
    return {"response": full_text}


@router.post("/extract", response_model=ExtractResponse)
async def extract_info(req: ExtractRequest):
    """
    Run post-generation extraction on a completed conversation.

    Makes two Claude Haiku calls (~200 tokens each):
      1. Extract structured trip metadata (destination, city, dates, country code)
      2. Extract budget breakdown per category from the itinerary text

    Call this after the first itinerary response to populate trip metadata
    before saving to the trip store.
    """
    raw_messages = [m.model_dump() for m in req.messages]
    extracted = extract_trip_details(raw_messages)
    itinerary = extract_itinerary(raw_messages)
    budget_breakdown = extract_budget_breakdown(itinerary, currency=req.currency)
    return ExtractResponse(**{**extracted, "budget_breakdown": budget_breakdown})
