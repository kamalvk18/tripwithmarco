"""
Trip CRUD endpoints.

GET    /trips              → list all trips (summaries)
GET    /trips/{trip_id}   → full trip with messages
POST   /trips             → save a new trip, returns trip_id
PUT    /trips/{trip_id}   → overwrite an existing trip
DELETE /trips/{trip_id}   → delete a trip
"""

from fastapi import APIRouter, HTTPException
from backend.db.trip_store import list_trips, load_trip, save_trip, update_trip, delete_trip
from backend.api.schemas import (
    TripSummary,
    TripDetail,
    SaveTripRequest,
    UpdateTripRequest,
    TripIdResponse,
    OkResponse,
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
