# Solo Travel Agent

An AI-powered travel planning app built around **Marco** — a brutally honest, opinionated travel companion with experience in 70+ countries. Marco creates detailed trip itineraries using real-time flight, hotel, weather, and places data, then stays with you throughout the trip as an active companion.

---

## Features

### Planning
- **Conversational trip form** — destination, origin, dates, budget, travel style, dietary needs, and driver's licence; Marco handles the rest
- **Real-time data** — live flights (Google Flights via SerpApi), hotels, restaurants, attractions, and 5-day weather forecasts all fetched during planning
- **Agentic tool use** — Claude autonomously decides when to search flights, hotels, weather, or local spots; live status messages ("✈️ Checking flights…") stream to the UI as it works
- **Day-by-day itinerary** — full trip broken into expandable day cards; today's card is highlighted automatically
- **Budget overview** — per-category cost breakdown (flights, accommodation, food, activities, transport) extracted from the itinerary; over-budget warning shown when Marco's estimate exceeds your stated budget

### During the Trip
- **Companion mode** — once your trip is active, Marco switches into a short, punchy, weather-aware mode; leads with today's forecast and proactively restructures the plan if needed
- **Rebuild Today** — regenerates just today's day plan around current live weather without touching the rest of the itinerary; rebuilt days are stored as overrides and shown with a 🔄 badge
- **Expense tracker** — log real spending per category (flights, accommodation, food, activities, transport, misc) tracked against Marco's estimates; running total vs. budget shown at a glance
- **Daily briefing email** — optional morning email each trip day with weather, today's plan, and remaining budget; configure once, delivered automatically

### Before the Trip
- **Pre-trip checklist** — auto-generated from destination and passport country: visa requirements, recommended vaccinations, travel insurance, emergency numbers, and packing essentials; items are persistent and checkable

### Export & Offline
- **Markdown export** — full itinerary as `.md` for Notion, Obsidian, or any notes app
- **Calendar export** — `.ics` file with one all-day event per trip day; imports directly into Google Calendar, Apple Calendar, or Outlook
- **Offline HTML** — self-contained single-file HTML (no CDN, no external dependencies); dark-mode; save to phone before the flight

### Technical
- **React + Vite frontend** — fast SPA with SSE streaming, collapsible panels, and Tailwind CSS dark theme
- **FastAPI REST layer** — full REST API (`/api/trips` CRUD, `/api/chat/stream`, `/api/chat/weather`, and more); Swagger docs at `/docs`
- **Client-side weather cache** — weather is fetched once per city per hour in the browser and injected into companion-mode requests, avoiding redundant OpenWeather calls
- **Trip persistence** — all trips saved locally as JSON; reload and resume any conversation at any time
- **CI** — GitHub Actions runs the full test suite on every push

---

## Architecture

```
┌────────────────────────────────────────┐
│   React SPA (Vite)                     │  frontend/src/
│   pages/: Home, PlanTrip, TripView     │
│   hooks/: useSSEChat, useWeatherCache  │
│   lib/api.js — HTTP client             │
└──────────────────┬─────────────────────┘
                   │ HTTP (SSE + REST)
                   ▼
┌────────────────────────────────────────┐
│   FastAPI API                          │  backend/api/
│   /api/trips           (CRUD)          │
│   /api/chat/stream     (SSE)           │
│   /api/chat/weather    (forecast)      │
│   /api/chat/extract                    │
│   /api/trips/{id}/expenses             │
│   /api/trips/{id}/checklist            │
│   /api/trips/{id}/email-config         │
│   /api/trips/{id}/send-briefing        │
│   /api/send-briefings  (cron job)      │
└──────────────────┬─────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│   planning_agent.py                    │
│   chat() → run_agentic_loop()          │  streams Claude Sonnet
│        │                               │
│        ├── tool_use? ───► execute_tool()
│        │                      ├── search_flights()  → SerpApi
│        │                      ├── search_hotels()   → SerpApi
│        │                      ├── search_places()   → SerpApi
│        │                      └── get_weather()     → OpenWeather
│        │
│        └── end_turn → extract_trip_details()    (Haiku)
│                     → extract_budget_breakdown() (Haiku)
│                     → save to data/trips/
└────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM — Planning & Companion | Claude Sonnet 4.5 (streaming, tool use) |
| LLM — Extraction | Claude Haiku 4.5 (trip details, budget breakdown) |
| Frontend | React 19 + Vite + Tailwind CSS v4 |
| API | FastAPI + Uvicorn |
| External Data | SerpApi (flights, hotels, places), OpenWeather API |
| Email | Resend |
| Persistence | Local JSON files (`data/trips/`) |
| Runtime | Python 3.14, [uv](https://docs.astral.sh/uv/) |
| CI | GitHub Actions |

---

## Setup

### 1. Install Python dependencies

```bash
uv sync
```

### 2. Install frontend dependencies

```bash
cd frontend && npm install
```

### 3. Configure API keys

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENWEATHER_API_KEY=...
SERPAPI_KEY=...
RESEND_API_KEY=...        # optional — only needed for daily briefing emails
```

