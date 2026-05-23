"""
HTTP client for the Solo Travel Agent API.

Wraps all backend calls (trip CRUD, streaming chat, extraction) so the
Streamlit frontend doesn't import backend modules directly.  This is the only
file the frontend should depend on for data access.

Configuration
─────────────
Set the ``API_URL`` environment variable to point at a non-local server:

    API_URL=https://my-app.fly.dev  streamlit run frontend/app.py

Defaults to ``http://localhost:8000`` (the local dev server started by
``uv run main.py --api`` or ``uv run main.py --both``).
"""

import json
import os
from typing import Generator

import requests

_BASE_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
_SHORT_TIMEOUT = 10    # seconds — used for quick CRUD calls
_CHAT_TIMEOUT  = (10, 300)  # (connect, read) — reading can take a while


# ── Health ────────────────────────────────────────────────────────────────────

def is_api_running() -> bool:
    """Return True if the API server responds to a health check."""
    try:
        resp = requests.get(f"{_BASE_URL}/health", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


# ── Trip CRUD ─────────────────────────────────────────────────────────────────

def list_trips() -> list[dict]:
    """Return all saved trip summaries, newest first. Empty list on error."""
    try:
        resp = requests.get(f"{_BASE_URL}/api/trips", timeout=_SHORT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def load_trip(trip_id: str) -> dict | None:
    """Return a full trip dict, or None if it doesn't exist."""
    try:
        resp = requests.get(f"{_BASE_URL}/api/trips/{trip_id}", timeout=_SHORT_TIMEOUT)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def save_trip(trip_data: dict) -> str:
    """Save a new trip and return its generated trip_id."""
    resp = requests.post(
        f"{_BASE_URL}/api/trips",
        json={"trip_data": trip_data},
        timeout=_SHORT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["trip_id"]


def update_trip(trip_id: str, trip_data: dict) -> bool:
    """Overwrite an existing trip. Returns True on success."""
    try:
        resp = requests.put(
            f"{_BASE_URL}/api/trips/{trip_id}",
            json={"trip_data": trip_data},
            timeout=_SHORT_TIMEOUT,
        )
        return resp.status_code == 200
    except Exception:
        return False


def delete_trip(trip_id: str) -> bool:
    """Delete a trip. Returns True on success."""
    try:
        resp = requests.delete(
            f"{_BASE_URL}/api/trips/{trip_id}",
            timeout=_SHORT_TIMEOUT,
        )
        return resp.status_code == 200
    except Exception:
        return False


# ── Chat ──────────────────────────────────────────────────────────────────────

def chat_stream(
    messages: list,
    trip_data: dict | None = None,
    companion_mode: bool = False,
    on_tool_call=None,
) -> Generator[str, None, None]:
    """
    Stream Marco's response from the API. Yields text chunks (strings).

    Mirrors the interface of ``planning_agent.chat()`` so call sites in
    ``app.py`` are a drop-in replacement — just swap the import.

    SSE events handled internally:
        ``{"text": "..."}``       — yielded to the caller
        ``{"tool_call": "name"}`` — forwarded to *on_tool_call* if provided
        ``[DONE]``                — stops iteration

    If the API server is unreachable, yields a single error string so
    Streamlit can surface it in the chat bubble rather than crashing.
    """
    payload = {
        "messages": messages,
        "trip_data": trip_data,
        "companion_mode": companion_mode,
    }
    try:
        with requests.post(
            f"{_BASE_URL}/api/chat/stream",
            json=payload,
            stream=True,
            timeout=_CHAT_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                payload_str = raw_line[5:].strip()
                if payload_str == "[DONE]":
                    return
                try:
                    data = json.loads(payload_str)
                except json.JSONDecodeError:
                    continue
                if "tool_call" in data:
                    if on_tool_call is not None:
                        on_tool_call(data["tool_call"], {})
                elif "text" in data:
                    yield data["text"]

    except requests.exceptions.ConnectionError:
        yield (
            "\n\n⚠️ *Cannot connect to the API server.*  "
            "Start it with `uv run main.py --api` (or `--both` to run everything at once)."
        )
    except Exception as exc:
        yield f"\n\n⚠️ *API error: {exc}*"


# ── Extraction ────────────────────────────────────────────────────────────────

def extract_info(messages: list, currency: str = "EUR") -> dict:
    """
    Run post-generation extraction on a completed conversation.

    Makes two Claude Haiku calls on the server (~200 tokens each):
      1. Structured trip metadata (destination, city, country_code, dates)
      2. Budget breakdown per category from the itinerary text

    Returns a dict with keys:
        destination, city, country_code, start_date, end_date, budget_breakdown

    Returns {} on any failure so callers can proceed with empty/default values.
    """
    try:
        resp = requests.post(
            f"{_BASE_URL}/api/chat/extract",
            json={"messages": messages, "currency": currency},
            timeout=_SHORT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}
