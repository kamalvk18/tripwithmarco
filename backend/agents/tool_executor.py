import time
import contextlib
from datetime import date, timedelta

from backend.tools.flights import search_flights, format_flights_for_marco
from backend.tools.weather import get_weather_forecast, format_weather_for_marco
from backend.tools.hotels import search_hotels, format_hotels_for_marco
from backend.tools.places import search_places, format_places_for_marco
from backend.tools.cache import get_cached, set_cached


def _log_tool_call(tool_name: str, cache_hit: bool, success: bool, duration_ms: int) -> None:
    if success and not cache_hit:
        print(f"✅ {tool_name} completed in {duration_ms}ms")
    elif not success:
        print(f"❌ {tool_name} failed in {duration_ms}ms")
    try:
        from backend.db.database import SessionLocal
        from backend.db.models import ToolCallLog
        with SessionLocal() as session:
            session.add(ToolCallLog(
                tool_name=tool_name,
                cache_hit=cache_hit,
                success=success,
                duration_ms=duration_ms,
            ))
            session.commit()
    except Exception:
        pass


def execute_tool(tool_name: str, tool_input: dict, collected: dict | None = None, _lock=None) -> str:
    """
    Execute a tool by name with given inputs.
    Returns result as a string to send back to Claude.
    Never raises — any error is returned as a string so the agentic loop stays alive.

    collected: optional mutable dict; hotel suggestions are appended under
               collected["hotel_suggestions"] for surfacing booking links in the UI.
    """
    cached = get_cached(tool_name, tool_input)
    if cached is not None:
        print(f"✅ Cache hit: {tool_name}")
        _log_tool_call(tool_name, cache_hit=True, success=True, duration_ms=0)
        return cached

    start = time.monotonic()
    try:
        if tool_name == "search_hotels":
            hotels = search_hotels(
                destination=tool_input["destination"],
                check_in_date=tool_input["check_in_date"],
                check_out_date=tool_input["check_out_date"],
            )
            if collected is not None and hotels:
                with (_lock if _lock is not None else contextlib.nullcontext()):
                    seen = {h["name"] for h in collected.get("hotel_suggestions", [])}
                    new = [
                        {
                            "name": h["name"],
                            "destination": tool_input["destination"],
                            "check_in": tool_input["check_in_date"],
                            "check_out": tool_input["check_out_date"],
                        }
                        for h in hotels[:4] if h["name"] not in seen
                    ]
                    collected.setdefault("hotel_suggestions", []).extend(new)
            result = format_hotels_for_marco(
                hotels,
                tool_input["destination"],
                tool_input["check_in_date"],
                tool_input["check_out_date"],
            )
            if hotels:   # never cache empty results — a transient API glitch would poison the cache for the whole TTL
                set_cached(tool_name, tool_input, result)
            _log_tool_call(tool_name, cache_hit=False, success=True, duration_ms=int((time.monotonic() - start) * 1000))
            return result

        elif tool_name == "search_places":
            places = search_places(
                query=tool_input["query"],
                location=tool_input["location"],
            )
            result = format_places_for_marco(
                places,
                tool_input["query"],
                tool_input["location"],
            )
            if places:
                set_cached(tool_name, tool_input, result)
            _log_tool_call(tool_name, cache_hit=False, success=True, duration_ms=int((time.monotonic() - start) * 1000))
            return result

        elif tool_name == "search_flights":
            currency = tool_input.get("currency", "EUR")
            flights = search_flights(
                origin=tool_input["origin_iata"],
                destination=tool_input["destination_iata"],
                outbound_date=tool_input["outbound_date"],
                return_date=tool_input.get("return_date"),
                currency=currency,
                max_results=5,
            )
            result = format_flights_for_marco(
                flights,
                tool_input["origin_city"],
                tool_input["destination_city"],
                currency=currency,
            )
            if flights:
                set_cached(tool_name, tool_input, result)
            _log_tool_call(tool_name, cache_hit=False, success=True, duration_ms=int((time.monotonic() - start) * 1000))
            return result

        elif tool_name == "get_weather_forecast":
            trip_date_str = tool_input.get("trip_date") or tool_input.get("date")
            if trip_date_str:
                try:
                    trip_date = date.fromisoformat(trip_date_str)
                    if trip_date > date.today() + timedelta(days=7):
                        return (
                            "Weather forecasts beyond 7 days are unreliable. "
                            "Use your knowledge of typical seasonal weather for this destination instead. "
                            "Do not retry this tool call."
                        )
                except ValueError:
                    pass
            weather_data = get_weather_forecast(
                tool_input["city"],
                tool_input.get("country_code", ""),
            )
            result = format_weather_for_marco(weather_data)
            set_cached(tool_name, tool_input, result)
            _log_tool_call(tool_name, cache_hit=False, success=True, duration_ms=int((time.monotonic() - start) * 1000))
            return result

        else:
            return f"Unknown tool: {tool_name}"

    except KeyError as e:
        _log_tool_call(tool_name, cache_hit=False, success=False, duration_ms=int((time.monotonic() - start) * 1000))
        print(f"⚠️  Tool '{tool_name}' missing required input: {e}")
        return f"Tool '{tool_name}' was called with a missing required field. Do not retry."
    except Exception as e:
        _log_tool_call(tool_name, cache_hit=False, success=False, duration_ms=int((time.monotonic() - start) * 1000))
        # Log the real error server-side; never return raw exception strings to Claude
        # — HTTP library errors can include API keys embedded in URL query params.
        print(f"⚠️  Tool '{tool_name}' error: {e}")
        return f"Tool '{tool_name}' failed to fetch data. Do not retry this search."
