import json
import os
from datetime import datetime

TRIPS_DIR = "data/trips"

def ensure_storage():
    """Make sure the storage directory exists."""
    os.makedirs(TRIPS_DIR, exist_ok=True)

def save_trip(trip_data: dict) -> str:
    """Save a trip to disk. Returns the trip ID."""
    ensure_storage()
    
    trip_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    trip_data["trip_id"] = trip_id
    trip_data["saved_at"] = datetime.now().isoformat()
    
    filepath = os.path.join(TRIPS_DIR, f"{trip_id}.json")
    
    with open(filepath, "w") as f:
        json.dump(trip_data, f, indent=2)
    
    return trip_id

def load_trip(trip_id: str) -> dict | None:
    """Load a specific trip by ID."""
    filepath = os.path.join(TRIPS_DIR, f"{trip_id}.json")
    
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, "r") as f:
        return json.load(f)

def list_trips() -> list:
    """List all saved trips."""
    ensure_storage()
    trips = []
    
    for filename in sorted(os.listdir(TRIPS_DIR), reverse=True):
        if filename.endswith(".json"):
            filepath = os.path.join(TRIPS_DIR, filename)
            with open(filepath, "r") as f:
                trip = json.load(f)
                trips.append({
                    "trip_id": trip.get("trip_id"),
                    "destination": trip.get("destination", "Unknown"),
                    "dates": trip.get("dates", ""),
                    "saved_at": trip.get("saved_at", "")
                })
    
    return trips

def update_trip(trip_id: str, trip_data: dict) -> bool:
    """Overwrite an existing trip with updated data."""
    filepath = os.path.join(TRIPS_DIR, f"{trip_id}.json")
    if not os.path.exists(filepath):
        return False
    with open(filepath, "w") as f:
        json.dump(trip_data, f, indent=2)
    return True

def delete_trip(trip_id: str) -> bool:
    """Delete a trip by ID."""
    filepath = os.path.join(TRIPS_DIR, f"{trip_id}.json")

    if os.path.exists(filepath):
        os.remove(filepath)
        return True

    return False