# Backend CLAUDE.md

## Structure

```
backend/
├── agents/         # LLM orchestration
├── tools/          # External API integrations
├── db/             # Trip persistence
├── prompts/        # System prompts
├── email/          # Daily briefing email (Resend)
└── api/            # FastAPI routes
```

## Agents

### planning_agent.py

Entry point is `chat(messages, trip_data, companion_mode)`. It:
1. Loads `marco.md` as the base system prompt
2. Appends current date and trip context
3. In companion mode: injects `get_weather_forecast()` result + today's day section into the system prompt
4. Calls `run_agentic_loop()` and yields streamed text chunks

`run_agentic_loop()` streams from Claude, intercepts `tool_use`, dispatches via `tool_executor.execute_tool()`, appends `tool_result` blocks, and loops. Yield only text chunks to callers.

`extract_trip_details()` uses Haiku (not Sonnet) — it is a cheap structured extraction call, not a conversation turn. Returns `{destination, city, country_code, start_date, end_date}`.

### tools.py

The `TOOLS` list is passed directly to the Claude API as the `tools` parameter. Each entry follows Anthropic's tool schema format. Input schemas use JSON Schema (not Pydantic).

### tool_executor.py

`execute_tool(tool_name, tool_input)` is the only public function. It returns a formatted string (natural language) that gets inserted as a `tool_result` message. All formatting happens here via `format_*_for_marco()` functions from each tool module.

## Tools

Each tool module follows the same pattern:
1. `search_<tool>(...)` — calls external API, returns raw parsed data (list of dicts)
2. `parse_<tool>(raw)` — normalizes the API response
3. `format_<tool>_for_marco(data, ...)` — converts to natural language string for Claude

API keys are read from environment variables via `os.getenv()` with no fallback — missing keys will cause `None` to be passed as the API key, which will fail at the HTTP level.

### flights.py
Calls SerpApi `google_flights` engine. Parses `best_flights` and `other_flights` arrays. `outbound_date` format must be `YYYY-MM-DD`. IATA codes are required for both origin and destination.

### hotels.py
Calls SerpApi `google_hotels` engine. Returns name, price/night, total price, rating, review count, top amenities.

### places.py
Calls SerpApi `google_local` engine with a freeform `query` (e.g., "street food near old town"). Returns name, rating, hours, address, price level.

When SerpApi rejects a location as unsupported (e.g. very remote or sub-region strings like "Hanle, Ladakh, India"), `search_places()` automatically retries with progressively broader fallbacks ("Ladakh, India", then "India") before giving up — all within a single tool call. If all fallbacks fail, `format_places_for_marco()` returns an explicit "do not retry" message so Claude doesn't loop on failed searches.

### weather.py
Two-step: geocode city via OpenWeather Geo API, then fetch 5-day/3-hour forecast. Aggregates 8 readings/day into daily summaries. Dominant condition is chosen by frequency. Returns `{date, condition, avg_temp, min_temp, max_temp, rain}` per day.

## DB

`trip_store.py` is the only entry point for persistence — no other module touches the DB directly.

- Storage: SQLite via SQLAlchemy (`data/trips.db` locally). Swap to Postgres (e.g. Neon) with `DATABASE_URL=postgresql://...`.
- Schema: `Trip` table in `models.py` — indexed summary columns (`trip_id`, `destination`, `start_date`, `end_date`, `saved_at`, `budget`, `currency`) plus a `data TEXT` column holding the full trip JSON blob.
- Trip IDs are timestamp strings (`20260516_225345`). The `messages` field inside the blob is the full conversation history.
- `update_trip()` rewrites the JSON blob and syncs the indexed columns. No partial updates at the DB layer — callers load, mutate, then call `update_trip()`.
- On startup, `migrate_from_json()` imports any legacy `.json` files found in `TRIPS_DIR` and renames them to `.json.migrated`.
- Group trips have a `TripMember` table linking `trip_id` + `user_id` with a `role` (`owner` / `member`). Invite tokens are stored in the `Trip` JSON blob.

## Email

`email/briefing.py` — generates and sends the daily morning briefing via Resend. Called by `email/scheduler.py` (APScheduler, fires at 06:00 local time per trip). The `/api/send-briefings` endpoint can also trigger it manually (protected by `CRON_SECRET`).

Sender address is read from `RESEND_FROM` env var (default: `Marco <marco@marco.app>`).

## API Routes

### auth.py — `/api/auth`
| Method | Path | Description |
|---|---|---|
| `GET` | `/google/login-url` | Returns the Google OAuth redirect URL |
| `GET` | `/google/login` | Redirects browser to Google OAuth |
| `GET` | `/google/callback` | Handles OAuth callback, issues JWT |
| `GET` | `/me` | Returns the current user from the JWT |

### trips.py — `/api/trips`
Standard CRUD plus expenses, settlements, balances, checklist, debrief, email config, and sharing/invite endpoints. See `routes/trips.py` for the full list.

### chat.py — `/api/chat`
| Method | Path | Description |
|---|---|---|
| `POST` | `/stream` | SSE streaming chat |
| `POST` | `` | Sync chat (non-streaming) |
| `GET` | `/weather` | Live weather for a city |
| `POST` | `/extract` | Haiku extraction of trip metadata |

### admin.py — `/api/admin`
| Method | Path | Description |
|---|---|---|
| `GET` | `/stats` | User and trip counts (admin only) |

## Prompts

`marco.md` is the only prompt file. It is loaded at runtime (not hardcoded), so changes take effect without restarting. The prompt has two behavioral modes: **Pre-Trip** (detailed planning) and **Companion** (short, weather-aware daily advice). The mode is set by the caller via context injection, not by a flag in the prompt.
