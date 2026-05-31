import json
import os
from datetime import datetime
from pathlib import Path

from backend.db.database import SessionLocal
from backend.db.models import Trip


# Legacy JSON directory — only used during one-time migration.
_LEGACY_DIR = os.getenv("TRIPS_DIR", "data/trips")


def _row_to_summary(row: Trip) -> dict:
    return {
        "trip_id":     row.trip_id,
        "destination": row.destination or "Unknown",
        "dates":       row.dates or "",
        "saved_at":    row.saved_at or "",
        "start_date":  row.start_date or "",
        "end_date":    row.end_date or "",
        "budget":      row.budget,
        "currency":    row.currency,
    }


def _trip_to_row(trip_id: str, trip_data: dict) -> Trip:
    return Trip(
        trip_id=trip_id,
        destination=trip_data.get("destination", ""),
        start_date=trip_data.get("start_date", ""),
        end_date=trip_data.get("end_date", ""),
        dates=trip_data.get("dates", ""),
        saved_at=trip_data.get("saved_at", ""),
        budget=trip_data.get("budget"),
        currency=trip_data.get("currency"),
        data=json.dumps(trip_data),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def save_trip(trip_data: dict) -> str:
    """Persist a new trip. Returns the generated trip_id."""
    trip_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    trip_data["trip_id"] = trip_id
    trip_data["saved_at"] = datetime.now().isoformat()
    with SessionLocal() as session:
        session.add(_trip_to_row(trip_id, trip_data))
        session.commit()
    return trip_id


def load_trip(trip_id: str) -> dict | None:
    """Load a single trip by ID. Returns None if not found."""
    with SessionLocal() as session:
        row = session.get(Trip, trip_id)
        if row is None:
            return None
        trip = json.loads(row.data)
        if not trip.get("trip_id"):
            trip["trip_id"] = trip_id
        return trip


def list_trips() -> list:
    """Return summary dicts for all trips, newest first."""
    with SessionLocal() as session:
        rows = session.query(Trip).order_by(Trip.saved_at.desc()).all()
        return [_row_to_summary(r) for r in rows]


def update_trip(trip_id: str, trip_data: dict) -> bool:
    """Overwrite an existing trip with new data. Returns False if not found."""
    with SessionLocal() as session:
        row = session.get(Trip, trip_id)
        if row is None:
            return False
        row.destination = trip_data.get("destination", row.destination)
        row.start_date  = trip_data.get("start_date",  row.start_date)
        row.end_date    = trip_data.get("end_date",     row.end_date)
        row.dates       = trip_data.get("dates",        row.dates)
        row.budget      = trip_data.get("budget",       row.budget)
        row.currency    = trip_data.get("currency",     row.currency)
        row.data        = json.dumps(trip_data)
        session.commit()
    return True


def delete_trip(trip_id: str) -> bool:
    """Delete a trip by ID. Returns False if not found."""
    with SessionLocal() as session:
        row = session.get(Trip, trip_id)
        if row is None:
            return False
        session.delete(row)
        session.commit()
    return True


# ── Seeding & migration ───────────────────────────────────────────────────────

def _upsert_from_dict(session, trip_data: dict) -> bool:
    """Insert trip if trip_id not already in DB. Returns True if inserted."""
    trip_id = trip_data.get("trip_id")
    if not trip_id:
        return False
    if session.get(Trip, trip_id) is not None:
        return False
    session.add(_trip_to_row(trip_id, trip_data))
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
