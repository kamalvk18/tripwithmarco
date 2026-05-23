"""
Pydantic request/response models for the Solo Travel Agent API.
"""

from typing import Any
from pydantic import BaseModel, Field


# ── Shared types ──────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str           # "user" | "assistant"
    content: Any        # str for simple text, list for tool content blocks


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: list[Message]
    trip_data: dict[str, Any] | None = None
    companion_mode: bool = False


# ── Trips ────────────────────────────────────────────────────────────────────

class TripSummary(BaseModel):
    """Lightweight trip info returned by list_trips."""
    trip_id: str
    destination: str
    dates: str
    saved_at: str
    start_date: str = ""
    end_date: str = ""
    budget: float | None = None
    currency: str | None = None


class TripDetail(BaseModel):
    """Full trip object including conversation messages."""
    trip_id: str
    destination: str
    dates: str = ""
    saved_at: str = ""
    start_date: str = ""
    end_date: str = ""
    city: str = ""
    country_code: str = ""
    budget: float | None = None
    currency: str | None = None
    budget_breakdown: dict[str, Any] | None = None
    messages: list[Message] = Field(default_factory=list)


class SaveTripRequest(BaseModel):
    """Body for POST /trips — saves a new trip and returns its ID."""
    trip_data: dict[str, Any]


class UpdateTripRequest(BaseModel):
    """Body for PUT /trips/{trip_id} — overwrites a trip."""
    trip_data: dict[str, Any]


class TripIdResponse(BaseModel):
    trip_id: str


class OkResponse(BaseModel):
    ok: bool = True


# ── Expenses ─────────────────────────────────────────────────────────────────

EXPENSE_CATEGORIES = ["flights", "accommodation", "food", "activities", "transport", "misc"]

class ExpenseCreate(BaseModel):
    """Body for POST /trips/{trip_id}/expenses."""
    category: str
    amount: float
    description: str = ""
    date: str = ""          # ISO date string, defaults to today on server


class Expense(BaseModel):
    """A single logged expense entry."""
    id: str
    category: str
    amount: float
    description: str = ""
    date: str = ""


# ── Checklist ────────────────────────────────────────────────────────────────

class ChecklistItem(BaseModel):
    id: str
    category: str           # "visa", "health", "insurance", "documents", "kit"
    item: str
    completed: bool = False
    priority: str = "normal"   # "high" | "normal" | "low"


class ChecklistResponse(BaseModel):
    items: list[ChecklistItem]


# ── Extraction ────────────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    """Body for POST /chat/extract — runs post-generation Haiku extraction."""
    messages: list[Message]
    currency: str = "EUR"


class ExtractResponse(BaseModel):
    """Structured trip info + budget breakdown extracted from conversation."""
    destination: str = ""
    city: str = ""
    country_code: str = ""
    start_date: str = ""
    end_date: str = ""
    budget_breakdown: dict[str, Any] = Field(default_factory=dict)
