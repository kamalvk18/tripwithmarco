"""
Pydantic request/response models for the Marco API.
"""

import re
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
        if isinstance(v, list) and len(v) > 50:
            raise ValueError("Message content list exceeds 50 items")
        return v


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    messages: list[Message] = Field(..., max_length=100)
    trip_data: dict[str, Any] | None = None
    companion_mode: bool = False


# ── Trips ────────────────────────────────────────────────────────────────────

class TripMemberInfo(BaseModel):
    """A single trip participant (owner or joined member)."""
    user_id: int
    name: str = ""
    picture: str = ""
    email: str = ""
    role: str = "member"      # "owner" | "member"
    joined_at: str = ""


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
    origin: str = ""
    is_member: bool = False        # True when the caller joined but doesn't own the trip
    owner_name: str = ""           # Non-empty only when is_member=True


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
    origin_country: str = ""
    is_domestic: bool | None = None
    budget: float | None = None
    currency: str | None = None
    budget_breakdown: dict[str, Any] | None = None
    day_overrides: dict[str, Any] = Field(default_factory=dict)
    spending: list[dict[str, Any]] = Field(default_factory=list)
    settlements: list[dict[str, Any]] = Field(default_factory=list)
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

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ExpenseSplit(BaseModel):
    """One member's share of an expense."""
    user_id: int
    name: str = Field("", max_length=200)
    amount: float = Field(..., gt=0, le=1_000_000)


class ExpenseCreate(BaseModel):
    """Body for POST /trips/{trip_id}/expenses."""
    category: str
    amount: float = Field(..., gt=0, le=1_000_000)
    description: str = Field("", max_length=500)
    date: str = Field("", max_length=10)
    paid_by_user_id: int | None = None   # defaults to current user
    splits: list[ExpenseSplit] = Field(default_factory=list, max_length=50)

    @field_validator("category")
    @classmethod
    def _valid_category(cls, v: str) -> str:
        if v not in EXPENSE_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(EXPENSE_CATEGORIES)}")
        return v

    @field_validator("date")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        if v and not _DATE_RE.match(v):
            raise ValueError("date must be in YYYY-MM-DD format")
        return v


class Expense(BaseModel):
    """A single logged expense entry."""
    id: str
    category: str
    amount: float
    description: str = ""
    date: str = ""
    added_by_user_id: int | None = None   # who logged this expense
    added_by_name: str = ""               # display name of the logger
    paid_by_user_id: int | None = None    # who actually paid
    paid_by_name: str = ""
    splits: list[ExpenseSplit] = Field(default_factory=list)


# ── Settlements ───────────────────────────────────────────────────────────────

class SettlementCreate(BaseModel):
    """Body for POST /trips/{trip_id}/settlements — current user pays to_user_id."""
    to_user_id: int
    amount: float = Field(..., gt=0, le=1_000_000)
    note: str = Field("", max_length=500)
    date: str = Field("", max_length=10)

    @field_validator("date")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        if v and not _DATE_RE.match(v):
            raise ValueError("date must be in YYYY-MM-DD format")
        return v


class Settlement(BaseModel):
    """A recorded payment between two trip members."""
    id: str
    from_user_id: int
    from_name: str = ""
    to_user_id: int
    to_name: str = ""
    amount: float
    date: str = ""
    note: str = ""


class BalanceEntry(BaseModel):
    from_user_id: int
    from_name: str
    to_user_id: int
    to_name: str
    amount: float


class BalancesResponse(BaseModel):
    balances: list[BalanceEntry]


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
    travel: float | None = None
    flights: float | None = None  # legacy — old trips used this; prefer travel
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
    origin_country: str = ""
    is_domestic: bool | None = None
    start_date: str = ""
    end_date: str = ""
    budget: float | None = None
    trip_type: str = "single_destination"
    stops: list[dict[str, Any]] = Field(default_factory=list)
    days: list[DayPlan] = Field(default_factory=list)
    budget_breakdown: dict[str, Any] = Field(default_factory=dict)


# ── Sharing ───────────────────────────────────────────────────────────────────

class SurpriseRequest(BaseModel):
    """Body for POST /chat/surprise — all three inputs are required."""
    origin: str = Field(..., min_length=1, max_length=200)
    start_date: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., min_length=10, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    # Optional personalisation context
    past_destinations: list[str] = Field(default_factory=list, max_length=50)
    preferences: list[str] = Field(default_factory=list, max_length=20)
    budget: float | None = None
    currency: str = Field("EUR", max_length=3)
    travel_styles: list[str] = Field(default_factory=list, max_length=10)


class SurpriseResponse(BaseModel):
    """Response for POST /chat/surprise — the destination Marco picked for the given dates."""
    destination: str
    reason: str


class InviteTokenResponse(BaseModel):
    invite_token: str
    invite_url: str


class TripPreviewResponse(BaseModel):
    """Public preview of a trip shown before joining (no auth required)."""
    trip_id: str
    destination: str
    dates: str
    owner_name: str
    owner_picture: str = ""


class JoinResponse(BaseModel):
    trip_id: str
    message: str = "Joined successfully"


class MembersResponse(BaseModel):
    members: list[TripMemberInfo]
