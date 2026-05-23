import os
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()


def search_places(
    query: str,
    location: str,
    max_results: int = 5
) -> list[dict]:
    """
    Search for restaurants, attractions, or activities using SerpApi Google Local.
    query: what to find (e.g. "traditional restaurants", "museums", "things to do")
    location: city or area (e.g. "Kraków, Poland")
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is not set — places search skipped")
        return []

    params = {
        "engine": "google_local",
        "q": query,
        "location": location,
        "api_key": api_key,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            print(f"SerpApi places error: {results['error']}")
            return []

        places = results.get("local_results", [])
        return parse_places(places[:max_results])
    except Exception as e:
        print(f"Places search error: {e}")
        return []


def parse_places(raw_places: list) -> list[dict]:
    parsed = []
    for place in raw_places:
        try:
            parsed.append({
                "name": place.get("title", "Unknown"),
                "rating": place.get("rating"),
                "reviews": place.get("reviews"),
                "type": place.get("type", ""),
                "address": place.get("address", ""),
                "hours": place.get("hours", ""),
                "price": place.get("price", ""),
                "description": place.get("description", ""),
            })
        except Exception:
            continue
    return parsed


def format_places_for_marco(
    places: list[dict],
    query: str,
    location: str
) -> str:
    if not places:
        return f"No results for '{query}' in {location}."

    lines = [f"Results for '{query}' in {location}:"]

    for i, p in enumerate(places, 1):
        rating_str = f" ⭐ {p['rating']}" if p['rating'] else ""
        reviews_str = f" ({p['reviews']} reviews)" if p['reviews'] else ""
        price_str = f" | {p['price']}" if p['price'] else ""
        type_str = f" [{p['type']}]" if p['type'] else ""

        line = f"{i}. {p['name']}{type_str}{rating_str}{reviews_str}{price_str}"
        if p['hours']:
            line += f"\n   🕐 {p['hours']}"
        if p['address']:
            line += f"\n   📍 {p['address']}"
        if p['description']:
            line += f"\n   {p['description'][:120]}"
        lines.append(line)

    return "\n".join(lines)


if __name__ == "__main__":
    places = search_places("traditional Polish restaurants", "Kraków, Poland")
    print(format_places_for_marco(places, "traditional Polish restaurants", "Kraków, Poland"))
