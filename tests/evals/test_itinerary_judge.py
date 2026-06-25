"""
Itinerary quality evals — use Haiku as a judge to score Marco's output.

NOT run by default. Run explicitly with:
    uv run pytest tests/evals/test_itinerary_judge.py -v
"""

import pytest
from backend.evals.judge import judge_itinerary

pytestmark = pytest.mark.eval

# A realistic, high-quality itinerary that references specific venues and live data
GOOD_ITINERARY = """
# Day 1 — Arrival in Tokyo
**Flight:** Departs London Heathrow at 11:30, arrives Haneda 09:15+1 (JAL JL402, ~€890).
Check into **Shinjuku Granbell Hotel** (€95/night, rated 4.3★, includes breakfast).
Evening: Ramen at **Ichiran Shinjuku** (private booths, ~€12).

# Day 2 — Shibuya & Harajuku
Morning: **Meiji Shrine** (free, arrive by 8am to avoid crowds).
Lunch: **Afuri Harajuku** — yuzu shio ramen (~€14).
Afternoon: Browse **Takeshita Street**, then Shibuya Crossing at dusk.
Dinner: **Gonpachi Nishiazabu** — yakitori, budget ~€30/person.

# Day 3 — Asakusa & Akihabara
Morning: **Senso-ji Temple**, Nakamise shopping street. Arrive before 9am.
Afternoon: **Akihabara** — retro game shops and the Robot Restaurant area.
Dinner: **Tsukiji Outer Market** for sushi (€20-30, arrive by 7pm).

# Day 4 — Day trip to Nikko
Take the **Tobu Nikko Line** (€25 return, 2h). Visit **Tosho-gu Shrine** (€12 entry).
Back by 7pm. Budget dinner at the hotel.

# Day 5 — Shinjuku & departure
Morning: **Shinjuku Gyoen** (€2 entry, best for photos).
Afternoon: last-minute shopping at **Isetan department store**.
Depart from Haneda on the 21:00 flight.

**Budget summary:** Flights €890 | Hotel 4 nights €380 | Food ~€200 | Activities €80 | Transport €120 | **Total ~€1670**
"""

# A vague, generic itinerary that references no real places and ignores live data
VAGUE_ITINERARY = """
# Day 1
Arrive at the airport and check in to your hotel. Rest and recover from the journey.
In the evening, explore the local area and find somewhere to eat.

# Day 2
Visit some famous landmarks in the city. Take lots of photos and enjoy the culture.
Have lunch at a local restaurant and try some traditional food.
In the afternoon, do some shopping or visit a museum.

# Day 3
Take a day trip to a nearby area of interest. This is a great way to see more of the country.
Return in the evening and enjoy your last dinner.

# Day 4
Check out and head to the airport. Have a safe flight home!
"""

REQUEST = "5 days in Tokyo from London, budget €2000, July 2027"


def test_good_itinerary_scores_high():
    scores = judge_itinerary(GOOD_ITINERARY, REQUEST)
    assert scores["coverage"] >= 4,     f"coverage too low: {scores}"
    assert scores["specificity"] >= 4,  f"specificity too low: {scores}"
    assert scores["budget_fit"] >= 3,   f"budget_fit too low: {scores}"
    assert scores["data_usage"] >= 3,   f"data_usage too low: {scores}"


def test_vague_itinerary_scores_low_on_specificity():
    scores = judge_itinerary(VAGUE_ITINERARY, REQUEST)
    assert scores["specificity"] <= 2, (
        f"Expected low specificity for vague itinerary, got {scores['specificity']}\n{scores}"
    )
    assert scores["data_usage"] <= 2, (
        f"Expected low data_usage for generic itinerary, got {scores['data_usage']}\n{scores}"
    )


def test_judge_returns_all_dimensions():
    scores = judge_itinerary(GOOD_ITINERARY, REQUEST)
    for dim in ("coverage", "specificity", "budget_fit", "data_usage"):
        assert dim in scores, f"Missing dimension: {dim}"
        assert 1 <= scores[dim] <= 5, f"{dim} out of range: {scores[dim]}"
    assert isinstance(scores["flags"], list)
