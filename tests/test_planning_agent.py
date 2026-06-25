"""
Tests for pure (no-API) functions in planning_agent.py.
Run with: uv run pytest tests/
"""

import pytest
from datetime import date, timedelta
from unittest.mock import patch

from backend.agents.planning_agent import (
    extract_all_days,
    extract_day_section,
    extract_itinerary,
    get_trip_day,
)
from backend.agents.models import ExtractionResult
from backend.agents.orchestrator import WorkflowType, _has_existing_itinerary, _route, _same_trip


# ── extract_all_days ──────────────────────────────────────────────────────────

SAMPLE_ITINERARY = """
# Day 1 — Arrival & Acclimatisation
Morning: land, rest, hydrate.

## Day 2: Old Town Exploration
Visit the castle and eat pierogi.

**Day 3 — Mountains**
Hike to the ridge.

Day 4: Beach day
Relax.
"""

MINIMAL_ITINERARY = """
Day 1: Start
Content here.

Day 2: Middle
More content.
"""


class TestExtractAllDays:
    def test_returns_correct_number_of_days(self):
        days = extract_all_days(SAMPLE_ITINERARY)
        assert len(days) == 4

    def test_day_numbers_are_sequential(self):
        days = extract_all_days(SAMPLE_ITINERARY)
        assert [d["day"] for d in days] == [1, 2, 3, 4]

    def test_titles_are_cleaned_of_markdown(self):
        days = extract_all_days(SAMPLE_ITINERARY)
        # Should not contain # or ** markers
        for day in days:
            assert "#" not in day["title"]
            assert "**" not in day["title"]

    def test_content_contains_body_text(self):
        days = extract_all_days(SAMPLE_ITINERARY)
        assert "pierogi" in days[1]["content"]

    def test_empty_string_returns_empty_list(self):
        assert extract_all_days("") == []

    def test_no_day_headings_returns_empty_list(self):
        assert extract_all_days("Just some random text with no day headings.") == []

    def test_duplicate_day_numbers_deduplicated(self):
        itinerary = "Day 1: First\ncontent\n\nDay 1: Duplicate\nshould be ignored\n\nDay 2: Second\nok"
        days = extract_all_days(itinerary)
        assert len(days) == 2
        assert days[0]["day"] == 1
        assert days[1]["day"] == 2

    def test_minimal_itinerary(self):
        days = extract_all_days(MINIMAL_ITINERARY)
        assert len(days) == 2
        assert days[0]["day"] == 1
        assert days[1]["day"] == 2


# ── extract_day_section ───────────────────────────────────────────────────────

class TestExtractDaySection:
    def test_extracts_correct_day(self):
        section = extract_day_section(SAMPLE_ITINERARY, 2)
        assert "pierogi" in section

    def test_does_not_bleed_into_next_day(self):
        section = extract_day_section(SAMPLE_ITINERARY, 2)
        assert "Hike to the ridge" not in section

    def test_returns_empty_string_for_missing_day(self):
        section = extract_day_section(SAMPLE_ITINERARY, 99)
        assert section == ""

    def test_last_day_captures_to_end(self):
        section = extract_day_section(SAMPLE_ITINERARY, 4)
        assert "Relax" in section


# ── extract_itinerary ─────────────────────────────────────────────────────────

class TestExtractItinerary:
    def test_finds_first_assistant_message_with_day1(self):
        messages = [
            {"role": "user", "content": "Plan my trip"},
            {"role": "assistant", "content": "Sure! Day 1: Arrival\nDay 2: Explore"},
            {"role": "user", "content": "Can you add more detail?"},
            {"role": "assistant", "content": "Day 1 expanded..."},
        ]
        itinerary = extract_itinerary(messages)
        # Should return the LAST assistant message with "day 1" (reversed search)
        assert "expanded" in itinerary

    def test_returns_empty_string_if_no_itinerary(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! Tell me your destination."},
        ]
        assert extract_itinerary(messages) == ""

    def test_case_insensitive_day_match(self):
        messages = [
            {"role": "assistant", "content": "DAY 1: Something"},
        ]
        assert extract_itinerary(messages) != ""

    def test_empty_messages_returns_empty(self):
        assert extract_itinerary([]) == ""


# ── get_trip_day ──────────────────────────────────────────────────────────────