| Key | Where to get it | Cost |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Pay per token |
| `OPENWEATHER_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) | Free tier works |
| `SERPAPI_KEY` | [serpapi.com](https://serpapi.com) | Free tier: 100 searches/month |
| `RESEND_API_KEY` | [resend.com](https://resend.com) | Free tier: 3,000 emails/month |

### 4. Run the app

```bash
# Recommended — starts API server + React dev server together
uv run main.py --both

# Or run them separately:
uv run main.py --api        # FastAPI on http://localhost:8000
uv run main.py --ui         # React dev server on http://localhost:5173
```

The React UI opens at **`http://localhost:5173`**.  
API docs (Swagger) are at **`http://localhost:8000/docs`**.

### Production build

```bash
cd frontend && npm run build   # outputs to frontend/dist/
uv run main.py --api           # FastAPI serves the built SPA from /
```

---

## Usage

### Plan a Trip
1. Click **"Plan a New Trip"**
2. Fill in destination, origin, dates, budget, travel style, dietary preferences, and any notes
3. Click **"Generate My Trip Plan"** — Marco searches live flights, hotels, weather, and local spots, then builds your full itinerary
4. Follow up in the **Ask Marco** chat below the itinerary to refine plans or explore alternatives
5. Click **Save Trip** to persist it

### On the Trip
Once today's date falls within your trip dates:
- **🧭 Companion Mode** — Marco switches to short, weather-aware advice; fetches live weather once and caches it for the session
- **Rebuild Today** — completely regenerates today's day plan around current weather; rebuilt version shown with a 🔄 badge

### Expense Tracker
- Log spending per category as you go; Marco's budget estimates shown alongside for comparison
- Available on active and past trips

### Pre-trip Checklist
- Click **Generate Checklist** — Marco produces a personalised checklist covering visa, health, insurance, documents, and kit based on your destination and passport country
- Check off items as you prepare; state is persisted

### Daily Briefing Email
- On any upcoming or active trip, click **"Get Marco's daily briefing in your inbox"**
- Enter your email; choose a send time; toggle on
- You'll receive a morning email each trip day: weather, today's plan, and remaining budget

### Export Options
Open **📤 Export** on any trip:
- **📝 Markdown** — paste into Notion, Obsidian, iA Writer
- **📅 Calendar (.ics)** — import into Google Calendar, Apple Calendar, or Outlook
- **📱 Offline HTML** — self-contained file; save to phone before flying

### Saved Trips
All trips on the home screen with status badges:
- 🗓️ **Upcoming** — shows days until departure
- ✈️ **Active** — shows which day of the trip you're on
- ✅ **Past** — completed trips

---

## Project Structure

