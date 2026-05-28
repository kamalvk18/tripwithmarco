"""
Trip CRUD endpoints.

GET    /trips                          → list all trips (summaries)
GET    /trips/{trip_id}               → full trip with messages
POST   /trips                          → save a new trip, returns trip_id
PUT    /trips/{trip_id}               → overwrite an existing trip
DELETE /trips/{trip_id}               → delete a trip

POST   /trips/{trip_id}/expenses      → add an expense
DELETE /trips/{trip_id}/expenses/{id} → remove an expense

POST   /trips/{trip_id}/checklist     → generate checklist (Haiku)
PATCH  /trips/{trip_id}/checklist/{id} → toggle completed
"""

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from backend.db.trip_store import list_trips, load_trip, save_trip, update_trip, delete_trip
from backend.api.schemas import (
    TripSummary,
    TripDetail,
    SaveTripRequest,
    UpdateTripRequest,
    TripIdResponse,
    OkResponse,
    Expense,
    ExpenseCreate,
    ChecklistItem,
    ChecklistResponse,
)

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("", response_model=list[TripSummary])
def get_all_trips():
    """Return a summary list of all saved trips."""
    return list_trips()


@router.get("/{trip_id}", response_model=TripDetail)
def get_trip(trip_id: str):
    """Return a single trip with full conversation history."""
    trip = load_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found")
    return trip


@router.post("", response_model=TripIdResponse, status_code=201)
def create_trip(body: SaveTripRequest):
    """Save a new trip. Returns the generated trip_id."""
    trip_id = save_trip(body.trip_data)
    return TripIdResponse(trip_id=trip_id)


@router.put("/{trip_id}", response_model=OkResponse)
def replace_trip(trip_id: str, body: UpdateTripRequest):
    """Overwrite an existing trip with new data."""
    success = update_trip(trip_id, body.trip_data)
    if not success:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found")
    return OkResponse()


@router.delete("/{trip_id}", response_model=OkResponse)
def remove_trip(trip_id: str):
    """Delete a trip by ID."""
    success = delete_trip(trip_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found")
    return OkResponse()


# ── Expenses ──────────────────────────────────────────────────────────────────

def _get_or_404(trip_id: str) -> dict:
    trip = load_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found")
    return trip


@router.post("/{trip_id}/expenses", response_model=Expense, status_code=201)
def add_expense(trip_id: str, body: ExpenseCreate):
    """Log a new expense against a trip."""
    trip = _get_or_404(trip_id)
    expense = Expense(
        id=str(uuid.uuid4()),
        category=body.category,
        amount=body.amount,
        description=body.description,
        date=body.date or date.today().isoformat(),
    )
    spending = trip.get("spending") or []
    spending.append(expense.model_dump())
    trip["spending"] = spending
    update_trip(trip_id, trip)
    return expense


@router.delete("/{trip_id}/expenses/{expense_id}", response_model=OkResponse)
def remove_expense(trip_id: str, expense_id: str):
    """Remove a logged expense."""
    trip = _get_or_404(trip_id)
    spending = trip.get("spending") or []
    new_spending = [e for e in spending if e.get("id") != expense_id]
    if len(new_spending) == len(spending):
        raise HTTPException(status_code=404, detail="Expense not found")
    trip["spending"] = new_spending
    update_trip(trip_id, trip)
    return OkResponse()


# ── Checklist ─────────────────────────────────────────────────────────────────

@router.post("/{trip_id}/checklist", response_model=ChecklistResponse)
def generate_checklist(trip_id: str, passport_country: str = ""):
    """Generate a pre-trip checklist using Claude Haiku."""
    from backend.agents.planning_agent import generate_checklist as _gen
    trip = _get_or_404(trip_id)
    destination = trip.get("destination", "")
    start_date  = trip.get("start_date", "")
    items_raw   = _gen(destination, passport_country, start_date)
    # Assign stable IDs and persist
    items = [ChecklistItem(id=str(uuid.uuid4()), **item) for item in items_raw]
    trip["checklist"] = [i.model_dump() for i in items]
    update_trip(trip_id, trip)
    return ChecklistResponse(items=items)


@router.patch("/{trip_id}/checklist/{item_id}", response_model=OkResponse)
def toggle_checklist_item(trip_id: str, item_id: str, completed: bool = False):
    """Toggle a checklist item's completed state."""
    trip = _get_or_404(trip_id)
    checklist = trip.get("checklist") or []
    found = False
    for item in checklist:
        if item.get("id") == item_id:
            item["completed"] = completed
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    trip["checklist"] = checklist
    update_trip(trip_id, trip)
    return OkResponse()


# ── Partial field patch ───────────────────────────────────────────────────────

@router.patch("/{trip_id}", response_model=OkResponse)
def patch_trip_fields(trip_id: str, updates: dict = Body(...)):
    """
    Apply partial updates to a trip without requiring the full trip body.
    Reads the current trip from disk, merges updates, and saves.
    Safer than PUT when only a single field needs changing.
    """
    trip = _get_or_404(trip_id)
    trip.update(updates)
    update_trip(trip_id, trip)
    return OkResponse()


# ── Post-trip debrief ─────────────────────────────────────────────────────────

class DebriefRequest(BaseModel):
    debrief_text: str


@router.post("/{trip_id}/debrief", response_model=OkResponse)
def save_debrief(trip_id: str, body: DebriefRequest):
    """Persist a post-trip debrief and extract travel preference signals."""
    from backend.agents.planning_agent import extract_preferences
    trip = _get_or_404(trip_id)
    preferences = extract_preferences(body.debrief_text)
    trip["debrief"] = body.debrief_text
    trip["preferences"] = preferences
    update_trip(trip_id, trip)
    return OkResponse()


# ── Email briefing config ─────────────────────────────────────────────────────

class EmailConfigRequest(BaseModel):
    email:     str
    send_time: str = "07:00"   # HH:MM 24-hour UTC
    enabled:   bool = True


@router.post("/{trip_id}/email-config", response_model=OkResponse)
def set_email_config(trip_id: str, body: EmailConfigRequest):
    """Save email + send time for daily briefings."""
    trip = _get_or_404(trip_id)
    trip["email_config"] = {
        "email":     body.email,
        "send_time": body.send_time,
        "enabled":   body.enabled,
    }
    update_trip(trip_id, trip)
    return OkResponse()


@router.post("/{trip_id}/send-briefing", response_model=OkResponse)
def send_briefing_now(trip_id: str, to_email: str = Body(..., embed=True)):
    """Send today's briefing immediately."""
    from backend.email.briefing import send_briefing
    success = send_briefing(trip_id, to_email)
    if not success:
        raise HTTPException(status_code=400, detail="Could not send briefing — check RESEND_API_KEY and trip dates")
    return OkResponse()
