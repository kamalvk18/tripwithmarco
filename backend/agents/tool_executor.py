from backend.tools.flights import search_flights, format_flights_for_marco
from backend.tools.weather import get_weather_forecast, format_weather_for_marco
from backend.tools.hotels import search_hotels, format_hotels_for_marco
from backend.tools.places import search_places, format_places_for_marco
from backend.tools.cache import get_cached, set_cached


def execute_tool(tool_name: str, tool_input: dict, collected: dict | None = None) -> str:
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
        return cached

    try:
        if tool_name == "search_hotels":
            hotels = search_hotels(
                destination=tool_input["destination"],
                check_in_date=tool_input["check_in_date"],
                check_out_date=tool_input["check_out_date"],
            )
            if collected is not None and hotels:
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
            set_cached(tool_name, tool_input, result)
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
            set_cached(tool_name, tool_input, result)
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
            set_cached(tool_name, tool_input, result)
            return result

        elif tool_name == "get_weather_forecast":
            weather_data = get_weather_forecast(
                tool_input["city"],
                tool_input.get("country_code", ""),
            )
            result = format_weather_for_marco(weather_data)
            set_cached(tool_name, tool_input, result)
            return result

        else:
            return f"Unknown tool: {tool_name}"

    except KeyError as e:
        error = f"Tool '{tool_name}' called with missing required input: {e}"
        print(f"⚠️  {error}")
        return error
    except Exception as e:
        error = f"Tool '{tool_name}' encountered an unexpected error: {e}"
        print(f"⚠️  {error}")
        return error
