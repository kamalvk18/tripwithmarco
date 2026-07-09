"""
Typed data models for the multi-agent pipeline.

Each model is the contract between two stages:
  ExtractionResult  → produced by extractor, consumed by router + research agent
  ResearchEvidence  → produced by research agent, consumed by planner + critic
  PlannerInput      → assembled by orchestrator, consumed by planner agent
  CriticResult      → produced by eval/judge agents, consumed by orchestrator
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowType(str, Enum):
    COMPANION = "companion"        # Active trip, short reply, no tools
    EXTRACT_ONLY = "extract_only"  # Missing required details — ask user
    INCREMENTAL = "incremental"    # Follow-up on existing plan, no research
    FULL_PLAN = "full_plan"        # Research → plan → eval → optional repair


class Stop(BaseModel):
    """One leg of a multi-destination trip.

    The leg describes how the traveller reaches THIS stop from the previous
    one (from the trip origin for the first stop).
    """
    city: str
    country_code: str = ""                     # 2-letter ISO
    nights: int = 1
    leg_mode: str = ""                         # drive | train | bus | flight | "" (unspecified)
    travel_hours_from_previous: float | None = None
    approx_km: float | None = None             # leg distance from previous stop
    from_iata: str = ""                        # flight legs only
    to_iata: str = ""                          # flight legs only

    # Set by the orchestrator once trip dates are known — never by the LLM
    check_in: str = ""             # YYYY-MM-DD
    check_out: str = ""            # YYYY-MM-DD


class ExtractionResult(BaseModel):
    # From LLM extraction
    destination: str = ""
    city: str = ""                 # Weather lookup city (may differ from destination label)
    country_code: str = ""         # 2-letter ISO
    origin_country: str = ""       # Country user is travelling FROM
    origin_city: str = ""          # City user is travelling FROM (road trip anchor)
    is_domestic: bool | None = None
    start_date: str = ""           # YYYY-MM-DD or ""
    end_date: str = ""             # YYYY-MM-DD or ""
    budget: float | None = None
    trip_type: str = "single_destination"   # single_destination | road_trip | multi_city
    destination_flexible: bool = False      # user is open — Marco picks the destination
    has_own_vehicle: bool = False
    stops: list[Stop] = Field(default_factory=list)   # user-specified or route-agent-derived

    # From trip_data (not LLM-extracted; set by caller)
    currency: str = "EUR"
    num_travelers: int = 1
    style: str = ""                # e.g. "adventure", "luxury", "budget"

    @classmethod
    def from_sources(
        cls,
        extracted: dict[str, Any],
        trip_data: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        """Merge LLM extraction output with trip_data fields.

        Extraction wins when it produced a value (it sees the latest messages,
        including destination changes); the saved trip record fills any gaps so
        one flaky extraction call can't downgrade a known trip to EXTRACT_ONLY.
        """
        td = trip_data or {}
        raw_stops = extracted.get("stops") or td.get("stops") or []
        stops = [Stop(**s) for s in raw_stops if isinstance(s, dict) and s.get("city")]
        # "single_destination" is the extraction schema default — low signal.
        # An explicit trip_type on the saved trip (form selector) outranks it.
        extracted_type = extracted.get("trip_type") or ""
        if extracted_type == "single_destination" and td.get("trip_type"):
            extracted_type = ""
        return cls(
            destination=extracted.get("destination") or td.get("destination", ""),
            city=extracted.get("city") or td.get("city", ""),
            country_code=extracted.get("country_code") or td.get("country_code", ""),
            origin_country=extracted.get("origin_country", ""),
            origin_city=extracted.get("origin_city") or td.get("origin", ""),
            is_domestic=extracted.get("is_domestic"),
            start_date=extracted.get("start_date") or td.get("start_date", ""),
            end_date=extracted.get("end_date") or td.get("end_date", ""),
            budget=extracted.get("budget") or td.get("budget"),
            trip_type=(
                extracted_type
                or td.get("trip_type")
                or ("road_trip" if td.get("road_trip") else "single_destination")
            ),
            destination_flexible=bool(extracted.get("destination_flexible")),
            has_own_vehicle=bool(extracted.get("has_own_vehicle") or td.get("road_trip")),
            stops=stops,
            currency=td.get("currency", "EUR"),
            num_travelers=int(td.get("number_of_travelers") or 1),
            style=td.get("style", ""),
        )

    @property
    def is_multi_stop(self) -> bool:
        return self.trip_type in ("road_trip", "multi_city")

    @property
    def is_complete(self) -> bool:
        """True if we have enough to attempt full planning.

        Multi-stop trips and flexible-destination trips need an anchor
        (origin city) rather than a destination — the route agent derives
        stops, and suggest_destination() picks a destination.
        """
        anchor = self.destination or (
            (self.is_multi_stop or self.destination_flexible) and self.origin_city
        )
        return bool(anchor and self.start_date and self.end_date)

    @property
    def num_days(self) -> int | None:
        """Trip length in days, or None if dates are missing."""
        if not (self.start_date and self.end_date):
            return None
        try:
            from datetime import date
            return (date.fromisoformat(self.end_date) - date.fromisoformat(self.start_date)).days + 1
        except ValueError:
            return None


class ResearchEvidence(BaseModel):
    chosen_destination: str = ""   # "City, Country — reason", when Marco picked it
    route: str = ""                # rendered stop list for multi-stop trips
    flights: str = ""
    hotels: str = ""
    places: list[str] = Field(default_factory=list)   # one entry per search_places call
    weather: str = ""

    # Hotel names/links surfaced to the UI (populated by tool_executor)
    hotel_suggestions: list[dict[str, Any]] = Field(default_factory=list)

    # Metadata — not passed to the planner LLM
    cached: bool = False           # True if all results came from disk cache
    tools_called: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any([self.chosen_destination, self.route, self.flights, self.hotels, self.places, self.weather])

    def as_context_block(self) -> str:
        """Render evidence into a prompt-injected context string for the planner."""
        parts: list[str] = []
        if self.chosen_destination:
            parts.append(
                "## Chosen Destination\n"
                f"The user was flexible about where to go, and you chose: {self.chosen_destination}. "
                "Open your response by announcing the destination and the one-line reason, then plan as normal."
            )
        if self.route:
            parts.append(f"## Planned Route\nFollow this route and nights-per-stop exactly — hotels below were researched for these dates.\n{self.route}")
        if self.flights:
            parts.append(f"## Available Flights\n{self.flights}")
        if self.hotels:
            parts.append(f"## Available Hotels\n{self.hotels}")
        if self.places:
            parts.append("## Places & Restaurants\n" + "\n\n".join(self.places))
        if self.weather:
            parts.append(f"## Weather Forecast\n{self.weather}")
        return "\n\n".join(parts)


class PlannerInput(BaseModel):
    extraction: ExtractionResult
    evidence: ResearchEvidence
    messages: list[dict[str, Any]]   # Conversation history (tool result turns stripped)


class CriticResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    criteria: dict[str, bool | None] = Field(default_factory=dict)
    scores: dict[str, int | list[str]] | None = None   # from judge_itinerary if run

    def repair_instruction(self) -> str | None:
        """Return a targeted repair prompt when issues exist, else None."""
        if self.passed or not self.issues:
            return None
        bullets = "\n".join(f"- {issue}" for issue in self.issues)
        return (
            "The itinerary has the following issues that must be fixed:\n"
            f"{bullets}\n\n"
            "Revise the itinerary to address each issue. "
            "Keep all grounded data (flights, hotels, specific venues). "
            "Return the full corrected itinerary only."
        )
