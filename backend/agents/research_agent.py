"""
Research agent — calls travel tools and returns structured evidence.

Single non-streaming LLM call to derive tool parameters, then all tools
execute in parallel. No prose is generated — only ResearchEvidence.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from backend import llm
from backend.agents.models import ExtractionResult, ResearchEvidence
from backend.agents.tool_executor import execute_tool
from backend.agents.tools import TOOL_DEFINITIONS
from backend.config import LLM_FAST_MODEL

_RESEARCH_SYSTEM = """You are a travel data collector. Given trip details, decide which tools to call and call them now.

Rules:
- search_flights: only if flying is the right mode (intercontinental, or domestic where a flight saves >2h over train/bus). Use correct IATA codes.
- search_hotels: once for the main destination if check-in/check-out dates are known.
- search_places: 1-2 calls max. Use broad queries: "top attractions and restaurants in <city>" or "street food and nightlife in <city>".
- get_weather_forecast: only if the trip starts within the next 7 days. Skip for future trips.
- Call all applicable tools. Return no text — only tool calls.

Common IATA codes:
London LHR | Paris CDG | Amsterdam AMS | Frankfurt FRA | Madrid MAD | Rome FCO | Berlin BER
New York JFK | Los Angeles LAX | Chicago ORD | Toronto YYZ | São Paulo GRU
Tokyo NRT | Seoul ICN | Singapore SIN | Bangkok BKK | Hong Kong HKG | Dubai DXB
Mumbai BOM | Delhi DEL | Bengaluru BLR | Chennai MAA | Hyderabad HYD | Kolkata CCU
Sydney SYD | Melbourne MEL | Auckland AKL | Cape Town CPT | Nairobi NBO"""


def _build_research_prompt(extraction: ExtractionResult) -> str:
    lines: list[str] = [f"Destination: {extraction.destination}"]
    if extraction.city:
        lines.append(f"City (for weather): {extraction.city}")
    if extraction.country_code:
        lines.append(f"Country code: {extraction.country_code}")
    if extraction.origin_country:
        lines.append(f"Origin country: {extraction.origin_country}")
    if extraction.start_date:
        lines.append(f"Start / check-in date: {extraction.start_date}")
    if extraction.end_date:
        lines.append(f"End / check-out date: {extraction.end_date}")
    if extraction.budget:
        lines.append(f"Budget: {extraction.budget} {extraction.currency}")
    if extraction.num_travelers > 1:
        lines.append(f"Travelers: {extraction.num_travelers}")
    return "\n".join(lines)


def _log_usage(model: str, usage: dict) -> None:
    try:
        from backend.db.database import SessionLocal
        from backend.db.models import ClaudeUsageLog
        with SessionLocal() as session:
            session.add(ClaudeUsageLog(
                model=model,
                input_tokens=usage.get("input_tokens", 0) or 0,
                output_tokens=usage.get("output_tokens", 0) or 0,
                cache_read_tokens=usage.get("cache_read_tokens", 0) or 0,
                cache_creation_tokens=usage.get("cache_creation_tokens", 0) or 0,
            ))
            session.commit()
    except Exception:
        pass


def run_research(extraction: ExtractionResult) -> ResearchEvidence:
    """
    Collect travel data for a trip by calling tools in parallel.

    Uses the fast model once to derive tool call parameters, then fires all
    tool HTTP calls concurrently. Returns ResearchEvidence — no streaming,
    no prose.
    """
    prompt = _build_research_prompt(extraction)

    resp = llm.complete(
        model=LLM_FAST_MODEL,
        system=_RESEARCH_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        tools=TOOL_DEFINITIONS,
        tool_choice="required",
        max_tokens=512,
    )
    _log_usage(LLM_FAST_MODEL, resp["usage"])

    tool_calls = resp.get("tool_calls", [])
    if not tool_calls:
        return ResearchEvidence()

    for tc in tool_calls:
        print(f"🔍 Research: {tc['name']} ← {tc['input']}")

    lock = threading.Lock()
    collected: dict = {}   # hotel_suggestions accumulate here via execute_tool

    def _run(tc: dict) -> tuple[str, str]:
        result = execute_tool(tc["name"], tc["input"], collected=collected, _lock=lock)
        return tc["id"], result

    results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
        for tool_id, result in pool.map(_run, tool_calls):
            results[tool_id] = result

    evidence = ResearchEvidence(
        tools_called=[tc["name"] for tc in tool_calls],
        hotel_suggestions=collected.get("hotel_suggestions", []),
    )

    for tc in tool_calls:
        result = results[tc["id"]]
        name = tc["name"]
        if name == "search_flights":
            evidence.flights = result
        elif name == "search_hotels":
            evidence.hotels = result
        elif name == "search_places":
            evidence.places.append(result)
        elif name == "get_weather_forecast":
            evidence.weather = result

    return evidence
