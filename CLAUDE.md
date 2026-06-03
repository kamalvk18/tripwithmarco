# CLAUDE.md

## Project Overview

Solo Travel Agent is a React + FastAPI + Anthropic Claude app. The AI persona "Marco" plans trips and acts as a real-time travel companion. The app uses an agentic loop where Claude autonomously calls tools (flights, hotels, places, weather) to ground its itineraries in live data.

## Development Commands

```bash
# Install dependencies (uses uv, not pip)
uv sync

# Run API server only
uv run main.py --api          # http://localhost:8000 — docs at /docs
uvicorn backend.api.app:app --reload --port 8000   # direct

# Run React dev server only (requires API running separately)
uv run main.py --ui           # http://localhost:5173

# Run both together (recommended for local dev)
uv run main.py --both

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
- **claude-haiku-4-5-20251001** — Quick extraction tasks: `extract_trip_details()` only. Companion mode also uses Haiku (short replies, cost-sensitive). Do not use Haiku for anything requiring high-quality output.

### Companion Mode Context Injection
When `companion_mode=True`, `chat()` pre-fetches live weather and injects today's itinerary section directly into the system prompt (not as a user message). This gives Marco context without requiring tool calls at runtime. See `planning_agent.py:chat()`.

### Persistence
Trips are stored in a SQLite database (`data/trips.db` locally, `/data/trips.db` on Fly.io). Each row holds indexed summary columns plus a full JSON blob of the trip. The `messages` array inside the blob is the full conversation history — the trip record IS the conversation. `trip_store.py` is the only entry point; no other module touches the DB directly. To swap to Postgres, set `DATABASE_URL=postgresql://...`.

### Tool Result Caching
`backend/tools/cache.py` caches SerpApi and OpenWeather HTTP responses to disk. TTLs: weather 1h, flights/hotels 6h, places 24h. This only skips external API calls — Claude inference still runs on every request.

## File Map

| File | Responsibility |
|---|---|
| `frontend/src/` | React app (Vite + TypeScript) |
| `backend/config.py` | Central constants: model names, token limits, timeouts |
| `backend/agents/planning_agent.py` | Agentic loop, chat entry point, itinerary/day extraction |
| `backend/agents/tool_executor.py` | Dispatches tool name → handler, formats result for Claude |
| `backend/agents/tools.py` | JSON schema definitions for all 4 tools |
| `backend/tools/flights.py` | SerpApi Google Flights query + parse + format |
| `backend/tools/hotels.py` | SerpApi Google Hotels query + parse + format |
| `backend/tools/places.py` | SerpApi Google Local query + parse + format |
| `backend/tools/weather.py` | OpenWeather geo + forecast query + format |
| `backend/tools/cache.py` | Disk cache for external API calls (TTL-based) |
| `backend/db/database.py` | SQLAlchemy engine, session factory, `init_db()` |
| `backend/db/models.py` | `Trip` SQLAlchemy model |
| `backend/db/trip_store.py` | save/load/list/update/delete + JSON migration |
| `backend/prompts/marco.md` | Marco's system prompt — personality, modes, tool usage rules |
| `backend/api/app.py` | FastAPI app factory, auth middleware, CORS, route registration |
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

## Deployment Architecture

Production stack: **Neon** (Postgres) + **Render** (backend) + **Vercel** (frontend).

### Backend — Render
- Deploy via Docker (`Dockerfile` is Python-only; no Node stage)
- Set all env vars as Render environment variables
- `DATABASE_URL` must point to the Neon connection string

### Frontend — Vercel
- Root directory: `frontend/`
- Build command: `npm run build` / output: `dist`
- `vercel.json` handles SPA rewrites (already committed)
- Set `VITE_API_URL` = your Render backend URL (e.g. `https://solo-travel-agent.onrender.com`)

### Database — Neon (Postgres)
- Copy the connection string from Neon dashboard → set as `DATABASE_URL` on Render
- One-time migration from SQLite:
  ```bash
  SQLITE_FILE=data/trips.db DATABASE_URL=postgresql://... uv run scripts/migrate_to_postgres.py
  ```

### Google OAuth
After deploying, add to Google Cloud Console → OAuth client → Authorized redirect URIs:
- `https://<render-app>.onrender.com/api/auth/google/callback`

And to Authorized JavaScript origins:
- `https://<vercel-app>.vercel.app`

## Environment Variables

Required in `.env` (local) / Render env vars (production):
- `ANTHROPIC_API_KEY` — Claude API
- `OPENWEATHER_API_KEY` — Free tier at openweathermap.org
- `SERPAPI_KEY` — Free tier: 250 searches/month
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — Google OAuth
- `JWT_SECRET` — random secret for signing JWTs
- `FRONTEND_URL` — frontend origin (e.g. `https://<app>.vercel.app`); used for OAuth redirect

Optional:
- `DATABASE_URL` — SQLAlchemy URL (defaults to `sqlite:///data/trips.db`; set to `postgresql://...` for Postgres)
- `ALLOWED_ORIGINS` — comma-separated extra CORS origins (e.g. your Vercel URL)
- `CRON_SECRET` — protects the `/api/send-briefings` cron endpoint
- `RESEND_API_KEY` / `RESEND_FROM` — email briefing delivery

## Itinerary Parsing

`extract_all_days()` in `planning_agent.py` uses regex to split itinerary text into day objects. It handles markdown headers (`# Day 1`, `**Day 1**`, `Day 1:`, etc.). If Marco's output format changes significantly, this regex may need updating.

## FastAPI Layer

`backend/api/app.py` is the FastAPI application. Swagger docs at `http://localhost:8000/docs`.

The streaming endpoint wraps the sync `chat()` generator using `starlette.concurrency.iterate_in_threadpool` so it doesn't block the event loop. All trip and chat logic still flows through `planning_agent.py:chat()` — the API layer adds no business logic.

On startup, the lifespan handler: creates DB tables → migrates any legacy JSON files → seeds demo trips.

## Known Limitations

- `data/` grows indefinitely (SQLite DB + cache files); no automatic cleanup
- SerpApi free tier is 250 searches/month — budget searches carefully in dev
- `test.py` uses Google Gemini (unrelated to the main app) — do not treat it as a test suite
