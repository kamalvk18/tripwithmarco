# Solo Travel Agent

An AI-powered travel planning app built around **Marco** — a brutally honest, opinionated travel companion with experience in 70+ countries. Marco creates detailed trip itineraries using real-time flight, hotel, weather, and places data, then stays with you throughout the trip as an active companion.

---

## Features

### Planning
- **Conversational trip form** — destination, dates, budget, travel style, dietary needs, and driver's licence in a single structured form; Marco handles the rest
- **Real-time data** — live flights (Google Flights via SerpApi), hotels, restaurants, attractions, and 5-day weather forecasts all fetched during planning
- **Agentic tool use** — Claude autonomously decides when to search flights, hotels, weather, or local spots; you see live status ("✈️ Checking flights...") as it works
- **Day-by-day itinerary** — full trip broken into expandable day cards; today's card opens automatically when you're on the trip
- **Budget tracking** — per-category cost breakdown (flights, accommodation, food, activities, transport) extracted from the itinerary; shows how Marco's estimate compares to your stated budget with an over-budget warning if needed

### During the Trip
- **Companion mode** — once your trip is active, Marco switches into a short, punchy, weather-aware mode; leads with what today's forecast means for the plan and proactively restructures if needed
- **Rebuild Today** — one button regenerates just today's day plan around current live weather, without touching the rest of the itinerary; rebuilt days are stored as overrides and shown with a 🔄 badge

### Export & Offline
- **Markdown export** — full itinerary as `.md` for Notion, Obsidian, or any notes app
- **Calendar export** — `.ics` file with one all-day event per trip day; imports directly into Google Calendar, Apple Calendar, or Outlook
- **Offline HTML** — self-contained single-file HTML (no CDN, no external dependencies); dark-mode aware; save to your phone before the flight and read it on the plane with no internet

### Technical
- **FastAPI REST layer** — full REST API (`/api/trips` CRUD, `/api/chat/stream`, `/api/chat/extract`) separate from the Streamlit UI; Swagger docs at `/docs`
- **SSE streaming** — server-sent events with live tool-call notifications forwarded to the UI
- **Trip persistence** — all trips saved locally as JSON; reload and resume any conversation at any time
- **CI** — GitHub Actions runs the full test suite on every push

---

## Architecture

```
┌──────────────────────────────┐
│   Streamlit UI               │  frontend/app.py
│   (frontend/api_client.py)   │
└──────────┬───────────────────┘
           │ HTTP (SSE + REST)
           ▼
┌──────────────────────────────┐
│   FastAPI API                │  backend/api/
│   /api/trips  (CRUD)         │
│   /api/chat/stream  (SSE)    │
│   /api/chat/extract          │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│   planning_agent.py          │
│   chat() → run_agentic_loop()│  streams Claude Sonnet
│        │                     │
│        ├── tool_use? ──────► execute_tool()
│        │                         ├── search_flights()  → SerpApi
│        │                         ├── search_hotels()   → SerpApi
│        │                         ├── search_places()   → SerpApi
│        │                         └── get_weather()     → OpenWeather
│        │
│        └── end_turn → extract_trip_details()  (Haiku)
│                     → extract_budget_breakdown() (Haiku)
│                     → save to data/trips/
└──────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM — Planning | Claude Sonnet 4.5 (streaming, tool use) |
| LLM — Extraction | Claude Haiku 4.5 (trip details, budget breakdown) |
| UI | Streamlit |
| API | FastAPI + Uvicorn |
| External Data | SerpApi (flights, hotels, places), OpenWeather API |
| Persistence | Local JSON files (`data/trips/`) |
| Runtime | Python 3.14, [uv](https://docs.astral.sh/uv/) |
| CI | GitHub Actions |

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure API keys

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENWEATHER_API_KEY=...
SERPAPI_KEY=...
```

| Key | Where to get it | Cost |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Pay per token |
| `OPENWEATHER_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) | Free tier works |
| `SERPAPI_KEY` | [serpapi.com](https://serpapi.com) | Free tier: 100 searches/month |

### 3. Run the app

```bash
# Recommended — starts API server + Streamlit UI together
uv run main.py --both

# Or run them in separate terminals:
uv run main.py --api        # FastAPI on http://localhost:8000
uv run main.py              # Streamlit on http://localhost:8501
```

The Streamlit UI opens at `http://localhost:8501`.  
API docs (Swagger) are at `http://localhost:8000/docs`.

---

## Usage

### Plan a Trip
1. Click **"Plan a New Trip"** in the sidebar
2. Fill in destination, origin, dates, budget, travel style, dietary preferences, and any special notes
3. Click **"Generate My Trip Plan"** — Marco searches live flights, hotels, weather, and local spots, then builds your full itinerary

### During Planning
- **Budget Overview** — expander shows Marco's estimated costs per category vs. your stated budget; a warning appears if the estimate is over budget
- **Ask Marco** — follow-up chat below the itinerary to refine plans, add days, or get honest opinions
- **Regenerate Plan** — rebuild the entire itinerary from scratch using your original prompt

### On the Trip
Once today's date falls within your trip dates:
- **"I'm on Day X — What should I do?"** — switches Marco into companion mode; he checks live weather and gives short, actionable, weather-aware advice for today
- **"🔄 Rebuild Today"** — completely regenerates today's day plan around current weather; original plan is preserved, rebuilt version shown with a 🔄 badge
- Today's day card is automatically expanded and marked with "← today"