class TestGetTripDay:
    def test_upcoming_trip(self):
        future_start = (date.today() + timedelta(days=5)).isoformat()
        future_end = (date.today() + timedelta(days=10)).isoformat()
        result = get_trip_day(future_start, future_end)
        assert result["status"] == "upcoming"
        assert result["days_until"] == 5

    def test_active_trip_first_day(self):
        today = date.today()
        end = (today + timedelta(days=6)).isoformat()
        result = get_trip_day(today.isoformat(), end)
        assert result["status"] == "active"
        assert result["day_number"] == 1
        assert result["total_days"] == 7

    def test_active_trip_mid_trip(self):
        start = (date.today() - timedelta(days=3)).isoformat()
        end = (date.today() + timedelta(days=3)).isoformat()
        result = get_trip_day(start, end)
        assert result["status"] == "active"
        assert result["day_number"] == 4

    def test_past_trip(self):
        past_start = (date.today() - timedelta(days=10)).isoformat()
        past_end = (date.today() - timedelta(days=5)).isoformat()
        result = get_trip_day(past_start, past_end)
        assert result["status"] == "past"

    def test_invalid_dates_return_unknown(self):
        result = get_trip_day("not-a-date", "also-bad")
        assert result["status"] == "unknown"

    def test_empty_dates_return_unknown(self):
        result = get_trip_day("", "")
        assert result["status"] == "unknown"

    def test_single_day_trip(self):
        today = date.today().isoformat()
        result = get_trip_day(today, today)
        assert result["status"] == "active"
        assert result["day_number"] == 1
        assert result["total_days"] == 1


# ── Orchestrator routing ──────────────────────────────────────────────────────

ITINERARY_MESSAGES = [
    {"role": "user", "content": "Plan a trip to Tokyo"},
    {"role": "assistant", "content": (
        "# Day 1 — Arrival\nCheck in and rest.\n\n"
        "# Day 2 — Shibuya\nVisit the crossing.\n\n"
        "# Day 3 — Departure\nHead to the airport."
    )},
]

EMPTY_MESSAGES = [
    {"role": "user", "content": "Plan a trip to Tokyo"},
]

_COMPLETE = ExtractionResult(destination="Tokyo", start_date="2026-08-01", end_date="2026-08-05")
_INCOMPLETE = ExtractionResult(destination="Tokyo")  # no dates


class TestOrchestratorRouting:
    def test_extract_only_when_dates_missing(self):
        assert _route(_INCOMPLETE, EMPTY_MESSAGES, None) == WorkflowType.EXTRACT_ONLY

    def test_full_plan_when_no_itinerary_yet(self):
        assert _route(_COMPLETE, EMPTY_MESSAGES, None) == WorkflowType.FULL_PLAN

    def test_incremental_when_itinerary_exists_and_same_trip(self):
        trip_data = {"destination": "Tokyo, Japan", "start_date": "2026-08-01"}
        assert _route(_COMPLETE, ITINERARY_MESSAGES, trip_data) == WorkflowType.INCREMENTAL

    def test_full_plan_when_destination_changed(self):
        trip_data = {"destination": "Osaka, Japan", "start_date": "2026-08-01"}
        assert _route(_COMPLETE, ITINERARY_MESSAGES, trip_data) == WorkflowType.FULL_PLAN

    def test_full_plan_when_trip_data_absent(self):
        # No trip_data means _same_trip returns False → FULL_PLAN even with itinerary
        assert _route(_COMPLETE, ITINERARY_MESSAGES, None) == WorkflowType.FULL_PLAN

    def test_has_existing_itinerary_true(self):
        assert _has_existing_itinerary(ITINERARY_MESSAGES) is True

    def test_has_existing_itinerary_false(self):
        assert _has_existing_itinerary(EMPTY_MESSAGES) is False

    def test_same_trip_matches_partial_destination(self):
        # Saved: "Tokyo, Japan", extracted: "Tokyo" — should match
        extraction = ExtractionResult(destination="Tokyo", start_date="2026-08-01", end_date="2026-08-05")
        trip_data = {"destination": "Tokyo, Japan", "start_date": "2026-08-01"}
        assert _same_trip(extraction, trip_data) is True

    def test_same_trip_rejects_different_destination(self):
        extraction = ExtractionResult(destination="Osaka", start_date="2026-08-01", end_date="2026-08-05")
        trip_data = {"destination": "Tokyo, Japan", "start_date": "2026-08-01"}
        assert _same_trip(extraction, trip_data) is False

    def test_same_trip_rejects_different_start_date(self):
        extraction = ExtractionResult(destination="Tokyo", start_date="2026-09-01", end_date="2026-09-05")
        trip_data = {"destination": "Tokyo, Japan", "start_date": "2026-08-01"}
        assert _same_trip(extraction, trip_data) is False
