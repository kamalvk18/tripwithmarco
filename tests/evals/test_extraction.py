"""
Extraction evals — test extract_trip_details() accuracy with real Haiku calls.

NOT run by default. Run explicitly with:
    uv run pytest tests/evals/test_extraction.py -v
"""

import pytest
from backend.agents.planning_agent import extract_trip_details

pytestmark = pytest.mark.eval

CASES = [
    {
        "id": "basic_international",
        "messages": [
            {"role": "user", "content": (
                "Plan 5 days in Tokyo, Japan from London. "
                "Dates: 2027-07-01 to 2027-07-06. Budget €2000 per person."
            )},
            {"role": "assistant", "content": (
                "Here's your Tokyo itinerary!\n\nDay 1: Arrival\nDay 2: Explore Shibuya"
            )},
        ],
        "expect": {
            "destination": "Tokyo, Japan",
            "city": "Tokyo",
            "country_code": "JP",
            "origin_country": "United Kingdom",
            "is_domestic": False,
            "start_date": "2027-07-01",
            "end_date": "2027-07-06",
            "budget": 2000.0,
        },
    },
    {
        "id": "domestic_india",
        "messages": [
            {"role": "user", "content": (
                "Plan a 3-day trip from Mumbai, India to Goa, India. "
                "Dates: 2027-09-15 to 2027-09-18. Budget ₹20000."
            )},
        ],
        "expect": {
            "destination": "Goa, India",
            "city": "Goa",
            "country_code": "IN",
            "origin_country": "India",
            "is_domestic": True,
            "start_date": "2027-09-15",
            "end_date": "2027-09-18",
            "budget": 20000.0,
        },
    },
    {
        "id": "budget_update",
        "messages": [
            {"role": "user", "content": (
                "Plan a trip to Paris, France from Berlin. "
                "Dates: 2027-10-03 to 2027-10-07. My budget is €1000."
            )},
            {"role": "assistant", "content": "Here's a plan for €1000..."},
            {"role": "user", "content": "Actually I got a bonus — my budget is now €1500."},
            {"role": "assistant", "content": "Great, here's an updated plan for €1500..."},
        ],
        "expect": {
            "destination": "Paris, France",
            "city": "Paris",
            "country_code": "FR",
            "origin_country": "Germany",
            "is_domestic": False,
            "start_date": "2027-10-03",
            "end_date": "2027-10-07",
            "budget": 1500.0,
        },
    },
    {
        "id": "southeast_asia",
        "messages": [
            {"role": "user", "content": (
                "7 days in Bali, Indonesia from Sydney, Australia. "
                "Dates 2027-08-10 to 2027-08-17. Budget AUD 3000."
            )},
        ],
        "expect": {
            "destination": "Bali, Indonesia",
            "city": "Denpasar",
            "country_code": "ID",
            "origin_country": "Australia",
            "is_domestic": False,
            "start_date": "2027-08-10",
            "end_date": "2027-08-17",
            "budget": 3000.0,
        },
    },
]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_extract_trip_details(case):
    result = extract_trip_details(case["messages"])
    for field, expected in case["expect"].items():
        actual = result.get(field)
        assert actual == expected, (
            f"[{case['id']}] '{field}': expected {expected!r}, got {actual!r}\n"
            f"Full result: {result}"
        )
