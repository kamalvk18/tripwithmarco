import os
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()


def search_flights(
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str = None,
    currency: str = "EUR",
    max_results: int = 5
) -> list[dict]:
    """
    Search for flights using SerpApi Google Flights.
    origin/destination: IATA codes (e.g. "AMS", "MUC")
    outbound_date: YYYY-MM-DD
    return_date: YYYY-MM-DD (None for one-way)
    """

    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is not set — flight search skipped")
        return []

    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": outbound_date,
        "currency": currency,
        "type": "1" if return_date else "2",  # 1 = round trip, 2 = one way
        "api_key": api_key,
    }

    if return_date:
        params["return_date"] = return_date

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            print(f"SerpApi flight error: {results['error']}")
            return []

        # SerpApi returns best_flights and other_flights
        flights = results.get("best_flights", []) + results.get("other_flights", [])
        return parse_flights(flights[:max_results])

    except Exception as e:
        print(f"SerpApi flight search error: {e}")
        return []


def parse_flights(raw_flights: list) -> list[dict]:
    """Parse SerpApi Google Flights response into clean dicts."""

    parsed = []

    for flight in raw_flights:
        try:
            legs = flight.get("flights", [])
            if not legs:
                continue

            first_leg = legs[0]
            last_leg = legs[-1]

            departure = first_leg["departure_airport"]
            arrival = last_leg["arrival_airport"]

            # Total duration in hours and minutes
            total_minutes = flight.get("total_duration", 0)
            duration_str = f"{total_minutes // 60}h {total_minutes % 60}m"

            # Stops
            layovers = flight.get("layovers", [])
            stops = len(layovers)
            stop_label = "Direct" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
            layover_cities = [l["name"].split(" Airport")[0] for l in layovers]

            # Airlines — deduplicate if same airline on all legs
            airlines = list(dict.fromkeys([l["airline"] for l in legs]))
            airline_str = " + ".join(airlines)

            # Warnings
            warnings = []
            for leg in legs:
                if leg.get("often_delayed_by_over_30_min"):
                    warnings.append(f"{leg['airline']} {leg['flight_number']} often delayed")
                if leg.get("overnight"):
                    warnings.append("overnight flight")

            price = flight.get("price")
            if not price:
                # Skip flights where SerpApi returns null or 0 — unusable for planning
                continue

            parsed.append({
                "airline": airline_str,
                "airline_logo": first_leg.get("airline_logo"),
                "price": price,
                "price_label": None,  # set by format_flights_for_marco once currency is known
                "from": departure["id"],
                "to": arrival["id"],
                "departure_time": departure["time"],
                "arrival_time": arrival["time"],
                "duration": duration_str,
                "total_minutes": total_minutes,
                "stops": stops,
                "stop_label": stop_label,
                "layover_cities": layover_cities,
                "warnings": warnings,
                "type": flight.get("type", "One way"),
            })

        except (KeyError, IndexError) as e:
            print(f"Error parsing flight: {e}")
            continue

    return parsed


_CURRENCY_SYMBOLS = {
    "EUR": "€", "USD": "$", "GBP": "£", "JPY": "¥", "INR": "₹",
    "AUD": "A$", "CAD": "C$", "SGD": "S$", "CHF": "CHF ", "CNY": "¥",
}


def _fmt_price(amount: int | float, currency: str) -> str:
    symbol = _CURRENCY_SYMBOLS.get(currency.upper(), f"{currency} ")
    return f"{symbol}{amount:,.0f}"


def format_flights_for_marco(
    flights: list[dict],
    origin_city: str,
    destination_city: str,
    currency: str = "EUR",
) -> str:
    """Format parsed flights into a string Marco can use naturally."""

    if not flights:
        return f"No flights found from {origin_city} to {destination_city}."

    lines = [f"Live flight prices from {origin_city} to {destination_city} ({currency}):"]

    for i, f in enumerate(flights, 1):
        dep_time = f["departure_time"].split(" ")[-1][:5]
        arr_time = f["arrival_time"].split(" ")[-1][:5]
        dep_date = f["departure_time"].split(" ")[0]
        price_str = _fmt_price(f["price"], currency)

        line = (
            f"{i}. {f['airline']} — {price_str} | "
            f"{f['stop_label']} | {dep_date} {dep_time}→{arr_time} | "
            f"{f['duration']}"
        )

        if f["layover_cities"]:
            line += f" (via {', '.join(f['layover_cities'])})"

        if f["warnings"]:
            line += f" ⚠️ {', '.join(f['warnings'])}"

        lines.append(line)

    cheapest = min(flights, key=lambda x: x["price"])
    fastest = min(flights, key=lambda x: x["total_minutes"])

    lines.append(f"\n💰 Cheapest: {_fmt_price(cheapest['price'], currency)} — {cheapest['airline']} ({cheapest['stop_label']})")

    if fastest["price"] != cheapest["price"]:
        lines.append(f"⚡ Fastest: {fastest['duration']} — {fastest['airline']} ({_fmt_price(fastest['price'], currency)})")

    return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    flights = search_flights(
        origin="AMS",
        destination="MUC",
        outbound_date="2026-05-19",
        return_date="2026-05-24"
    )
    print(format_flights_for_marco(flights, "Amsterdam", "Munich"))