"""
Route agent — pre-research destination decisions for the pipeline.

Two single-purpose calls, both forced tool calls on the strong model, both
running between extraction and research so no external API fires until the
"where" is fixed:

- derive_route()         — ordered stops for road trips / multi-city trips
                           (temperature 0: same request, same route)
- suggest_destination()  — picks one destination when the user is flexible
                           (default temperature: flexibility invites variety)
"""

from __future__ import annotations

from datetime import date, timedelta

from backend import llm
from backend.agents.models import ExtractionResult, Stop
from backend.config import LLM_MODEL

MAX_STOPS = 5
FUEL_L_PER_100KM = 6.5   # assumed consumption for fuel estimates

_ROUTE_SYSTEM = """You are a route planner for multi-destination trips. Given an origin, trip length, and traveller context, pick the best ordered stops and call save_route.

Rules:
- Max {max_stops} stops. Fewer, longer stays beat many one-night stands — only give a stop 1 night if it is genuinely a short visit en route.
- leg_mode is how the traveller reaches that stop from the previous one (from the origin for the first stop).
- Road trips (own vehicle): every leg_mode is "drive", max 3.5 hours per leg, and the last stop must allow a reasonable drive back to the origin on the final day.
- Multi-city trips: choose per-leg modes — "train" for under ~800 km in regions with good rail, "bus" where rail is poor, "flight" only when overland is impractical (roughly >6h door to door). If the origin is far from the first stop, the first leg may be a "flight". The route does not need to loop back, but the last stop must have a good connection back to the origin.
- For every "flight" leg set from_iata and to_iata (3-letter IATA codes). Leave both empty for all other modes.
- Nights across all stops MUST sum exactly to the number of nights stated.
- Prefer routes that match the stated travel style and budget level.
- travel_hours_from_previous: realistic door-to-door time for the chosen mode.
- approx_km: realistic road/rail distance of each leg in km.
- Road trips: also fill return_leg_km / return_leg_hours (last stop back to the origin) and fuel_price_per_litre (typical current petrol price along the route, in the user's currency). Set all three to 0 for non-road trips."""

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
                            "leg_mode": {
                                "type": "string",
                                "enum": ["drive", "train", "bus", "flight"],
                                "description": "How the traveller reaches this stop from the previous one.",
                            },
                            "travel_hours_from_previous": {"type": "number"},
                            "approx_km": {"type": "number", "description": "Leg distance in km from the previous stop."},
                            "from_iata": {"type": "string", "description": "Departure IATA — flight legs only, else empty."},
                            "to_iata": {"type": "string", "description": "Arrival IATA — flight legs only, else empty."},
                        },
                        "required": ["city", "country_code", "nights", "leg_mode", "travel_hours_from_previous", "approx_km"],
                    },
                },
                "route_label": {
                    "type": "string",
                    "description": 'Concise label, e.g. "Amsterdam → Ghent → Bruges → Amsterdam".',
                },
                "return_leg_km": {"type": "number", "description": "Road trips: km from the last stop back to the origin. 0 otherwise."},
                "return_leg_hours": {"type": "number", "description": "Road trips: driving hours for the return leg. 0 otherwise."},
                "fuel_price_per_litre": {"type": "number", "description": "Road trips: typical petrol price along the route in the user's currency. 0 otherwise."},
            },
            "required": ["stops", "route_label", "return_leg_km", "return_leg_hours", "fuel_price_per_litre"],
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


_SUGGEST_SYSTEM = """You are a travel expert. Given an origin city and exact travel dates, recommend the single best destination to visit during that specific window. The reason MUST reflect conditions during the stated dates (season, weather, events). Respect the stated budget and travel style. Call save_destination with your pick."""

_SUGGEST_TOOL = {
    "type": "function",
    "function": {
        "name": "save_destination",
        "description": "Persist the recommended destination.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": '"City, Country"'},
                "city": {"type": "string", "description": "Main city for weather lookup."},
                "country_code": {"type": "string", "description": "2-letter ISO code."},
                "reason": {
                    "type": "string",
                    "description": "One sentence — what makes it great on those exact dates.",
                },
            },
            "required": ["destination", "city", "country_code", "reason"],
        },
    },
}


