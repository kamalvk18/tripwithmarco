"""
Multi-destination / road trip pipeline tests — no API keys required.

Covers: stop date assignment, ExtractionResult multi-stop merging,
deterministic per-stop research fan-out, and route-agent orchestration.

Run with: uv run pytest tests/test_road_trip.py -v
"""

import json
from unittest.mock import patch, MagicMock

from backend.agents.models import ExtractionResult, Stop
from backend.agents.route_agent import assign_stop_dates, derive_route


def _stops(*specs):
    return [Stop(city=c, nights=n) for c, n in specs]


class TestAssignStopDates:
    def test_exact_fit(self):
        stops = assign_stop_dates(_stops(("Ghent", 2), ("Bruges", 3)), "2026-08-01", "2026-08-06")
        assert [(s.check_in, s.check_out) for s in stops] == [
            ("2026-08-01", "2026-08-03"),
            ("2026-08-03", "2026-08-06"),
        ]

    def test_undershoot_last_stop_absorbs(self):
        stops = assign_stop_dates(_stops(("Ghent", 1), ("Bruges", 1)), "2026-08-01", "2026-08-06")
        assert stops[-1].nights == 4
        assert stops[-1].check_out == "2026-08-06"

    def test_overshoot_trims_tail(self):
        stops = assign_stop_dates(
            _stops(("Ghent", 3), ("Bruges", 3), ("Antwerp", 3)), "2026-08-01", "2026-08-05",
        )
        assert sum(s.nights for s in stops) == 4
        assert stops[-1].check_out == "2026-08-05"

    def test_invalid_dates_returns_unchanged(self):
        stops = _stops(("Ghent", 2))
        assert assign_stop_dates(stops, "", "") == stops


class TestMultiStopExtraction:
    def test_road_trip_complete_with_origin_only(self):
        """A road trip needs an anchor city, not a destination."""
        result = ExtractionResult.from_sources({
            "trip_type": "road_trip", "origin_city": "Amsterdam",
            "start_date": "2026-08-01", "end_date": "2026-08-09",
        })
        assert result.is_multi_stop
        assert result.is_complete

    def test_single_destination_still_requires_destination(self):
        result = ExtractionResult.from_sources({
            "origin_city": "Amsterdam",
            "start_date": "2026-08-01", "end_date": "2026-08-09",
        })
        assert not result.is_complete

    def test_form_road_trip_flag_sets_trip_type(self):
        """The form toggle must reach the pipeline even if text extraction misses it."""
        result = ExtractionResult.from_sources({}, {"road_trip": True, "origin": "Amsterdam"})
        assert result.trip_type == "road_trip"
        assert result.has_own_vehicle
        assert result.origin_city == "Amsterdam"

    def test_user_named_stops_are_parsed(self):
        result = ExtractionResult.from_sources({
            "trip_type": "road_trip",
            "stops": [{"city": "Ghent", "nights": 2}, {"city": "Bruges", "nights": 3}],
        })
        assert [s.city for s in result.stops] == ["Ghent", "Bruges"]


class TestDeterministicResearch:
    def _extraction(self):
        stops = assign_stop_dates(
            [Stop(city="Ghent", country_code="BE", nights=2, drive_hours_from_previous=2.0),
             Stop(city="Bruges", country_code="BE", nights=1, drive_hours_from_previous=0.8),
             Stop(city="Antwerp", country_code="BE", nights=2, drive_hours_from_previous=1.2)],
            "2026-08-01", "2026-08-06",
        )
        return ExtractionResult(
            trip_type="road_trip", origin_city="Amsterdam", has_own_vehicle=True,
            start_date="2026-08-01", end_date="2026-08-06", stops=stops,
        )

    def test_fan_out_is_pure_python(self):
        """Multi-stop research must not make any LLM call."""
        from backend.agents import research_agent

        captured = []

        def fake_execute(name, params, collected=None, _lock=None):
            captured.append((name, params))
            return f"{name} result"

        with (
            patch("backend.agents.research_agent.execute_tool", side_effect=fake_execute),
            patch("backend.agents.research_agent.llm.complete", side_effect=AssertionError("LLM must not be called")),
        ):
            evidence = research_agent.run_research_stops(self._extraction())

        hotel_calls = [p for n, p in captured if n == "search_hotels"]
        places_calls = [p for n, p in captured if n == "search_places"]
        flight_calls = [p for n, p in captured if n == "search_flights"]

        assert len(hotel_calls) == 3                        # one per stop
        assert hotel_calls[0]["check_in_date"] == "2026-08-01"
        assert hotel_calls[0]["check_out_date"] == "2026-08-03"
        assert len(places_calls) == 2                       # only 2+ night stops (Bruges skipped)
        assert flight_calls == []                           # road trip — never flights
        assert "Ghent: 2 night(s)" in evidence.route
        assert "### Ghent (2026-08-01 → 2026-08-03)" in evidence.hotels

    def test_route_appears_in_planner_context(self):
        from backend.agents import research_agent

        with patch("backend.agents.research_agent.execute_tool", return_value="data"):
            evidence = research_agent.run_research_stops(self._extraction())

        block = evidence.as_context_block()
        assert "## Planned Route" in block
        assert block.index("## Planned Route") < block.index("## Available Hotels")


