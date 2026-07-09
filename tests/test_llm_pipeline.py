"""
Pipeline robustness tests — exercise the real llm.complete()/stream() wrappers
against a mocked litellm.completion, plus the SSE failure paths.

These exist because the unit tests mock at the function level (extract_trip_details,
chat, ...) and would not catch a broken llm wrapper or SSE protocol regression.

Run with: uv run pytest tests/test_llm_pipeline.py -v
"""

import json
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from backend import llm
from backend.api.app import app
from backend.auth.deps import get_current_user

_MOCK_USER = {"id": 1, "google_id": "g123", "email": "test@example.com", "name": "Test User", "picture": ""}
app.dependency_overrides[get_current_user] = lambda: _MOCK_USER

client = TestClient(app)


def _tool_call_response(name: str, arguments: dict):
    """Build a fake non-streaming litellm response containing one tool call."""
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments)
    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    resp.usage = MagicMock(
        prompt_tokens=10, completion_tokens=5,
        prompt_tokens_details=None,
        cache_read_input_tokens=0, cache_creation_input_tokens=0,
    )
    return resp


class TestLLMComplete:
    def test_complete_builds_messages_and_returns_tool_calls(self):
        """Guards the _build_messages(model, system, messages) call signature."""
        captured = {}

        def fake(**kw):
            captured.update(kw)
            return _tool_call_response("save_trip_details", {"destination": "Kraków, Poland"})

        with patch("litellm.completion", side_effect=fake):
            result = llm.complete(
                model="deepseek/deepseek-chat",
                system="extract things",
                messages=[{"role": "user", "content": "hi"}],
                tools=[{"type": "function", "function": {"name": "save_trip_details"}}],
                tool_choice={"type": "function", "function": {"name": "save_trip_details"}},
                temperature=0,
            )

        assert captured["messages"][0] == {"role": "system", "content": "extract things"}
        assert captured["messages"][1] == {"role": "user", "content": "hi"}
        assert captured["temperature"] == 0
        assert result["tool_calls"][0]["input"] == {"destination": "Kraków, Poland"}

    def test_complete_omits_temperature_when_not_set(self):
        captured = {}

        def fake(**kw):
            captured.update(kw)
            return _tool_call_response("save_destination", {"destination": "x", "reason": "y"})

        with patch("litellm.completion", side_effect=fake):
            llm.complete(model="deepseek/deepseek-chat", messages=[{"role": "user", "content": "hi"}])

        assert "temperature" not in captured


class TestTruncationFlag:
    def test_length_finish_reason_sets_truncated(self):
        def fake_stream(**kw):
            def gen():
                chunk = MagicMock()
                chunk.choices = [MagicMock(
                    delta=MagicMock(content="Day 1 partial", tool_calls=None),
                    finish_reason="length",
                )]
                chunk.usage = None
                yield chunk
            return gen()

        with patch("litellm.completion", side_effect=fake_stream):
            from backend.agents.planning_agent import run_agentic_loop
            collected = {}
            text = "".join(run_agentic_loop(
                [{"role": "user", "content": "hi"}], "sys", collected=collected,
            ))

        assert text == "Day 1 partial"
        assert collected.get("_truncated") is True

    def test_normal_stop_does_not_set_truncated(self):
        def fake_stream(**kw):
            def gen():
                chunk = MagicMock()
                chunk.choices = [MagicMock(
                    delta=MagicMock(content="done", tool_calls=None),
                    finish_reason="stop",
                )]
                chunk.usage = None
                yield chunk
            return gen()

        with patch("litellm.completion", side_effect=fake_stream):
            from backend.agents.planning_agent import run_agentic_loop
            collected = {}
            "".join(run_agentic_loop(
                [{"role": "user", "content": "hi"}], "sys", collected=collected,
            ))

        assert "_truncated" not in collected


class TestLLMResilience:
    def test_complete_passes_timeout_and_retries(self):
        captured = {}

        def fake(**kw):
            captured.update(kw)
            return _tool_call_response("save_eval", {"passed": True, "issues": [], "criteria": {}})

        with patch("litellm.completion", side_effect=fake):
            llm.complete(model="deepseek/deepseek-chat", messages=[{"role": "user", "content": "hi"}])

        assert captured["timeout"] > 0
        assert captured["num_retries"] >= 1

    def test_stream_passes_timeout_without_retries(self):
        captured = {}

        def fake(**kw):
            captured.update(kw)
            return iter(())

        with patch("litellm.completion", side_effect=fake):
            list(llm.stream(model="deepseek/deepseek-chat", messages=[{"role": "user", "content": "hi"}]))

        assert captured["timeout"] > 0
        assert "num_retries" not in captured  # a mid-stream retry would duplicate visible text


