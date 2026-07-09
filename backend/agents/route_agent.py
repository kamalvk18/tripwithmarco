"""
Route agent — derives an ordered list of stops for multi-destination trips.

Runs between extraction and research, only when the trip is a road trip or
multi-city trip and the user did not name the stops themselves. One forced
tool call on the strong model at temperature 0: route quality is the product,
but the same request should always yield the same route.

The output feeds the deterministic per-stop research fan-out — no external
API is called until the route is fixed.
"""

from __future__ import annotations

from datetime import date, timedelta

from backend import llm
from backend.agents.models import ExtractionResult, Stop
from backend.config import LLM_MODEL

MAX_STOPS = 5

_ROUTE_SYSTEM = """You are a route planner for multi-destination trips. Given an origin, trip length, and traveller context, pick the best ordered stops and call save_route.

Rules:
- Max {max_stops} stops. Fewer, longer stays beat many one-night stands — only give a stop 1 night if it is genuinely a short visit en route.
- Road trips: max 3.5 hours driving per leg, and the last stop must allow a reasonable drive back to the origin on the final day.
- Nights across all stops MUST sum exactly to the number of nights stated.
- Prefer routes that match the stated travel style and budget level.
- drive_hours_from_previous: realistic driving time from the previous stop (from the origin for the first stop)."""

_ROUTE_TOOL = {
    "type": "function",
    "function": {
        "name": "save_route",
        "description": "Persist the chosen route.",
        "parameters": {
            "type": "object",
            "properties": {
                "stops": {
                    "type": "array",
                    "maxItems": MAX_STOPS,
                    "items": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string"},
                            "country_code": {"type": "string", "description": "2-letter ISO"},
                            "nights": {"type": "integer", "minimum": 1},
                            "drive_hours_from_previous": {"type": "number"},
                        },
                        "required": ["city", "country_code", "nights", "drive_hours_from_previous"],
                    },
                },
                "route_label": {
                    "type": "string",
                    "description": 'Concise label, e.g. "Amsterdam → Ghent → Bruges → Amsterdam".',
                },
            },
            "required": ["stops", "route_label"],
        },
    },
}


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


def assign_stop_dates(stops: list[Stop], start_date: str, end_date: str) -> list[Stop]:
    """Deterministically assign check-in/check-out dates from cumulative nights.

    If the stops' nights overshoot the trip window, the tail stops are clamped;
    if they undershoot, the last stop absorbs the remaining nights. The result
    always spans exactly [start_date, end_date].
    """
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (ValueError, TypeError):
        return stops

    total_nights = (end - start).days
    if total_nights < 1 or not stops:
        return stops

    # Normalise nights to sum to the trip window
    nights = [max(1, s.nights) for s in stops]
    while sum(nights) > total_nights and len(nights) > 1:
        # Drop nights from (or remove) tail stops until the route fits
        if nights[-1] > 1:
            nights[-1] -= 1
        else:
            nights.pop()
    stops = stops[:len(nights)]
    nights[-1] += total_nights - sum(nights)   # last stop absorbs any remainder

    cursor = start
    dated: list[Stop] = []
    for stop, n in zip(stops, nights):
        check_out = cursor + timedelta(days=n)
        dated.append(stop.model_copy(update={
            "nights": n,
            "check_in": cursor.isoformat(),
            "check_out": check_out.isoformat(),
        }))
        cursor = check_out
    return dated


def derive_route(extraction: ExtractionResult) -> tuple[list[Stop], str]:
    """
    Derive stops for a multi-stop trip. Returns (stops_with_dates, route_label).
    Returns ([], "") on failure — the caller falls back to single-destination flow.
    """
    num_days = extraction.num_days
    nights = (num_days - 1) if num_days else None

    lines = [f"Origin: {extraction.origin_city or extraction.destination}"]
    if extraction.trip_type == "road_trip":
        lines.append("Trip type: road trip" + (" (own vehicle)" if extraction.has_own_vehicle else ""))
    else:
        lines.append("Trip type: multi-city")
    if nights:
        lines.append(f"Nights available: {nights} ({extraction.start_date} to {extraction.end_date})")
    if extraction.budget:
        lines.append(f"Budget: {extraction.budget} {extraction.currency} per person")
    if extraction.num_travelers > 1:
        lines.append(f"Travelers: {extraction.num_travelers}")
    if extraction.style:
        lines.append(f"Travel style: {extraction.style}")

    try:
        resp = llm.complete(
            model=LLM_MODEL,
            system=_ROUTE_SYSTEM.format(max_stops=MAX_STOPS),
            messages=[{"role": "user", "content": "\n".join(lines)}],
            tools=[_ROUTE_TOOL],
            tool_choice={"type": "function", "function": {"name": "save_route"}},
            max_tokens=600,
            temperature=0,
        )
        _log_usage(LLM_MODEL, resp["usage"])
        if not resp["tool_calls"]:
            return [], ""
        data = resp["tool_calls"][0]["input"]
        stops = [Stop(**s) for s in data.get("stops", []) if isinstance(s, dict) and s.get("city")]
        if not stops:
            return [], ""
        stops = assign_stop_dates(stops, extraction.start_date, extraction.end_date)
        label = data.get("route_label") or " → ".join(s.city for s in stops)
        print(f"🗺️  Route: {label} | " + ", ".join(f"{s.city}×{s.nights}n" for s in stops))
        return stops, label
    except Exception as exc:
        print(f"route_agent error: {exc}")
        return [], ""
