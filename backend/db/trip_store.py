import json
import os
import secrets
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from backend.db.database import SessionLocal
from backend.db.models import Trip, TripMember, User


# Legacy JSON directory — only used during one-time migration.
_LEGACY_DIR = os.getenv("TRIPS_DIR", "data/trips")

# Fields that are computed at load time and must not be persisted into the JSON blob.
_TRANSIENT_FIELDS = {"members", "is_owner", "invite_token"}


def _row_to_summary(row: Trip, is_member: bool = False, owner_name: str = "") -> dict:
    return {
        "trip_id":     row.trip_id,
        "destination": row.destination or "Unknown",
        "dates":       row.dates or "",
        "saved_at":    row.saved_at or "",
        "start_date":  row.start_date or "",
        "end_date":    row.end_date or "",
        "budget":      row.budget,
        "currency":    row.currency,
        "is_member":   is_member,
        "owner_name":  owner_name,
    }


def _trip_to_row(trip_id: str, trip_data: dict, user_id: int | None = None) -> Trip:
    return Trip(
        trip_id=trip_id,
        user_id=user_id,
        destination=trip_data.get("destination", ""),
        start_date=trip_data.get("start_date", ""),
        end_date=trip_data.get("end_date", ""),
        dates=trip_data.get("dates", ""),
        saved_at=trip_data.get("saved_at", ""),
        budget=trip_data.get("budget"),
        currency=trip_data.get("currency"),
        data=json.dumps(trip_data),
    )


def _get_members_for_trip(session, trip_row: Trip) -> list[dict]:
    """Return the full member list (owner first, then joined members) for a trip."""
    members = []

    # Owner
    if trip_row.user_id:
        owner = session.get(User, trip_row.user_id)
        if owner:
            members.append({
                "user_id":   owner.id,
                "name":      owner.name,
                "picture":   owner.picture,
                "email":     owner.email,
                "role":      "owner",
                "joined_at": trip_row.saved_at or "",
            })

    # Joined members
    rows = (
        session.query(TripMember, User)
        .join(User, TripMember.user_id == User.id)
        .filter(TripMember.trip_id == trip_row.trip_id)
        .order_by(TripMember.joined_at)
        .all()
    )
    for tm, user in rows:
        members.append({
            "user_id":   user.id,
            "name":      user.name,
            "picture":   user.picture,
            "email":     user.email,
            "role":      "member",
            "joined_at": tm.joined_at.isoformat() if tm.joined_at else "",
        })

    return members


def _is_member(session, trip_id: str, user_id: int) -> bool:
    return (
        session.query(TripMember)
        .filter(TripMember.trip_id == trip_id, TripMember.user_id == user_id)
        .first()
    ) is not None


# ── Public API ────────────────────────────────────────────────────────────────

def save_trip(trip_data: dict, user_id: int | None = None) -> str:
    """Persist a new trip. Returns the generated trip_id."""
    now = datetime.now()
    trip_id = now.strftime("%Y%m%d_%H%M%S_") + f"{now.microsecond // 1000:03d}"
    trip_data["trip_id"] = trip_id
    trip_data["saved_at"] = now.isoformat()
    # Strip transient fields before persisting
    clean = {k: v for k, v in trip_data.items() if k not in _TRANSIENT_FIELDS}
    with SessionLocal() as session:
        try:
            session.add(_trip_to_row(trip_id, clean, user_id))
            session.commit()
        except IntegrityError:
            session.rollback()
            # Extremely unlikely collision — add more entropy
            trip_id = trip_id + f"_{secrets.token_hex(4)}"
            clean["trip_id"] = trip_id
            session.add(_trip_to_row(trip_id, clean, user_id))
            session.commit()
    return trip_id


def load_trip(trip_id: str, user_id: int | None = None, member_ok: bool = False) -> dict | None:
    """Load a single trip by ID.

    With user_id provided:
      - member_ok=False (default): only the trip owner can load.
      - member_ok=True: owner OR any joined member can load.

    Attaches computed fields: members, is_owner, invite_token (owner only).
    """
    with SessionLocal() as session:
        row = session.query(Trip).filter(Trip.trip_id == trip_id).first()
        if row is None:
            return None

        if user_id is not None:
            is_owner = row.user_id == user_id
            if not is_owner:
                if not member_ok or not _is_member(session, trip_id, user_id):
                    return None
        else:
            is_owner = False

        trip = json.loads(row.data)
        if not trip.get("trip_id"):
            trip["trip_id"] = trip_id

        # Attach computed fields (never stored in the blob)
        trip["is_owner"] = is_owner
        trip["members"]  = _get_members_for_trip(session, row)
        if is_owner:
            trip["invite_token"] = row.invite_token  # None if not yet generated
        return trip


