# Solo Travel Agent

AI-powered travel planning app built around **Marco** — an opinionated travel companion. Marco builds day-by-day itineraries using live flight, hotel, weather, and places data via an agentic tool-use loop, then stays with you throughout the trip.

---

## Features

- **Conversational planning** — natural language trip form; Marco autonomously searches flights, hotels, weather, and local spots during planning
- **Companion mode** — weather-aware daily advice once the trip is active; auto-rebuilds today's plan around bad weather
- **Near Me** — geolocation-based activity suggestions from today's itinerary
- **Expense tracker** — log real spending vs. Marco's estimates per category
- **Pre-trip checklist** — auto-generated visa, health, documents, and kit list
- **Post-trip debrief** — Marco reviews the full conversation and extracts travel preference signals for future planning
- **Daily briefing email** — morning email each trip day with weather, today's plan, and remaining budget
- **Export** — Markdown, `.ics` calendar, and self-contained offline HTML

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM — Planning & Companion | Claude Sonnet 4.5 (streaming, tool use) |
| LLM — Extraction | Claude Haiku 4.5 |
| Frontend | React 19 + Vite + Tailwind CSS v4 |
| API | FastAPI + Uvicorn |
| Persistence | SQLite via SQLAlchemy (swappable to Postgres via `DATABASE_URL`) |
| External data | SerpApi (flights, hotels, places), OpenWeather API |
| Email | Resend |
| Runtime | Python 3.14, [uv](https://docs.astral.sh/uv/) |

---

## Setup

**1. Install dependencies**

```bash
uv sync
cd frontend && npm install
```

**2. Configure `.env`**

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENWEATHER_API_KEY=...
SERPAPI_KEY=...
RESEND_API_KEY=...     # optional — daily briefing emails only
```

| Key | Source | Cost |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Pay per token |
| `OPENWEATHER_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) | Free tier |
| `SERPAPI_KEY` | [serpapi.com](https://serpapi.com) | Free tier: 250 searches/month |
| `RESEND_API_KEY` | [resend.com](https://resend.com) | Free tier: 3,000 emails/month |

**3. Run**

```bash
uv run main.py --both     # API on :8000 + React dev server on :5173
uv run main.py --api      # API only
uv run main.py --ui       # React dev server only (requires API running)
```

**Production build**

```bash
cd frontend && npm run build   # outputs to frontend/dist/
uv run main.py --api           # FastAPI serves the built SPA
```

---

## Tests

No API keys required — all external calls are mocked.

```bash
uv run pytest tests/ -v
```

---

## Architecture

```
React SPA (Vite)
    │ HTTP + SSE
    ▼
FastAPI  (/api/trips, /api/chat/stream, ...)
    │
    ▼
planning_agent.py → run_agentic_loop()
    │
    ├── tool_use → execute_tool()
    │       ├── search_flights()   → SerpApi
    │       ├── search_hotels()    → SerpApi
    │       ├── search_places()    → SerpApi
    │       └── get_weather()      → OpenWeather
    │
    └── end_turn → extract + save to SQLite
```

Tool results are disk-cached (weather: 1h, flights/hotels: 6h, places: 24h) to avoid redundant API calls.