### Export Options
Open the **📤 Export & Share** expander on any trip:
- **📝 Markdown** — paste into Notion, Obsidian, iA Writer, or any notes app
- **📅 Calendar (.ics)** — import into Google Calendar, Apple Calendar, or Outlook; each day becomes an all-day event with the itinerary in the description
- **📱 Offline HTML** — self-contained file that works without internet; save to phone before flying

### Saved Trips
All trips appear in the sidebar and on the home screen with status badges:
- 🗓️ **Upcoming** — shows days until departure
- ✈️ **Active** — shows which day of the trip you're on
- ✅ **Past** — completed trips

---

## Project Structure

```
solo_travel_agent/
├── .github/
│   └── workflows/
│       └── test.yml            # CI — runs pytest on every push
├── frontend/
│   ├── app.py                  # Streamlit UI — home, plan, and trip views
│   └── api_client.py           # HTTP client — wraps all backend API calls
├── backend/
│   ├── config.py               # Central constants (model names, token limits, timeouts)
│   ├── agents/
│   │   ├── planning_agent.py   # Agentic loop, streaming, itinerary/budget extraction
│   │   ├── tool_executor.py    # Dispatches tool calls to handlers
│   │   └── tools.py            # Tool schemas (JSON definitions for Claude)
│   ├── tools/
│   │   ├── flights.py          # SerpApi Google Flights integration
│   │   ├── hotels.py           # SerpApi Google Hotels integration
│   │   ├── places.py           # SerpApi Google Local search
│   │   └── weather.py          # OpenWeather 5-day forecast
│   ├── api/
│   │   ├── app.py              # FastAPI application factory + CORS
│   │   ├── schemas.py          # Pydantic request/response models
│   │   └── routes/
│   │       ├── trips.py        # GET/POST/PUT/DELETE /api/trips
│   │       └── chat.py         # POST /api/chat/stream, /api/chat, /api/chat/extract
│   ├── db/
│   │   └── trip_store.py       # JSON file-based trip persistence
│   └── prompts/
│       └── marco.md            # Marco's system prompt and personality
├── tests/
│   ├── test_planning_agent.py  # Unit tests for itinerary parsing and date logic
│   ├── test_tools.py           # Unit tests for flight/hotel/places/weather formatters
│   └── test_api.py             # API endpoint tests (all routes, mocked dependencies)
├── data/
│   └── trips/                  # Saved trip JSON files (gitignored)
├── main.py                     # Entry point (--both, --api, or Streamlit only)
└── pyproject.toml              # Dependencies (managed by uv)
```

---

## Running Tests

No API keys required — all external calls are mocked.

```bash
uv run pytest tests/ -v
```

80 tests covering itinerary parsing, date logic, tool formatters, and all API endpoints.

---

## Marco's Persona

Marco is defined in [backend/prompts/marco.md](backend/prompts/marco.md). Key traits:

- Seasoned solo traveler, 70+ countries; honest about risks and trade-offs
- Gives specific recommendations ("Marco's Pick 🎯"), not generic lists
- **Pre-trip mode**: detailed, structured, asks clarifying questions, uses real data
- **Companion mode**: short, punchy, actionable, phone-friendly; leads with weather impact
- Never uses corporate filler language ("Certainly!", "Of course!", "Great question!")
- Proactively restructures plans around bad weather rather than just warning

To adjust Marco's behaviour, edit `backend/prompts/marco.md` — changes take effect without restarting.

---

## Roadmap

Features planned but not yet implemented, roughly in priority order:

### High priority
- **Proactive daily briefing email** — automated morning email each day of the trip: weather, today's plan, remaining budget. Uses existing companion mode logic + a cron job + Resend/SendGrid. The main differentiator vs. Claude.ai (which is purely reactive).
- **Actual expense tracker** — log real spending during the trip per category, tracked against Marco's estimates. Requires a simple add-expense UI and a `spending` field in the trip JSON.
- **Pre-trip document checklist** — auto-generated from destination + passport country: visa requirements, passport validity check, recommended vaccinations, travel insurance, emergency numbers, nearest embassy.

### Medium priority
- **"What's near me?" mode** — when on an active trip, use browser geolocation to show the nearest activities from the itinerary or suggest alternatives based on current position.
- **Post-trip debrief** — after trip ends, Marco reviews the original plan vs. what actually happened, extracts preference signals ("loved the food scene, hated crowded museums"), and stores them to inform future planning.
- **Day timeline view** — hour-by-hour visual timeline for each day (09:00 → activity → 12:30 → lunch → 14:00 → activity) rather than a text block.
- **Budget reality check during planning** — use actual prices from flight/hotel tool results to validate the budget before generating the full itinerary, rather than estimating afterwards.

### Larger features
- **Authentication** — simple user accounts so multiple people can use the same deployment without data mixing.
- **Docker + deployment** — `Dockerfile` + `docker-compose.yml` (API + Streamlit as two services) for hosting on Fly.io, Railway, or Render.
- **Multi-city / multi-leg trips** — support trips with multiple destinations (Amsterdam → Berlin → Prague), with inter-city transport planning.
- **Direct booking API integration** — replace SerpApi with Amadeus (flights) and direct hotel APIs for richer data and no 100 searches/month limit.
- **Shareable trip links** — generate a read-only public link to share an itinerary.