def list_trips(user_id: int | None = None) -> list:
    """Return summary dicts for trips the user owns or has joined, newest first."""
    with SessionLocal() as session:
        result: list[dict] = []

        if user_id is not None:
            # Owned trips
            owned = (
                session.query(Trip)
                .filter(Trip.user_id == user_id)
                .order_by(Trip.saved_at.desc())
                .all()
            )
            for row in owned:
                result.append(_row_to_summary(row, is_member=False))

            # Joined trips (not owner)
            member_trip_ids = [
                tm.trip_id
                for tm in session.query(TripMember)
                .filter(TripMember.user_id == user_id)
                .all()
            ]
            if member_trip_ids:
                shared = (
                    session.query(Trip)
                    .filter(Trip.trip_id.in_(member_trip_ids))
                    .all()
                )
                for row in shared:
                    owner = session.get(User, row.user_id) if row.user_id else None
                    result.append(_row_to_summary(
                        row,
                        is_member=True,
                        owner_name=owner.name if owner else "Unknown",
                    ))
        else:
            rows = session.query(Trip).order_by(Trip.saved_at.desc()).all()
            result = [_row_to_summary(r) for r in rows]

        # Sort combined list newest-first
        result.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        return result


def update_trip(
    trip_id: str,
    trip_data: dict,
    user_id: int | None = None,
    member_ok: bool = False,
) -> bool:
    """Overwrite an existing trip with new data. Returns False if not found / not authorized."""
    clean = {k: v for k, v in trip_data.items() if k not in _TRANSIENT_FIELDS}
    with SessionLocal() as session:
        row = session.query(Trip).filter(Trip.trip_id == trip_id).first()
        if row is None:
            return False

        if user_id is not None:
            is_owner = row.user_id == user_id
            if not is_owner:
                if not member_ok or not _is_member(session, trip_id, user_id):
                    return False

        row.destination = clean.get("destination", row.destination)
        row.start_date  = clean.get("start_date",  row.start_date)
        row.end_date    = clean.get("end_date",     row.end_date)
        row.dates       = clean.get("dates",        row.dates)
        row.budget      = clean.get("budget",       row.budget)
        row.currency    = clean.get("currency",     row.currency)
        row.data        = json.dumps(clean)
        session.commit()
    return True


def delete_trip(trip_id: str, user_id: int | None = None) -> bool:
    """Delete a trip by ID. Only the owner can delete. Returns False if not found."""
    with SessionLocal() as session:
        query = session.query(Trip).filter(Trip.trip_id == trip_id)
        if user_id is not None:
            query = query.filter(Trip.user_id == user_id)
        row = query.first()
        if row is None:
            return False
        session.delete(row)
        session.commit()
    return True


# ── Sharing ───────────────────────────────────────────────────────────────────

def generate_invite_token(trip_id: str, owner_id: int) -> str | None:
    """Generate and store a unique invite token for the trip. Returns the token, or
    None if the trip doesn't exist / caller is not the owner."""
    with SessionLocal() as session:
        row = session.query(Trip).filter(
            Trip.trip_id == trip_id,
            Trip.user_id == owner_id,
        ).first()
        if row is None:
            return None
        if not row.invite_token:
            token = secrets.token_urlsafe(16)
            row.invite_token = token
            session.commit()
        return row.invite_token


def revoke_invite_token(trip_id: str, owner_id: int) -> bool:
    """Remove the invite token so the old link stops working."""
    with SessionLocal() as session:
        row = session.query(Trip).filter(
            Trip.trip_id == trip_id,
            Trip.user_id == owner_id,
        ).first()
        if row is None:
            return False
        row.invite_token = None
        session.commit()
    return True


def regenerate_invite_token(trip_id: str, owner_id: int) -> str | None:
    """Revoke old token and issue a fresh one. Returns the new token."""
    with SessionLocal() as session:
        row = session.query(Trip).filter(
            Trip.trip_id == trip_id,
            Trip.user_id == owner_id,
        ).first()
        if row is None:
            return None
        token = secrets.token_urlsafe(16)
        row.invite_token = token
        session.commit()
        return token


