"""
Trip CRUD + sharing endpoints — all routes require a valid Bearer JWT
(except GET /trips/invite/{token} which is public).

GET    /trips                            → list caller's owned + joined trips
GET    /trips/{trip_id}                  → full trip (owner or member)
POST   /trips                            → save a new trip, returns trip_id
PUT    /trips/{trip_id}                  → overwrite an existing trip (owner only)
PATCH  /trips/{trip_id}                  → partial field update (owner or member)
DELETE /trips/{trip_id}                  → delete a trip (owner only)

POST   /trips/{trip_id}/expenses              → add an expense with optional paid_by + splits
DELETE /trips/{trip_id}/expenses/{id}         → remove an expense (own or owner)

POST   /trips/{trip_id}/settlements           → record a payment between members (from = current user)
DELETE /trips/{trip_id}/settlements/{id}      → remove a settlement (own or owner)
GET    /trips/{trip_id}/balances              → computed net balances across all members

POST   /trips/{trip_id}/checklist        → generate checklist (owner or member)
PATCH  /trips/{trip_id}/checklist/{id}   → toggle completed (owner or member)

── Sharing ──────────────────────────────────────────────────────────────────
GET    /trips/invite/{token}             → public preview of a trip (no auth)
POST   /trips/{trip_id}/invite           → generate invite link (owner only)
POST   /trips/{trip_id}/invite/regenerate → new link, old one revoked (owner)
DELETE /trips/{trip_id}/invite           → revoke invite link (owner only)
POST   /trips/join/{token}              → join a trip as member (auth required)
GET    /trips/{trip_id}/members          → list members (owner or member)
DELETE /trips/{trip_id}/members/{uid}   → kick a member (owner only)
DELETE /trips/{trip_id}/leave           → leave a trip (member only)
"""

import os
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from pydantic import BaseModel, Field
from backend.auth.deps import get_current_user
from backend.api.rate_limit import check_trip_limit, check_claude_limit
from backend.db.trip_store import (
    list_trips, load_trip, save_trip, update_trip, delete_trip,
    generate_invite_token, regenerate_invite_token, revoke_invite_token,
    get_trip_preview, join_trip, get_trip_members,
    remove_trip_member, leave_trip,
)
from backend.api.schemas import (
    TripSummary,
    TripDetail,
    SaveTripRequest,
    UpdateTripRequest,
    TripIdResponse,
    OkResponse,
    Expense,
    ExpenseCreate,
    Settlement,
    SettlementCreate,
    BalanceEntry,
    BalancesResponse,
    ChecklistItem,
    ChecklistResponse,
    InviteTokenResponse,
    TripPreviewResponse,
    JoinResponse,
    MembersResponse,
    TripMemberInfo,
)

router = APIRouter(prefix="/trips", tags=["trips"])

_FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(trip_id: str, user_id: int, member_ok: bool = True) -> dict:
    """Load trip, allowing members when member_ok=True (default)."""
    trip = load_trip(trip_id, user_id, member_ok=member_ok)
    if trip is None:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found")
    return trip


def _require_owner(trip: dict, user_id: int) -> None:
    if not trip.get("is_owner"):
        raise HTTPException(status_code=403, detail="Only the trip owner can do this")


def _compute_balances(spending: list, settlements: list, members: list) -> list[dict]:
    """Compute simplified net balances (minimum transactions) from expenses and settlements."""
    name_map = {m["user_id"]: m["name"] for m in members}
    net: dict[int, float] = {}

    for expense in spending:
        paid_by = expense.get("paid_by_user_id")
        splits = expense.get("splits") or []
        if not paid_by or not splits:
            continue
        for split in splits:
            uid = split["user_id"]
            amt = split["amount"]
            if uid != paid_by:
                net[paid_by] = net.get(paid_by, 0.0) + amt
                net[uid] = net.get(uid, 0.0) - amt

    for s in settlements:
        net[s["to_user_id"]] = net.get(s["to_user_id"], 0.0) - s["amount"]
        net[s["from_user_id"]] = net.get(s["from_user_id"], 0.0) + s["amount"]

    creditors = sorted([(uid, amt) for uid, amt in net.items() if amt > 0.005], key=lambda x: -x[1])
    debtors   = sorted([(uid, -amt) for uid, amt in net.items() if amt < -0.005], key=lambda x: -x[1])

    balances, ci, di = [], 0, 0
    creditors, debtors = list(creditors), list(debtors)
    while ci < len(creditors) and di < len(debtors):
        cuid, camt = creditors[ci]
        duid, damt = debtors[di]
        transfer = min(camt, damt)
        balances.append({
            "from_user_id": duid,
            "from_name": name_map.get(duid, "Unknown"),
            "to_user_id": cuid,
            "to_name": name_map.get(cuid, "Unknown"),
            "amount": round(transfer, 2),
        })
        creditors[ci] = (cuid, camt - transfer)
        debtors[di]   = (duid, damt - transfer)
        if creditors[ci][1] < 0.005:
            ci += 1
        if debtors[di][1] < 0.005:
            di += 1

    return balances


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[TripSummary])
def get_all_trips(current_user: dict = Depends(get_current_user)):
    return list_trips(current_user["id"])


