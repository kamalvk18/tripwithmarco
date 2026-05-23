# CLAUDE.md

## Project Overview

Solo Travel Agent is a Streamlit + Anthropic Claude app. The AI persona "Marco" plans trips and acts as a real-time travel companion. The app uses an agentic loop where Claude autonomously calls tools (flights, hotels, places, weather) to ground its itineraries in live data.

## Development Commands

```bash
# Install dependencies (uses uv, not pip)
uv sync

# Run the app (two equivalent ways)
streamlit run frontend/app.py
uv run main.py

# Run tests (no API keys required)
uv run pytest tests/ -v

# Add a dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>
```

## Key Architecture Decisions

### Agentic Loop
`backend/agents/planning_agent.py:run_agentic_loop()` is the core. It streams Claude Sonnet 4.5, intercepts `tool_use` stop reasons, dispatches to `tool_executor.py`, appends results back to `messages`, and loops until `end_turn`. Do not break this streaming/looping pattern — it is the foundation of the tool use behavior.

### Two Models in Use
- **claude-sonnet-4-5-20250929** — All planning and companion responses (streaming)
- **claude-haiku-4-5-20251001** — Quick extraction tasks: `extract_trip_details()` only. Do not use Haiku for anything requiring high-quality output.

### Companion Mode Context Injection
When `companion_mode=True`, `chat()` pre-fetches live weather and injects today's itinerary section directly into the system prompt (not as a user message). This gives Marco context without requiring tool calls at runtime. See `planning_agent.py:chat()`.

### Persistence
Trips are plain JSON in `data/trips/{timestamp}.json`. The `messages` array is the full conversation history — the trip JSON IS the conversation. `trip_store.py` is a thin wrapper around `json.load/dump`. No database.

## File Map

| File | Responsibility |
|---|---|
| `frontend/app.py` | All Streamlit UI: home, plan form, trip view, companion chat |
| `backend/config.py` | Central constants: model names, token limits, timeouts |
| `backend/agents/planning_agent.py` | Agentic loop, chat entry point, itinerary/day extraction |
| `backend/agents/tool_executor.py` | Dispatches tool name → handler, formats result for Claude |
| `backend/agents/tools.py` | JSON schema definitions for all 4 tools |
| `backend/tools/flights.py` | SerpApi Google Flights query + parse + format |
| `backend/tools/hotels.py` | SerpApi Google Hotels query + parse + format |
| `backend/tools/places.py` | SerpApi Google Local query + parse + format |
| `backend/tools/weather.py` | OpenWeather geo + forecast query + format |
| `backend/db/trip_store.py` | save/load/list/update/delete trip JSON files |
| `backend/prompts/marco.md` | Marco's system prompt — personality, modes, tool usage rules |
| `backend/api/app.py` | FastAPI app factory, CORS, route registration |
| `backend/api/schemas.py` | Pydantic request/response models |
| `backend/api/routes/trips.py` | Trip CRUD endpoints |
| `backend/api/routes/chat.py` | SSE streaming + sync chat endpoints |
| `tests/test_planning_agent.py` | Unit tests for extract_all_days, get_trip_day, etc. |
| `tests/test_tools.py` | Unit tests for parse/format functions in all 4 tool modules |
| `tests/test_api.py` | API endpoint tests (all routes, mocked dependencies) |

## Adding a New Tool

1. Implement the handler in `backend/tools/<toolname>.py` with a `search_<toolname>()` and `format_<toolname>_for_marco()` function.
2. Add the JSON schema entry in `backend/agents/tools.py` in the `TOOLS` list.
3. Add a dispatch case in `backend/agents/tool_executor.py:execute_tool()`.
4. Update `backend/prompts/marco.md` with when and how Marco should use it.

## Environment Variables

Required in `.env`:
- `ANTHROPIC_API_KEY` — Claude API
- `OPENWEATHER_API_KEY` — Free tier at openweathermap.org
- `SERPAPI_KEY` — Free tier: 100 searches/month

## Itinerary Parsing

`extract_all_days()` in `planning_agent.py` uses regex to split itinerary text into day objects. It handles markdown headers (`# Day 1`, `**Day 1**`, `Day 1:`, etc.). The day content is displayed in Streamlit expanders. If Marco's output format changes significantly, this regex may need updating.

## FastAPI Layer

`backend/api/app.py` is the FastAPI application. Start it with:

```bash
uv run main.py --api          # via entry point
uvicorn backend.api.app:app --reload --port 8000   # direct
```

Swagger docs at `http://localhost:8000/docs`.

**Routes:**
- `GET /health` — liveness check
- `GET/POST/PUT/DELETE /api/trips[/{id}]` — trip CRUD
- `POST /api/chat` — non-streaming (returns full JSON)
- `POST /api/chat/stream` — SSE streaming (yields `data: {"text": "..."}` chunks, ends with `data: [DONE]`)

The streaming endpoint wraps the sync `chat()` generator using `starlette.concurrency.iterate_in_threadpool` so it doesn't block the event loop. All trip and chat logic still flows through `planning_agent.py:chat()` — the API layer adds no business logic.

## Known Limitations

- No authentication — all trips are accessible to anyone with filesystem access
- `data/trips/` grows indefinitely; no cleanup
- SerpApi free tier is 100 searches/month — budget searches carefully in dev
- `test.py` uses Google Gemini (unrelated to the main app) — do not treat it as a test suite