class TestExtractionFallback:
    def test_trip_data_fills_gaps_when_extraction_fails(self):
        """A flaky extraction ({}) must not downgrade a saved trip to EXTRACT_ONLY."""
        from backend.agents.models import ExtractionResult

        trip_data = {
            "destination": "Kraków, Poland", "city": "Kraków", "country_code": "PL",
            "start_date": "2026-08-01", "end_date": "2026-08-05",
            "budget": 800.0, "currency": "EUR",
        }
        result = ExtractionResult.from_sources({}, trip_data)
        assert result.is_complete
        assert result.destination == "Kraków, Poland"
        assert result.num_days == 5

    def test_extraction_wins_over_trip_data(self):
        """Destination changes mid-conversation must not be masked by the saved record."""
        from backend.agents.models import ExtractionResult

        trip_data = {"destination": "Kraków, Poland", "start_date": "2026-08-01", "end_date": "2026-08-05"}
        extracted = {"destination": "Osaka, Japan", "start_date": "2026-09-10", "end_date": "2026-09-15"}
        result = ExtractionResult.from_sources(extracted, trip_data)
        assert result.destination == "Osaka, Japan"
        assert result.start_date == "2026-09-10"


class TestEmptyResultCaching:
    def test_empty_hotel_results_are_not_cached(self, tmp_path, monkeypatch):
        from backend.tools import cache
        from backend.agents import tool_executor

        monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path))
        tool_input = {"destination": "Nowhere", "check_in_date": "2026-08-01", "check_out_date": "2026-08-05"}

        with patch("backend.agents.tool_executor.search_hotels", return_value=[]):
            tool_executor.execute_tool("search_hotels", tool_input)

        assert cache.get_cached("search_hotels", tool_input) is None

    def test_nonempty_hotel_results_are_cached(self, tmp_path, monkeypatch):
        from backend.tools import cache
        from backend.agents import tool_executor

        monkeypatch.setattr(cache, "CACHE_DIR", str(tmp_path))
        tool_input = {"destination": "Kraków", "check_in_date": "2026-08-01", "check_out_date": "2026-08-05"}
        hotels = [{"name": "Hotel Stary", "price_per_night": 120}]

        with (
            patch("backend.agents.tool_executor.search_hotels", return_value=hotels),
            patch("backend.agents.tool_executor.format_hotels_for_marco", return_value="1 hotel found"),
        ):
            tool_executor.execute_tool("search_hotels", tool_input)

        assert cache.get_cached("search_hotels", tool_input) == "1 hotel found"


# A response that passes looks_like_itinerary (Day 1/2 headings, >400 chars)
_ITINERARY = (
    "## Day 1 — Arrival\nMorning: land, hotel check-in, old town walk.\n"
    "## Day 2 — City\nMorning: museum visit, evening: local food tour.\n"
) + "Afternoon details and restaurant recommendations. " * 10


