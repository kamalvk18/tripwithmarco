"""
Pipeline quality evals — run the real agentic loop and judge Marco's actual output.

External APIs (SerpApi, OpenWeather) are mocked with realistic formatted strings
so the eval doesn't burn API quota. Claude Sonnet runs for real.

NOT run by default. Run explicitly with:
    uv run python -m pytest tests/evals/test_pipeline_quality.py -v
"""

import pytest
from unittest.mock import patch
from backend.agents.planning_agent import chat
from backend.evals.judge import judge_itinerary

pytestmark = pytest.mark.eval

# ── Realistic mock tool outputs (match exact format of format_*_for_marco) ────

_MOCK_FLIGHTS = """Live flight prices from London to Tokyo (EUR):
1. Japan Airlines — €780 | Direct | 2027-07-01 11:30→09:15 | 11h 45m
2. British Airways + Japan Airlines — €650 | 1 stop | 2027-07-01 09:00→12:30 | 14h 30m (via Helsinki)
3. ANA — €820 | Direct | 2027-07-01 13:15→11:30 | 12h 15m

💰 Cheapest: €650 — British Airways + Japan Airlines (1 stop)
⚡ Fastest: 11h 45m — Japan Airlines (€780)"""

_MOCK_HOTELS = """Hotels in Tokyo, Japan (2027-07-01 → 2027-07-06):
1. Shinjuku Granbell Hotel [Hotel] — €95/night | Total: €475 | ⭐ 4.3 (1,240 reviews)
   Free Wi-Fi, Air conditioning, Restaurant, Fitness center, Bar
2. Citadines Shinjuku Tokyo [Serviced Apartment] — €80/night | Total: €400 | ⭐ 4.1 (856 reviews)
   Free Wi-Fi, Kitchenette, Air conditioning, Laundry facilities
3. Sotetsu Fresa Inn Roppongi [Hotel] — €68/night | Total: €340 | ⭐ 3.9 (622 reviews)
   Free Wi-Fi, Air conditioning, 24-hour front desk

💰 Cheapest: Sotetsu Fresa Inn Roppongi — €68/night
⭐ Top rated: Shinjuku Granbell Hotel — 4.3 (€95/night)"""

_MOCK_PLACES = """Results for 'top attractions in Tokyo' in Tokyo, Japan:
1. Senso-ji Temple [Tourist attraction] ⭐ 4.7 (42,300 reviews)
   🕐 Open 24 hours
   📍 2-3-1 Asakusa, Taito City, Tokyo
2. Shinjuku Gyoen National Garden [Park] ⭐ 4.6 (18,500 reviews) | ¥500
   🕐 9:00 AM – 4:30 PM
   📍 11 Naitomachi, Shinjuku City, Tokyo
3. TeamLab Planets [Museum] ⭐ 4.5 (8,200 reviews) | ¥3,200
   🕐 9:00 AM – 10:00 PM
   📍 6-1-16 Toyosu, Koto City, Tokyo
4. Meiji Shrine [Shrine] ⭐ 4.6 (31,000 reviews)
   🕐 Sunrise – Sunset
   📍 1-1 Yoyogikamizonocho, Shibuya City, Tokyo
5. Shibuya Crossing [Landmark] ⭐ 4.5 (28,000 reviews)
   🕐 Open 24 hours
   📍 Shibuya City, Tokyo"""

_MOCK_WEATHER = """Weather forecast for Tokyo:
  2027-07-01: Sunny, 24°C - 32°C
  2027-07-02: Partly Cloudy, 25°C - 31°C
  2027-07-03: Sunny, 25°C - 33°C
  2027-07-04: Humid, 26°C - 32°C
  2027-07-05: Partly Cloudy, 24°C - 30°C
  2027-07-06: Sunny, 24°C - 31°C"""


def _mock_execute_tool(tool_name: str, tool_input: dict, collected=None) -> str:
    if tool_name == "search_flights":
        return _MOCK_FLIGHTS
    if tool_name == "search_hotels":
        return _MOCK_HOTELS
    if tool_name == "search_places":
        return _MOCK_PLACES
    if tool_name == "get_weather_forecast":
        return _MOCK_WEATHER
    return f"No mock data for tool: {tool_name}"


# ── Trip cases — mirror the prompt buildPrompt() produces in PlanTrip.jsx ─────

TRIP_CASES = [
    {
        "id": "tokyo_midrange",
        "messages": [{
            "role": "user",
            "content": (
                "Plan my trip with these details: "
                "Destination: Tokyo, Japan. "
                "Travelling from: London. "
                "Dates: 2027-07-01 to 2027-07-06 (5 nights). "
                "Budget: 2000 EUR per person. "
                "Travel style: Mid-range."
            ),
        }],
        "thresholds": {
            "coverage": 4,
            "specificity": 4,
            "budget_fit": 3,
            "data_usage": 4,  # real Marco explicitly references fetched prices
        },
    },
]


@pytest.mark.parametrize("case", TRIP_CASES, ids=[c["id"] for c in TRIP_CASES])
def test_marco_itinerary_quality(case):
    with patch("backend.agents.planning_agent.execute_tool", side_effect=_mock_execute_tool):
        response = "".join(chat(case["messages"]))

    assert response, "Marco returned an empty response"

    scores = judge_itinerary(response, case["messages"][0]["content"])
    thresholds = case["thresholds"]

    failures = [
        f"{dim}: expected >={threshold}, got {scores.get(dim)} — flags: {scores.get('flags', [])}"
        for dim, threshold in thresholds.items()
        if scores.get(dim, 0) < threshold
    ]
    assert not failures, "Quality thresholds not met:\n" + "\n".join(failures)