@router.get("/{trip_id}", response_model=TripDetail)
def get_trip(trip_id: str, current_user: dict = Depends(get_current_user)):
    return _get_or_404(trip_id, current_user["id"], member_ok=True)


@router.post("", response_model=TripIdResponse, status_code=201)
def create_trip(body: SaveTripRequest, current_user: dict = Depends(check_trip_limit)):
    trip_id = save_trip(body.trip_data, current_user["id"])
    return TripIdResponse(trip_id=trip_id)


@router.put("/{trip_id}", response_model=OkResponse)
def replace_trip(trip_id: str, body: UpdateTripRequest, current_user: dict = Depends(get_current_user)):
    # Full overwrite is owner-only to prevent members from clobbering the itinerary
    success = update_trip(trip_id, body.trip_data, current_user["id"], member_ok=False)
    if not success:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found")
    return OkResponse()


@router.delete("/{trip_id}", response_model=OkResponse)
def remove_trip(trip_id: str, current_user: dict = Depends(get_current_user)):
    success = delete_trip(trip_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found")
    return OkResponse()


# ── Expenses ──────────────────────────────────────────────────────────────────

@router.post("/{trip_id}/expenses", response_model=Expense, status_code=201)
def add_expense(trip_id: str, body: ExpenseCreate, current_user: dict = Depends(get_current_user)):
    trip = _get_or_404(trip_id, current_user["id"], member_ok=True)
    paid_by_id = body.paid_by_user_id or current_user["id"]
    members = get_trip_members(trip_id)
    paid_by_name = next((m["name"] for m in members if m["user_id"] == paid_by_id), current_user["name"])
    expense = Expense(
        id=str(uuid.uuid4()),
        category=body.category,
        amount=body.amount,
        description=body.description,
        date=body.date or date.today().isoformat(),
        added_by_user_id=current_user["id"],
        added_by_name=current_user["name"],
        paid_by_user_id=paid_by_id,
        paid_by_name=paid_by_name,
        splits=[s.model_dump() for s in body.splits],
    )
    spending = trip.get("spending") or []
    spending.append(expense.model_dump())
    trip["spending"] = spending
    update_trip(trip_id, trip, current_user["id"], member_ok=True)
    return expense


@router.delete("/{trip_id}/expenses/{expense_id}", response_model=OkResponse)
def remove_expense(trip_id: str, expense_id: str, current_user: dict = Depends(get_current_user)):
    trip = _get_or_404(trip_id, current_user["id"], member_ok=True)
    spending = trip.get("spending") or []
    target = next((e for e in spending if e.get("id") == expense_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    # Members can only delete their own expenses; owners can delete any
    if not trip.get("is_owner") and target.get("added_by_user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="You can only delete your own expenses")
    trip["spending"] = [e for e in spending if e.get("id") != expense_id]
    update_trip(trip_id, trip, current_user["id"], member_ok=True)
    return OkResponse()


# ── Settlements ───────────────────────────────────────────────────────────────

@router.post("/{trip_id}/settlements", response_model=Settlement, status_code=201)
def add_settlement(trip_id: str, body: SettlementCreate, current_user: dict = Depends(get_current_user)):
    trip = _get_or_404(trip_id, current_user["id"], member_ok=True)
    members = get_trip_members(trip_id)
    to_name = next((m["name"] for m in members if m["user_id"] == body.to_user_id), None)
    if to_name is None:
        raise HTTPException(status_code=400, detail="to_user_id is not a trip member")
    settlement = Settlement(
        id=str(uuid.uuid4()),
        from_user_id=current_user["id"],
        from_name=current_user["name"],
        to_user_id=body.to_user_id,
        to_name=to_name,
        amount=body.amount,
        date=body.date or date.today().isoformat(),
        note=body.note,
    )
    settlements = trip.get("settlements") or []
    settlements.append(settlement.model_dump())
    trip["settlements"] = settlements
    update_trip(trip_id, trip, current_user["id"], member_ok=True)
    return settlement


@router.delete("/{trip_id}/settlements/{settlement_id}", response_model=OkResponse)
def remove_settlement(trip_id: str, settlement_id: str, current_user: dict = Depends(get_current_user)):
    trip = _get_or_404(trip_id, current_user["id"], member_ok=True)
    settlements = trip.get("settlements") or []
    target = next((s for s in settlements if s.get("id") == settlement_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Settlement not found")
    if not trip.get("is_owner") and target.get("from_user_id") != current_user["id"]:
        raise HTTPException(status_code=403, detail="You can only delete your own settlements")
    trip["settlements"] = [s for s in settlements if s.get("id") != settlement_id]
    update_trip(trip_id, trip, current_user["id"], member_ok=True)
    return OkResponse()


@router.get("/{trip_id}/balances", response_model=BalancesResponse)
def get_balances(trip_id: str, current_user: dict = Depends(get_current_user)):
    trip = _get_or_404(trip_id, current_user["id"], member_ok=True)
    members = get_trip_members(trip_id)
    balances = _compute_balances(trip.get("spending") or [], trip.get("settlements") or [], members)
    return BalancesResponse(balances=[BalanceEntry(**b) for b in balances])


# ── Checklist ─────────────────────────────────────────────────────────────────

@router.post("/{trip_id}/checklist", response_model=ChecklistResponse)
def generate_checklist(
    trip_id: str,
    passport_country: str = Query("", max_length=100, pattern=r"^[a-zA-Z ,\-]*$"),
    current_user: dict = Depends(check_claude_limit),
):
    from backend.agents.planning_agent import generate_checklist as _gen
    trip = _get_or_404(trip_id, current_user["id"], member_ok=True)
    # Use origin_country extracted from the conversation if the caller didn't supply one
    effective_passport = passport_country or trip.get("origin_country", "")
    items_raw = _gen(trip.get("destination", ""), effective_passport, trip.get("start_date", ""))
    items = [ChecklistItem(id=str(uuid.uuid4()), **item) for item in items_raw]
    trip["checklist"] = [i.model_dump() for i in items]
    update_trip(trip_id, trip, current_user["id"], member_ok=True)
    return ChecklistResponse(items=items)


@router.patch("/{trip_id}/checklist/{item_id}", response_model=OkResponse)
def toggle_checklist_item(
    trip_id: str,
    item_id: str,
    completed: bool = False,
    current_user: dict = Depends(get_current_user),
):
    trip = _get_or_404(trip_id, current_user["id"], member_ok=True)
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
    update_trip(trip_id, trip, current_user["id"], member_ok=True)
    return OkResponse()


# ── Partial field patch ───────────────────────────────────────────────────────

_PATCHABLE_ALL = {
    "day_overrides", "currency", "notes", "near_me_response",
    "email_config", "spending", "settlements", "checklist",
}
_PATCHABLE_MEMBER = {"day_overrides", "near_me_response", "spending", "settlements", "checklist"}


@router.patch("/{trip_id}", response_model=OkResponse)
def patch_trip_fields(
    trip_id: str,
    updates: dict = Body(...),
    current_user: dict = Depends(get_current_user),
):
    trip = _get_or_404(trip_id, current_user["id"], member_ok=True)
    allowed = _PATCHABLE_ALL if trip.get("is_owner") else _PATCHABLE_MEMBER
    disallowed = set(updates.keys()) - allowed
    if disallowed:
        raise HTTPException(status_code=422, detail=f"Fields not patchable: {sorted(disallowed)}")
    trip.update(updates)
    update_trip(trip_id, trip, current_user["id"], member_ok=True)
    return OkResponse()


# ── Post-trip debrief ─────────────────────────────────────────────────────────

class DebriefRequest(BaseModel):
    debrief_text: str = Field(..., max_length=5000)


@router.post("/{trip_id}/debrief", response_model=OkResponse)
def save_debrief(trip_id: str, body: DebriefRequest, current_user: dict = Depends(check_claude_limit)):
    from backend.agents.planning_agent import extract_preferences
    trip = _get_or_404(trip_id, current_user["id"], member_ok=False)
    preferences = extract_preferences(body.debrief_text)
    trip["debrief"] = body.debrief_text
    trip["preferences"] = preferences
    update_trip(trip_id, trip, current_user["id"], member_ok=False)
    return OkResponse()


# ── Email briefing config ─────────────────────────────────────────────────────

class EmailConfigRequest(BaseModel):
    email:     str
    send_time: str = "07:00"
    enabled:   bool = True


@router.post("/{trip_id}/email-config", response_model=OkResponse)
def set_email_config(trip_id: str, body: EmailConfigRequest, current_user: dict = Depends(get_current_user)):
    trip = _get_or_404(trip_id, current_user["id"], member_ok=False)
    trip["email_config"] = {"email": body.email, "send_time": body.send_time, "enabled": body.enabled}
    update_trip(trip_id, trip, current_user["id"], member_ok=False)
    return OkResponse()


@router.post("/{trip_id}/send-briefing", response_model=OkResponse)
def send_briefing_now(trip_id: str, to_email: str = Body(..., embed=True), current_user: dict = Depends(get_current_user)):
    from backend.email.briefing import send_briefing
    _get_or_404(trip_id, current_user["id"], member_ok=False)  # ownership check
    success = send_briefing(trip_id, to_email)
    if not success:
        raise HTTPException(status_code=400, detail="Could not send briefing — check RESEND_API_KEY and trip dates")
    return OkResponse()


# ── Sharing ───────────────────────────────────────────────────────────────────

@router.get("/invite/{token}", response_model=TripPreviewResponse, tags=["sharing"])
def get_invite_preview(token: str):
    """Public endpoint — returns trip preview for an invite link (no auth needed)."""
    preview = get_trip_preview(token)
    if preview is None:
        raise HTTPException(status_code=404, detail="Invite link not found or expired")
    return TripPreviewResponse(**preview)


@router.post("/{trip_id}/invite", response_model=InviteTokenResponse, tags=["sharing"])
def create_invite(trip_id: str, current_user: dict = Depends(get_current_user)):
    """Generate a shareable invite link (owner only). Idempotent — same token returned on repeat calls."""
    token = generate_invite_token(trip_id, current_user["id"])
    if token is None:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found")
    return InviteTokenResponse(
        invite_token=token,
        invite_url=f"{_FRONTEND_URL}/join/{token}",
    )


@router.post("/{trip_id}/invite/regenerate", response_model=InviteTokenResponse, tags=["sharing"])
def rotate_invite(trip_id: str, current_user: dict = Depends(get_current_user)):
    """Revoke old invite link and issue a fresh one (owner only)."""
    token = regenerate_invite_token(trip_id, current_user["id"])
    if token is None:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found")
    return InviteTokenResponse(
        invite_token=token,
        invite_url=f"{_FRONTEND_URL}/join/{token}",
    )


@router.delete("/{trip_id}/invite", response_model=OkResponse, tags=["sharing"])
def delete_invite(trip_id: str, current_user: dict = Depends(get_current_user)):
    """Revoke the invite link so the old URL stops working (owner only)."""
    success = revoke_invite_token(trip_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail=f"Trip '{trip_id}' not found")
    return OkResponse()


@router.post("/join/{token}", response_model=JoinResponse, tags=["sharing"])
def join_trip_route(token: str, current_user: dict = Depends(get_current_user)):
    """Join a trip as a member via an invite token."""
    try:
        trip_id = join_trip(token, current_user["id"])
    except ValueError as e:
        msg = str(e)
        if msg == "already_owner":
            # Owner clicking own link — just redirect them to the trip
            preview = get_trip_preview(token)
            if preview:
                return JoinResponse(trip_id=preview["trip_id"], message="You own this trip")
        # already_member — also fine, just redirect them
        if msg == "already_member":
            preview = get_trip_preview(token)
            if preview:
                return JoinResponse(trip_id=preview["trip_id"], message="Already a member")
        raise HTTPException(status_code=400, detail=msg)
    if trip_id is None:
        raise HTTPException(status_code=404, detail="Invite link not found or expired")
    return JoinResponse(trip_id=trip_id)


@router.get("/{trip_id}/members", response_model=MembersResponse, tags=["sharing"])
def list_members(trip_id: str, current_user: dict = Depends(get_current_user)):
    """List all members of a trip (owner or member can call this)."""
    _get_or_404(trip_id, current_user["id"], member_ok=True)  # access check
    members = get_trip_members(trip_id)
    return MembersResponse(members=[TripMemberInfo(**m) for m in members])


@router.delete("/{trip_id}/members/{member_user_id}", response_model=OkResponse, tags=["sharing"])
def kick_member(trip_id: str, member_user_id: int, current_user: dict = Depends(get_current_user)):
    """Remove a member from the trip (owner only)."""
    success = remove_trip_member(trip_id, current_user["id"], member_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Member or trip not found")
    return OkResponse()


@router.delete("/{trip_id}/leave", response_model=OkResponse, tags=["sharing"])
def leave_trip_route(trip_id: str, current_user: dict = Depends(get_current_user)):
    """Leave a shared trip (members only — owners cannot leave their own trip)."""
    trip = load_trip(trip_id, current_user["id"], member_ok=True)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip.get("is_owner"):
        raise HTTPException(status_code=400, detail="Owners cannot leave their own trip. Delete it instead.")
    success = leave_trip(trip_id, current_user["id"])
    if not success:
        raise HTTPException(status_code=404, detail="You are not a member of this trip")
    return OkResponse()