def _wait_for(condition, timeout=2.0):
    """Poll until the fire-and-forget executor write lands."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met within timeout")


class TestEvalLoop:
    def _stream(self, eval_result, judge_sampled=False, chat_fn=None):
        """Run a planning stream with a stubbed eval verdict; return (response, logged)."""
        logged = {}

        def default_chat(*a, **kw):
            # Serves both the first pass and (via the fallback repair path)
            # the repair generation — repair output passes the format check.
            yield _ITINERARY

        with (
            patch("backend.api.routes.chat.chat", side_effect=chat_fn or default_chat),
            patch("backend.api.routes.chat.eval_agent.check", return_value=eval_result),
            patch("backend.api.routes.chat.judge_itinerary", return_value={"coverage": 4, "specificity": 4, "budget_fit": 4, "data_usage": 4, "flags": []}),
            patch("backend.api.routes.chat._write_eval_log", side_effect=logged.update),
            patch("backend.api.routes.chat.random.random", return_value=0.0 if judge_sampled else 1.0),
        ):
            res = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "plan it"}]})
        _wait_for(lambda: logged)
        return res, logged

    def test_casual_reply_skips_eval_judge_and_logging(self):
        """Non-itinerary responses must not spend LLM calls on eval or judge."""
        def fake_chat(*a, **kw):
            yield "The museum opens at 9am — go early to beat the crowds."

        logged = {}
        with (
            patch("backend.api.routes.chat.chat", side_effect=fake_chat),
            patch("backend.api.routes.chat.eval_agent.check") as mock_check,
            patch("backend.api.routes.chat.judge_itinerary") as mock_judge,
            patch("backend.api.routes.chat._write_eval_log", side_effect=logged.update),
        ):
            res = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "when does it open?"}]})

        assert res.status_code == 200
        mock_check.assert_not_called()
        mock_judge.assert_not_called()
        assert not logged

    def test_no_conflicts_failure_is_advisory_not_repair(self):
        """A conflict flag alone must not trigger a 2x-cost regeneration."""
        res, logged = self._stream({
            "passed": False, "issues": ["Day 2 has venues 40km apart at the same time"],
            "criteria": {"days_have_content": True, "no_conflicts": False},
        })
        assert "eval_correction" not in res.text
        assert logged["repair_ran"] is False
        assert logged["eval_passed"] is False          # still recorded for tuning
        assert "40km apart" in logged["issues"]

    def test_empty_day_failure_triggers_and_verifies_repair(self):
        res, logged = self._stream({
            "passed": False, "issues": ["Day 2 section is empty"],
            "criteria": {"days_have_content": False, "no_conflicts": True},
        })
        assert "eval_correction" in res.text
        assert logged["repair_ran"] is True
        assert logged["repair_format_passed"] is True  # repair output re-verified

    def test_judge_only_runs_when_sampled(self):
        _, logged_sampled = self._stream(
            {"passed": True, "issues": [], "criteria": {"days_have_content": True, "no_conflicts": True}},
            judge_sampled=True,
        )
        assert logged_sampled["judge_scores"] is not None

        _, logged_skipped = self._stream(
            {"passed": True, "issues": [], "criteria": {"days_have_content": True, "no_conflicts": True}},
            judge_sampled=False,
        )
        assert logged_skipped["judge_scores"] is None


class TestSSEProtocol:
    def test_stream_error_emits_error_event_and_done(self):
        def boom(*a, **kw):
            raise RuntimeError("provider exploded")
            yield  # pragma: no cover — makes this a generator

        with patch("backend.api.routes.chat.chat", side_effect=lambda *a, **kw: boom()):
            res = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "hi"}]})

        assert res.status_code == 200
        assert '"error":' in res.text
        assert res.text.rstrip().endswith("data: [DONE]")
        # The raw exception message must not leak to the client
        assert "provider exploded" not in res.text

    def test_stream_opens_with_connected_comment_and_status(self):
        """Bytes must flow immediately so proxies don't kill the idle stream."""
        def fake_chat(*a, **kw):
            yield "hello"

        with patch("backend.api.routes.chat.chat", side_effect=fake_chat):
            res = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "hi"}]})

        assert res.text.startswith(": connected")
        assert '{"tool_call": "analyzing_trip"}' in res.text

    def test_companion_mode_skips_planning_status(self):
        def fake_chat(*a, **kw):
            yield "short reply"

        with patch("backend.api.routes.chat.chat", side_effect=fake_chat):
            res = client.post("/api/chat/stream", json={
                "messages": [{"role": "user", "content": "hi"}],
                "companion_mode": True,
            })

        assert "analyzing_trip" not in res.text

    def test_truncated_response_skips_repair(self):
        """A truncated plan must never start repair — it would truncate identically."""
        logged = {}

        def fake_chat(messages, trip_data=None, companion_mode=False, on_tool_call=None, collected=None):
            if collected is not None:
                collected["_truncated"] = True
            yield _ITINERARY

        failing_eval = {
            "passed": False, "issues": ["Day 2 cut off"],
            "criteria": {"days_have_content": False, "no_conflicts": True},
        }
        with (
            patch("backend.api.routes.chat.chat", side_effect=fake_chat),
            patch("backend.api.routes.chat.eval_agent.check", return_value=failing_eval),
            patch("backend.api.routes.chat._write_eval_log", side_effect=logged.update),
            patch("backend.api.routes.chat.random.random", return_value=1.0),  # judge not sampled
        ):
            res = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "plan it"}]})

        assert res.status_code == 200
        assert "eval_correction" not in res.text
        _wait_for(lambda: logged)
        assert logged["truncated"] is True
        assert logged["repair_ran"] is False