def get_trip_preview(token: str) -> dict | None:
    """Public: return minimal trip info for a join-link preview (no auth required)."""
    with SessionLocal() as session:
        row = session.query(Trip).filter(Trip.invite_token == token).first()
        if row is None:
            return None
        owner = session.get(User, row.user_id) if row.user_id else None
        return {
            "trip_id":     row.trip_id,
            "destination": row.destination,
            "dates":       row.dates,
            "owner_name":  owner.name if owner else "Someone",
            "owner_picture": owner.picture if owner else "",
        }


def join_trip(token: str, user_id: int) -> dict | None:
    """Add user as a member of the trip identified by token.

    Returns the trip_id on success, or None if token is invalid.
    Raises ValueError if user is already the owner or already a member.
    """
    with SessionLocal() as session:
        row = session.query(Trip).filter(Trip.invite_token == token).first()
        if row is None:
            return None
        if row.user_id == user_id:
            raise ValueError("already_owner")
        existing = session.query(TripMember).filter(
            TripMember.trip_id == row.trip_id,
            TripMember.user_id == user_id,
        ).first()
        if existing:
            raise ValueError("already_member")
        session.add(TripMember(trip_id=row.trip_id, user_id=user_id))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise ValueError("already_member")
        return row.trip_id


def get_trip_members(trip_id: str) -> list[dict]:
    """Return full member list for a trip (owner + joined members)."""
    with SessionLocal() as session:
        row = session.query(Trip).filter(Trip.trip_id == trip_id).first()
        if row is None:
            return []
        return _get_members_for_trip(session, row)


def remove_trip_member(trip_id: str, owner_id: int, member_user_id: int) -> bool:
    """Remove a member from a trip. Only the owner can do this."""
    with SessionLocal() as session:
        row = session.query(Trip).filter(
            Trip.trip_id == trip_id,
            Trip.user_id == owner_id,
        ).first()
        if row is None:
            return False
        tm = session.query(TripMember).filter(
            TripMember.trip_id == trip_id,
            TripMember.user_id == member_user_id,
        ).first()
        if tm is None:
            return False
        session.delete(tm)
        session.commit()
    return True


def leave_trip(trip_id: str, user_id: int) -> bool:
    """Remove self from a trip's member list. Returns False if not a member."""
    with SessionLocal() as session:
        tm = session.query(TripMember).filter(
            TripMember.trip_id == trip_id,
            TripMember.user_id == user_id,
        ).first()
        if tm is None:
            return False
        session.delete(tm)
        session.commit()
    return True


# ── Seeding & migration ───────────────────────────────────────────────────────

def _upsert_from_dict(session, trip_data: dict, user_id: int | None = None) -> bool:
    """Insert trip if trip_id not already in DB. Returns True if inserted."""
    trip_id = trip_data.get("trip_id")
    if not trip_id:
        return False
    if session.get(Trip, trip_id) is not None:
        return False
    clean = {k: v for k, v in trip_data.items() if k not in _TRANSIENT_FIELDS}
    session.add(_trip_to_row(trip_id, clean, user_id))
    return True


def seed_demo_trips() -> None:
    """Copy bundled demo trips into the DB if they aren't there yet."""
    demo_dir = Path(__file__).parent / "demo_trips"
    if not demo_dir.is_dir():
        return
    with SessionLocal() as session:
        for demo_file in sorted(demo_dir.glob("*.json")):
            demo = json.loads(demo_file.read_text())
            if _upsert_from_dict(session, demo):
                print(f"🌍 Seeded demo trip: {demo.get('destination')}")
        session.commit()


def migrate_from_json() -> None:
    """
    One-time migration: import any legacy JSON trip files into SQLite.
    After importing, renames each file to *.json.migrated so it is not
    re-imported on the next restart.
    """
    legacy = Path(_LEGACY_DIR)
    if not legacy.is_dir():
        return
    migrated = 0
    with SessionLocal() as session:
        for json_file in sorted(legacy.glob("*.json")):
            try:
                trip_data = json.loads(json_file.read_text())
            except Exception:
                continue
            if _upsert_from_dict(session, trip_data):
                migrated += 1
                json_file.rename(json_file.with_suffix(".json.migrated"))
        if migrated:
            session.commit()
            print(f"✅ Migrated {migrated} legacy JSON trip(s) to SQLite")
