# Backend CLAUDE.md

## Structure

```
backend/
├── agents/         # LLM orchestration
├── tools/          # External API integrations
├── db/             # Trip persistence
├── prompts/        # System prompts
└── api/            # FastAPI routes (empty, not yet used)
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

### weather.py
Two-step: geocode city via OpenWeather Geo API, then fetch 5-day/3-hour forecast. Aggregates 8 readings/day into daily summaries. Dominant condition is chosen by frequency. Returns `{date, condition, avg_temp, min_temp, max_temp, rain}` per day.

## DB

`trip_store.py` reads/writes JSON files in `data/trips/`. Trip IDs are timestamp strings (`20260516_225345`). The `messages` field stores the full conversation history. Trips have no schema enforcement — any dict can be saved. `update_trip()` does a full overwrite.

## Prompts

`marco.md` is the only prompt file. It is loaded at runtime (not hardcoded), so changes take effect without restarting. The prompt has two behavioral modes: **Pre-Trip** (detailed planning) and **Companion** (short, weather-aware daily advice). The mode is set by the caller via context injection, not by a flag in the prompt.