def suggest_destination(extraction: ExtractionResult) -> dict:
    """
    Pick a destination for a flexible-destination trip.

    Returns {"destination", "city", "country_code", "reason"} or {} on failure
    (the planner then asks the user, same as EXTRACT_ONLY).
    """
    lines = [f"Origin: {extraction.origin_city}"]
    if extraction.start_date and extraction.end_date:
        lines.append(f"Travel dates: {extraction.start_date} to {extraction.end_date}")
    if extraction.budget:
        lines.append(f"Budget: {extraction.budget} {extraction.currency} per person")
    if extraction.num_travelers > 1:
        lines.append(f"Travelers: {extraction.num_travelers}")
    if extraction.style:
        lines.append(f"Travel style: {extraction.style}")

    try:
        resp = llm.complete(
            model=LLM_MODEL,
            system=_SUGGEST_SYSTEM,
            messages=[{"role": "user", "content": "\n".join(lines)}],
            tools=[_SUGGEST_TOOL],
            tool_choice={"type": "function", "function": {"name": "save_destination"}},
            max_tokens=300,
        )
        _log_usage(LLM_MODEL, resp["usage"])
        if not resp["tool_calls"]:
            return {}
        data = resp["tool_calls"][0]["input"]
        if not data.get("destination"):
            return {}
        print(f"🌍 Destination pick: {data['destination']} — {data.get('reason', '')}")
        return data
    except Exception as exc:
        print(f"suggest_destination error: {exc}")
        return {}


def _fuel_note(extraction: ExtractionResult, stops: list[Stop], data: dict) -> str:
    """
    Deterministic route-cost note: total km (incl. return leg) and fuel
    arithmetic in Python. The LLM supplies distances and the local fuel
    price; the multiplication is ours, so the budget's travel line is
    grounded instead of invented.
    """
    return_km = float(data.get("return_leg_km") or 0)
    return_hours = float(data.get("return_leg_hours") or 0)
    total_km = sum(s.approx_km or 0 for s in stops) + return_km
    if not total_km:
        return ""

    lines = []
    if return_km:
        origin = extraction.origin_city or "the origin"
        lines.append(f"- Return to {origin}: ~{return_km:.0f} km, ~{return_hours:.1f}h drive")
    lines.append(f"Total distance: ~{total_km:.0f} km")

    price = float(data.get("fuel_price_per_litre") or 0)
    if extraction.trip_type == "road_trip" and price > 0:
        litres = total_km / 100 * FUEL_L_PER_100KM
        cost = litres * price
        lines.append(
            f"Fuel estimate (computed): {total_km:.0f} km × {FUEL_L_PER_100KM} L/100km × "
            f"{price:.2f} {extraction.currency}/L ≈ {cost:.0f} {extraction.currency}, plus tolls where applicable. "
            f"Use this as the basis for the travel line in the budget — do not invent a different fuel figure."
        )
    return "\n".join(lines)


def derive_route(extraction: ExtractionResult) -> tuple[list[Stop], str, str]:
    """
    Derive stops for a multi-stop trip.
    Returns (stops_with_dates, route_label, route_note) — route_note carries
    the return leg and the computed fuel estimate for road trips.
    Returns ([], "", "") on failure — the caller falls back to asking the user.
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
            return [], "", ""
        data = resp["tool_calls"][0]["input"]
        stops = [Stop(**s) for s in data.get("stops", []) if isinstance(s, dict) and s.get("city")]
        if not stops:
            return [], "", ""
        if extraction.trip_type == "road_trip":
            # Own vehicle — enforce drive legs regardless of what the model chose
            stops = [s.model_copy(update={"leg_mode": "drive", "from_iata": "", "to_iata": ""}) for s in stops]
        stops = assign_stop_dates(stops, extraction.start_date, extraction.end_date)
        label = data.get("route_label") or " → ".join(s.city for s in stops)
        note = _fuel_note(extraction, stops, data)
        print(f"🗺️  Route: {label} | " + ", ".join(f"{s.city}×{s.nights}n" for s in stops))
        return stops, label, note
    except Exception as exc:
        print(f"route_agent error: {exc}")
        return [], "", ""
