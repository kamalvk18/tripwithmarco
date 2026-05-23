import os
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()


def search_hotels(
    destination: str,
    check_in_date: str,
    check_out_date: str,
    currency: str = "EUR",
    max_results: int = 5
) -> list[dict]:
    """
    Search for hotels using SerpApi Google Hotels.
    destination: city or area name (e.g. "Kraków, Poland")
    check_in_date / check_out_date: YYYY-MM-DD
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is not set — hotel search skipped")
        return []

    params = {
        "engine": "google_hotels",
        "q": f"hotels in {destination}",
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "adults": "1",
        "currency": currency,
        "api_key": api_key,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            print(f"SerpApi hotel error: {results['error']}")
            return []

        hotels = results.get("properties", [])
        return parse_hotels(hotels[:max_results])
    except Exception as e:
        print(f"Hotel search error: {e}")
        return []


def parse_hotels(raw_hotels: list) -> list[dict]:
    parsed = []
    for hotel in raw_hotels:
        try:
            rate = hotel.get("rate_per_night", {})
            total = hotel.get("total_rate", {})
            parsed.append({
                "name": hotel.get("name", "Unknown"),
                "price_per_night": rate.get("lowest", "N/A"),
                "price_per_night_value": rate.get("extracted_lowest", 0),
                "total_price": total.get("lowest", "N/A"),
                "rating": hotel.get("overall_rating"),
                "reviews": hotel.get("reviews"),
                "type": hotel.get("type", "Hotel"),
                "amenities": hotel.get("amenities", [])[:5],
            })
        except Exception:
            continue
    return parsed


def format_hotels_for_marco(
    hotels: list[dict],
    destination: str,
    check_in: str,
    check_out: str
) -> str:
    if not hotels:
        return f"No hotels found in {destination} for {check_in} to {check_out}."

    lines = [f"Hotels in {destination} ({check_in} → {check_out}):"]

    for i, h in enumerate(hotels, 1):
        rating_str = f" | ⭐ {h['rating']}" if h['rating'] else ""
        reviews_str = f" ({h['reviews']} reviews)" if h['reviews'] else ""
        line = f"{i}. {h['name']} [{h['type']}] — {h['price_per_night']}/night | Total: {h['total_price']}{rating_str}{reviews_str}"
        if h['amenities']:
            line += f"\n   {', '.join(h['amenities'])}"
        lines.append(line)

    priced = [h for h in hotels if h['price_per_night_value']]
    if priced:
        cheapest = min(priced, key=lambda x: x['price_per_night_value'])
        best_rated = max(
            (h for h in hotels if h['rating']),
            key=lambda x: x['rating'],
            default=None
        )
        lines.append(f"\n💰 Cheapest: {cheapest['name']} — {cheapest['price_per_night']}/night")
        if best_rated and best_rated['name'] != cheapest['name']:
            lines.append(f"⭐ Top rated: {best_rated['name']} — {best_rated['rating']} ({best_rated['price_per_night']}/night)")

    return "\n".join(lines)


if __name__ == "__main__":
    hotels = search_hotels("Kraków, Poland", "2026-05-01", "2026-05-04")
    print(format_hotels_for_marco(hotels, "Kraków", "2026-05-01", "2026-05-04"))