```
solo_travel_agent/
├── .github/
│   └── workflows/
│       └── test.yml                 # CI — runs pytest on every push
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Home.jsx             # Trip list + status badges
│   │   │   ├── PlanTrip.jsx         # Trip planning form + SSE chat
│   │   │   └── TripView.jsx         # Full trip view (all panels)
│   │   ├── components/
│   │   │   ├── ChatPanel.jsx        # Collapsible Ask Marco / Companion chat
│   │   │   ├── DayCard.jsx          # Expandable day section with override badge
│   │   │   ├── BudgetPanel.jsx      # Budget breakdown vs. estimate
│   │   │   ├── ExpenseTracker.jsx   # Real spending log
│   │   │   ├── ChecklistPanel.jsx   # Pre-trip checklist
│   │   │   ├── EmailBriefingConfig.jsx  # Daily briefing email setup
│   │   │   └── ui/                  # Badge, Button, Card, Spinner
│   │   ├── hooks/
│   │   │   ├── useSSEChat.js        # SSE streaming + tool-status state
│   │   │   └── useWeatherCache.js   # Module-level 1-hour weather cache
│   │   └── lib/
│   │       ├── api.js               # HTTP client for all backend calls
│   │       ├── utils.js             # extractAllDays, tripStatus, formatMoney
│   │       └── exports.js           # buildMarkdown, buildICS, buildOfflineHTML
│   ├── package.json
│   └── vite.config.js
├── backend/
│   ├── config.py                    # Central constants (model names, token limits)
│   ├── agents/
│   │   ├── planning_agent.py        # Agentic loop, streaming, extraction
│   │   ├── tool_executor.py         # Dispatches tool calls to handlers
│   │   └── tools.py                 # Tool schemas (JSON definitions for Claude)
│   ├── tools/
│   │   ├── flights.py               # SerpApi Google Flights integration
│   │   ├── hotels.py                # SerpApi Google Hotels integration
│   │   ├── places.py                # SerpApi Google Local search
│   │   └── weather.py               # OpenWeather 5-day forecast
│   ├── api/
│   │   ├── app.py                   # FastAPI app factory + CORS + SPA serving
│   │   ├── schemas.py               # Pydantic request/response models
│   │   └── routes/
│   │       ├── trips.py             # Trip CRUD + expenses + checklist + email config
│   │       └── chat.py              # SSE stream, sync chat, weather, extract
│   ├── db/
│   │   └── trip_store.py            # JSON file-based trip persistence
│   └── prompts/
│       └── marco.md                 # Marco's system prompt and personality
├── tests/
│   ├── test_planning_agent.py       # Unit tests for itinerary parsing and date logic
│   ├── test_tools.py                # Unit tests for flight/hotel/places/weather formatters
│   └── test_api.py                  # API endpoint tests (all routes, mocked)
├── data/
│   └── trips/                       # Saved trip JSON files (gitignored)
├── main.py                          # Entry point (--both / --api / --ui)
└── pyproject.toml                   # Python dependencies (managed by uv)
```

---

## Running Tests

No API keys required — all external calls are mocked.

```bash
uv run pytest tests/ -v
```

81 tests covering itinerary parsing, date logic, tool formatters, and all API endpoints.

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

### Medium priority
- **"What's near me?" mode** — when on an active trip, use browser geolocation to show the nearest activities from the itinerary or suggest alternatives based on current position
- **Post-trip debrief** — after trip ends, Marco reviews the original plan vs. what actually happened, extracts preference signals ("loved the food scene, hated crowded museums"), and stores them to inform future planning
- **Day timeline view** — hour-by-hour visual timeline for each day (09:00 → activity → 12:30 → lunch → 14:00 → activity) rather than a text block
- **Budget reality check during planning** — use actual prices from flight/hotel tool results to validate the budget before generating the full itinerary, rather than estimating afterwards

### Larger features
- **Authentication** — simple user accounts so multiple people can use the same deployment without data mixing
- **Docker + deployment** — `Dockerfile` + `docker-compose.yml` for hosting on Fly.io, Railway, or Render
- **Multi-city / multi-leg trips** — support trips with multiple destinations (Amsterdam → Berlin → Prague), with inter-city transport planning
- **Direct booking API integration** — replace SerpApi with Amadeus (flights) and direct hotel APIs for richer data and no 100 searches/month limit
- **Shareable trip links** — generate a read-only public link to share an itinerary
