"""
FastAPI endpoint tests — no API keys or real Claude calls required.
Uses FastAPI's TestClient (synchronous) with mocked chat() and trip_store.

Run with: uv run pytest tests/test_api.py -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.auth.deps import get_current_user

# Override auth so tests never need a real JWT
_MOCK_USER = {"id": 1, "google_id": "g123", "email": "test@example.com", "name": "Test User", "picture": ""}
app.dependency_overrides[get_current_user] = lambda: _MOCK_USER

client = TestClient(app)

# ── /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_200(self):
        res = client.get("/health")
        assert res.status_code == 200

    def test_returns_ok_status(self):
        res = client.get("/health")
        assert res.json() == {"status": "ok"}


# ── /api/trips ────────────────────────────────────────────────────────────────

SAMPLE_TRIP = {
    "trip_id": "20260516_120000",
    "destination": "Kraków, Poland",
    "dates": "2026-06-01 to 2026-06-05",
    "saved_at": "2026-05-16T12:00:00",
    "start_date": "2026-06-01",
    "end_date": "2026-06-05",
    "city": "Kraków",
    "country_code": "PL",
    "budget": 800.0,
    "currency": "EUR",
    "messages": [{"role": "user", "content": "Plan my trip"}],
}

SAMPLE_SUMMARY = {
    "trip_id": "20260516_120000",
    "destination": "Kraków, Poland",
    "dates": "2026-06-01 to 2026-06-05",
    "saved_at": "2026-05-16T12:00:00",
}


class TestListTrips:
    def test_returns_200(self):
        with patch("backend.api.routes.trips.list_trips", return_value=[SAMPLE_SUMMARY]):
            res = client.get("/api/trips")
        assert res.status_code == 200

    def test_returns_list(self):
        with patch("backend.api.routes.trips.list_trips", return_value=[SAMPLE_SUMMARY]):
            res = client.get("/api/trips")
        assert isinstance(res.json(), list)
        assert len(res.json()) == 1

    def test_returns_empty_list_when_no_trips(self):
        with patch("backend.api.routes.trips.list_trips", return_value=[]):
            res = client.get("/api/trips")
        assert res.json() == []


class TestGetTrip:
    def test_returns_200_for_existing_trip(self):
        with patch("backend.api.routes.trips.load_trip", return_value=SAMPLE_TRIP):
            res = client.get("/api/trips/20260516_120000")
        assert res.status_code == 200

    def test_returns_trip_data(self):
        with patch("backend.api.routes.trips.load_trip", return_value=SAMPLE_TRIP):
            res = client.get("/api/trips/20260516_120000")
        assert res.json()["destination"] == "Kraków, Poland"

    def test_returns_404_for_missing_trip(self):
        with patch("backend.api.routes.trips.load_trip", return_value=None):
            res = client.get("/api/trips/nonexistent")
        assert res.status_code == 404


class TestCreateTrip:
    def test_returns_201(self):
        with patch("backend.api.routes.trips.save_trip", return_value="20260516_120000"):
            res = client.post("/api/trips", json={"trip_data": SAMPLE_TRIP})
        assert res.status_code == 201

    def test_returns_trip_id(self):
        with patch("backend.api.routes.trips.save_trip", return_value="20260516_120000"):
            res = client.post("/api/trips", json={"trip_data": SAMPLE_TRIP})
        assert res.json()["trip_id"] == "20260516_120000"


class TestUpdateTrip:
    def test_returns_200_for_existing_trip(self):
        with patch("backend.api.routes.trips.update_trip", return_value=True):
            res = client.put("/api/trips/20260516_120000", json={"trip_data": SAMPLE_TRIP})
        assert res.status_code == 200

    def test_returns_404_for_missing_trip(self):
        with patch("backend.api.routes.trips.update_trip", return_value=False):
            res = client.put("/api/trips/nonexistent", json={"trip_data": SAMPLE_TRIP})
        assert res.status_code == 404


class TestDeleteTrip:
    def test_returns_200_for_existing_trip(self):
        with patch("backend.api.routes.trips.delete_trip", return_value=True):
            res = client.delete("/api/trips/20260516_120000")
        assert res.status_code == 200

    def test_returns_ok_true(self):
        with patch("backend.api.routes.trips.delete_trip", return_value=True):
            res = client.delete("/api/trips/20260516_120000")
        assert res.json()["ok"] is True

    def test_returns_404_for_missing_trip(self):
        with patch("backend.api.routes.trips.delete_trip", return_value=False):
            res = client.delete("/api/trips/nonexistent")
        assert res.status_code == 404


# ── /api/chat ─────────────────────────────────────────────────────────────────

CHAT_PAYLOAD = {
    "messages": [{"role": "user", "content": "What's the best time to visit Kraków?"}],
    "trip_data": None,
    "companion_mode": False,
}


class TestChatSync:
    def test_returns_200(self):
        with patch("backend.api.routes.chat.chat", return_value=iter(["Hello ", "from ", "Marco."])):
            res = client.post("/api/chat", json=CHAT_PAYLOAD)
        assert res.status_code == 200

    def test_returns_full_response(self):
        with patch("backend.api.routes.chat.chat", return_value=iter(["Hello ", "from ", "Marco."])):
            res = client.post("/api/chat", json=CHAT_PAYLOAD)
        assert res.json()["response"] == "Hello from Marco."


class TestChatStream:
    def test_returns_200(self):
        with patch("backend.api.routes.chat.chat", return_value=iter(["chunk1"])):
            res = client.post("/api/chat/stream", json=CHAT_PAYLOAD)
        assert res.status_code == 200

    def test_returns_event_stream_content_type(self):
        with patch("backend.api.routes.chat.chat", return_value=iter(["chunk1"])):
            res = client.post("/api/chat/stream", json=CHAT_PAYLOAD)
        assert "text/event-stream" in res.headers["content-type"]

    def test_sse_format_contains_data_lines(self):
        with patch("backend.api.routes.chat.chat", return_value=iter(["Hello", " Marco"])):
            res = client.post("/api/chat/stream", json=CHAT_PAYLOAD)
        body = res.text
        assert "data:" in body
        assert "[DONE]" in body

    def test_sse_chunks_are_valid_json(self):
        with patch("backend.api.routes.chat.chat", return_value=iter(["Hello"])):
            res = client.post("/api/chat/stream", json=CHAT_PAYLOAD)
        for line in res.text.strip().splitlines():
            if line.startswith("data:") and "[DONE]" not in line:
                payload = line.removeprefix("data:").strip()
                parsed = json.loads(payload)
                # Valid event types in the SSE stream
                valid_keys = {"text", "tool_call", "booking_data", "eval_result"}
                assert parsed.keys() & valid_keys, f"Unexpected SSE event keys: {parsed.keys()}"


# ── /api/chat/extract ─────────────────────────────────────────────────────────

EXTRACT_PAYLOAD = {
    "messages": [
        {"role": "user", "content": "Plan my trip to Kraków from June 1 to June 5."},
        {"role": "assistant", "content": "Day 1: Arrival...\n\nDay 2: Old Town..."},
    ],
    "currency": "EUR",
}

EXTRACT_RESULT = {
    "destination": "Kraków, Poland",
    "city": "Kraków",
    "country_code": "PL",
    "start_date": "2026-06-01",
    "end_date": "2026-06-05",
    "budget_breakdown": {"flights": 200, "accommodation": 300, "total_estimated": 600},
}


_STRUCTURED_RESULT = {
    "days": [{"day": 1, "title": "Day 1 — ARRIVAL", "content": "Arrive, check in."}],
    "budget_breakdown": EXTRACT_RESULT["budget_breakdown"],
}


class TestExtract:
    def test_returns_200(self):
        with (
            patch("backend.api.routes.chat.extract_trip_details", return_value=EXTRACT_RESULT),
            patch("backend.api.routes.chat.extract_itinerary", return_value="Day 1: ..."),
            patch("backend.api.routes.chat.extract_structured_itinerary", return_value=_STRUCTURED_RESULT),
        ):
            res = client.post("/api/chat/extract", json=EXTRACT_PAYLOAD)
        assert res.status_code == 200

    def test_returns_destination(self):
        with (
            patch("backend.api.routes.chat.extract_trip_details", return_value=EXTRACT_RESULT),
            patch("backend.api.routes.chat.extract_itinerary", return_value="Day 1: ..."),
            patch("backend.api.routes.chat.extract_structured_itinerary", return_value=_STRUCTURED_RESULT),
        ):
            res = client.post("/api/chat/extract", json=EXTRACT_PAYLOAD)
        assert res.json()["destination"] == "Kraków, Poland"

    def test_returns_budget_breakdown(self):
        with (
            patch("backend.api.routes.chat.extract_trip_details", return_value=EXTRACT_RESULT),
            patch("backend.api.routes.chat.extract_itinerary", return_value="Day 1: ..."),
            patch("backend.api.routes.chat.extract_structured_itinerary", return_value=_STRUCTURED_RESULT),
        ):
            res = client.post("/api/chat/extract", json=EXTRACT_PAYLOAD)
        assert res.json()["budget_breakdown"]["flights"] == 200

    def test_returns_days(self):
        _days = [{"day": 1, "title": "ARRIVAL", "content": "Arrive, check in."}]
        with (
            patch("backend.api.routes.chat.extract_trip_details", return_value=EXTRACT_RESULT),
            patch("backend.api.routes.chat.extract_itinerary", return_value="Day 1: ..."),
            patch("backend.api.routes.chat.extract_structured_itinerary", return_value=_STRUCTURED_RESULT),
            patch("backend.api.routes.chat.extract_all_days", return_value=_days),
        ):
            res = client.post("/api/chat/extract", json=EXTRACT_PAYLOAD)
        days = res.json()["days"]
        assert len(days) == 1
        assert days[0]["day"] == 1
        assert days[0]["title"] == "ARRIVAL"

    def test_missing_currency_defaults_to_eur(self):
        payload_no_currency = {
            "messages": EXTRACT_PAYLOAD["messages"],
        }
        with (
            patch("backend.api.routes.chat.extract_trip_details", return_value={}),
            patch("backend.api.routes.chat.extract_itinerary", return_value=""),
            patch("backend.api.routes.chat.extract_structured_itinerary", return_value={}) as mock_extract,
        ):
            client.post("/api/chat/extract", json=payload_no_currency)
        mock_extract.assert_called_once_with("", currency="EUR")