class TestRouteAgent:
    def test_derive_route_returns_dated_stops(self):
        route_input = {
            "stops": [
                {"city": "Ghent", "country_code": "BE", "nights": 3, "drive_hours_from_previous": 2.2},
                {"city": "Bruges", "country_code": "BE", "nights": 2, "drive_hours_from_previous": 0.8},
                {"city": "Antwerp", "country_code": "BE", "nights": 3, "drive_hours_from_previous": 1.3},
            ],
            "route_label": "Amsterdam → Ghent → Bruges → Antwerp → Amsterdam",
        }

        def fake(**kw):
            tc = MagicMock()
            tc.id = "r1"
            tc.function.name = "save_route"
            tc.function.arguments = json.dumps(route_input)
            msg = MagicMock(content=None, tool_calls=[tc])
            resp = MagicMock()
            resp.choices = [MagicMock(message=msg)]
            resp.usage = None
            return resp

        extraction = ExtractionResult(
            trip_type="road_trip", origin_city="Amsterdam", has_own_vehicle=True,
            start_date="2026-08-01", end_date="2026-08-09",
        )
        with patch("litellm.completion", side_effect=fake):
            stops, label = derive_route(extraction)

        assert label.startswith("Amsterdam →")
        assert sum(s.nights for s in stops) == 8            # exactly the trip nights
        assert stops[0].check_in == "2026-08-01"
        assert stops[-1].check_out == "2026-08-09"

    def test_derive_route_failure_returns_empty(self):
        def fake(**kw):
            raise RuntimeError("provider down")

        extraction = ExtractionResult(
            trip_type="road_trip", origin_city="Amsterdam",
            start_date="2026-08-01", end_date="2026-08-09",
        )
        with patch("litellm.completion", side_effect=fake):
            stops, label = derive_route(extraction)
        assert stops == [] and label == ""


class TestOrchestration:
    def test_road_trip_full_plan_uses_route_agent_and_stop_research(self):
        from backend.agents import orchestrator

        extraction_out = {
            "destination": "", "trip_type": "road_trip", "origin_city": "Amsterdam",
            "has_own_vehicle": True, "start_date": "2026-08-01", "end_date": "2026-08-09",
            "stops": [],
        }
        derived = assign_stop_dates(
            [Stop(city="Ghent", country_code="BE", nights=4, drive_hours_from_previous=2.2),
             Stop(city="Bruges", country_code="BE", nights=4, drive_hours_from_previous=0.8)],
            "2026-08-01", "2026-08-09",
        )
        tool_events = []

        def fake_plan(planner_input, system_base, on_tool_call=None, collected=None):
            assert planner_input.extraction.stops, "planner must receive the derived route"
            yield "## Day 1 — Amsterdam to Ghent"

        with (
            patch("backend.agents.orchestrator.extract_trip_details", return_value=extraction_out),
            patch("backend.agents.orchestrator.derive_route", return_value=(derived, "Amsterdam → Ghent → Bruges")) as mock_route,
            patch("backend.agents.orchestrator.run_research_stops") as mock_stops_research,
            patch("backend.agents.orchestrator.run_research", side_effect=AssertionError("single-dest research must not run")),
            patch("backend.agents.orchestrator.plan", side_effect=fake_plan),
        ):
            from backend.agents.models import ResearchEvidence
            mock_stops_research.return_value = ResearchEvidence(route="- Ghent", hotels="h")
            out = "".join(orchestrator.orchestrate(
                [{"role": "user", "content": "8 night road trip from Amsterdam, I have a car"}],
                "SYSTEM", None, on_tool_call=lambda n, i: tool_events.append(n),
            ))

        assert "Day 1" in out
        mock_route.assert_called_once()
        mock_stops_research.assert_called_once()
        passed_extraction = mock_stops_research.call_args[0][0]
        assert passed_extraction.destination == "Amsterdam → Ghent → Bruges"
        assert "planning_route" in tool_events

    def test_user_specified_stops_skip_route_agent(self):
        from backend.agents import orchestrator

        extraction_out = {
            "destination": "Ghent → Bruges", "trip_type": "road_trip", "origin_city": "Amsterdam",
            "has_own_vehicle": True, "start_date": "2026-08-01", "end_date": "2026-08-06",
            "stops": [{"city": "Ghent", "nights": 2}, {"city": "Bruges", "nights": 3}],
        }

        def fake_plan(planner_input, system_base, on_tool_call=None, collected=None):
            stops = planner_input.extraction.stops
            assert stops[0].check_in == "2026-08-01", "dates must be assigned to user stops"
            yield "plan"

        with (
            patch("backend.agents.orchestrator.extract_trip_details", return_value=extraction_out),
            patch("backend.agents.orchestrator.derive_route", side_effect=AssertionError("route agent must not run")),
            patch("backend.agents.orchestrator.run_research_stops") as mock_stops_research,
            patch("backend.agents.orchestrator.plan", side_effect=fake_plan),
        ):
            from backend.agents.models import ResearchEvidence
            mock_stops_research.return_value = ResearchEvidence(route="- Ghent")
            out = "".join(orchestrator.orchestrate(
                [{"role": "user", "content": "road trip: Ghent 2 nights then Bruges 3 nights"}],
                "SYSTEM", None,
            ))

        assert out == "plan"
        mock_stops_research.assert_called_once()
