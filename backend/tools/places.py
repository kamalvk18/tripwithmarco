import os
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()


def _location_fallbacks(location: str) -> list[str]:
    """Return progressively broader versions of a location string.
    'Hanle, Ladakh, India' → ['Hanle, Ladakh, India', 'Ladakh, India', 'India']
    """
    parts = [p.strip() for p in location.split(",")]
    return [", ".join(parts[i:]) for i in range(len(parts))]


def search_places(
    query: str,
    location: str,
    max_results: int = 5
) -> list[dict]:
    """
    Search for restaurants, attractions, or activities using SerpApi Google Local.
    Retries with progressively broader locations on unsupported-location errors
    so a single Claude tool call doesn't fail silently on remote/obscure places.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is not set — places search skipped")
        return []

    for candidate in _location_fallbacks(location):
        if candidate != location:
            print(f"Places: '{location}' unsupported, retrying with '{candidate}'")

        params = {
            "engine": "google_local",
            "q": query,
            "location": candidate,
            "api_key": api_key,
        }

        try:
            search = GoogleSearch(params)
            results = search.get_dict()

            if "error" in results:
                error_msg = results["error"]
                if "unsupported" in error_msg.lower():
                    continue  # try next broader location without surfacing error
                print(f"SerpApi places error: {error_msg}")
                return []

            places = results.get("local_results", [])
            return parse_places(places[:max_results])
        except Exception as e:
            print(f"Places search error for '{candidate}': {e}")
            return []

    print(f"Places: exhausted location fallbacks for '{location}'")
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
        return (
            f"No places data available for '{query}' near {location}. "
            "The location may be too remote or unrecognised by the search service. "
            "Do not retry this search — proceed with your itinerary using general knowledge for this area."
        )

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
