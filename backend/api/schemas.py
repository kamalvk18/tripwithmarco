"""
Pydantic request/response models for the Marco API.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


# ── Shared types ──────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str | list[Any] = Field(..., )

    @field_validator("content")
    @classmethod
    def _cap_content(cls, v: Any) -> Any:
        if isinstance(v, str) and len(v) > 32_000:
            raise ValueError("Message content exceeds 32,000 character limit")
        return v


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: list[Message] = Field(..., max_length=100)
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
    model_config = {"extra": "allow"}   # pass through any future fields without schema changes

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
    day_overrides: dict[str, Any] = Field(default_factory=dict)
    spending: list[dict[str, Any]] = Field(default_factory=list)
    checklist: list[dict[str, Any]] = Field(default_factory=list)
    email_config: dict[str, Any] = Field(default_factory=dict)
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

class DayPlan(BaseModel):
    """A single day's itinerary, extracted from Marco's free-form response."""
    day: int              # Day number (first number for ranges like Day 5-6 → 5)
    title: str            # Full heading, e.g. "Day 1 (May 28) — ARRIVAL"
    content: str          # Everything Marco wrote for that day


class BudgetBreakdown(BaseModel):
    """Estimated costs per category. None means the category wasn't mentioned."""
    flights: float | None = None
    accommodation: float | None = None
    food: float | None = None
    activities: float | None = None
    transport: float | None = None
    total_estimated: float | None = None


class ExtractRequest(BaseModel):
    """Body for POST /chat/extract — runs post-generation Haiku extraction."""
    messages: list[Message] = Field(..., max_length=100)
    currency: str = Field("EUR", max_length=3, pattern=r"^[A-Z]{3}$")


class ExtractResponse(BaseModel):
    """Structured trip info, day plans, and budget extracted from conversation."""
    destination: str = ""
    city: str = ""
    country_code: str = ""
    start_date: str = ""
    end_date: str = ""
    budget: float | None = None
    days: list[DayPlan] = Field(default_factory=list)
    budget_breakdown: BudgetBreakdown = Field(default_factory=BudgetBreakdown)
