# Marco

AI-powered travel planning app built around **Marco** — an opinionated travel companion. Marco builds day-by-day itineraries using live flight, hotel, weather, and places data via an agentic tool-use loop, then stays with you throughout the trip.

---

## Features

- **Conversational planning** — natural language trip form; Marco autonomously searches flights, hotels, weather, and local spots during planning
- **Companion mode** — weather-aware daily advice once the trip is active; auto-rebuilds today's plan around bad weather
- **Near Me** — geolocation-based activity suggestions from today's itinerary
- **Trip sharing** — invite links for group trips; per-member expense tracking with live balance settlement
- **Expense splitting** — Splitwise-style group expense tracking: log who paid, split equally or among selected members, see live per-member balances, and record settlements — no separate app needed
- **Pre-trip checklist** — auto-generated visa, health, documents, and kit list
- **Post-trip debrief** — Marco reviews the full conversation and extracts travel preference signals for future planning
- **Daily briefing email** — morning email each trip day with weather, today's plan, and remaining budget
- **Export** — Markdown, `.ics` calendar, and self-contained offline HTML
- **Google OAuth** — sign in with Google; JWT-based session management

---

## Screenshots

**Trip planning form**

![Trip planning form](docs/screenshots/Screenshot%202026-06-22%20at%201.15.15%E2%80%AFPM.png)

**Trip overview & budget estimate**

![Trip overview](docs/screenshots/Screenshot%202026-06-22%20at%201.15.34%E2%80%AFPM.png)

**Day-by-day itinerary**

![Itinerary expanded](docs/screenshots/Screenshot%202026-06-22%20at%201.17.26%E2%80%AFPM.png)

![Itinerary with booking links and Ask Marco](docs/screenshots/Screenshot%202026-06-22%20at%201.17.43%E2%80%AFPM.png)

**Interactive map & daily briefing email**

![Map and briefing email](docs/screenshots/Screenshot%202026-06-22%20at%201.17.12%E2%80%AFPM.png)

**Expense tracking & pre-trip checklist**

![Expenses and checklist](docs/screenshots/Screenshot%202026-06-22%20at%201.16.24%E2%80%AFPM.png)

**Trip sharing**

![Trip sharing and invite link](docs/screenshots/Screenshot%202026-06-22%20at%201.15.57%E2%80%AFPM.png)

**Companion mode — active trip**

![Active trip with companion mode](docs/screenshots/Screenshot%202026-06-22%20at%201.24.37%E2%80%AFPM.png)

![Companion mode itinerary detail](docs/screenshots/Screenshot%202026-06-22%20at%201.25.02%E2%80%AFPM.png)

![Companion mode chat](docs/screenshots/Screenshot%202026-06-22%20at%201.25.17%E2%80%AFPM.png)

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM — Planning & Companion | Configurable via `LLM_MODEL` (default: Claude Sonnet 4.6); streamed with tool use |
| LLM — Extraction | Configurable via `LLM_FAST_MODEL` (default: Claude Haiku 4.5) |
| LLM Provider | [LiteLLM](https://github.com/BerriAI/litellm) — provider-agnostic; works with Anthropic, DeepSeek, OpenAI-compatible gateways, etc. |
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
# Required
OPENWEATHER_API_KEY=...
SERPAPI_KEY=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
JWT_SECRET=<random-secret>
FRONTEND_URL=http://localhost:5173

# LLM — Anthropic (default)
ANTHROPIC_API_KEY=sk-ant-...

# LLM — override to use a different provider (all optional)
# LLM_MODEL=deepseek/deepseek-chat          # LiteLLM model string
# LLM_FAST_MODEL=deepseek/deepseek-chat     # for quick extraction tasks
# LLM_BASE_URL=https://ai-gateway.vercel.sh/v1   # custom/gateway endpoint
# LLM_API_KEY=<gateway-token>               # replaces provider-specific key

# Optional
RESEND_API_KEY=...     # daily briefing emails only
```

| Key | Source | Cost |
|---|---|---|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Pay per token |
| `OPENWEATHER_API_KEY` | [openweathermap.org/api](https://openweathermap.org/api) | Free tier |
| `SERPAPI_KEY` | [serpapi.com](https://serpapi.com) | Free tier: 250 searches/month |
| `RESEND_API_KEY` | [resend.com](https://resend.com) | Free tier: 3,000 emails/month |
| `GOOGLE_CLIENT_ID/SECRET` | [Google Cloud Console](https://console.cloud.google.com) → OAuth 2.0 | Free |
| `LLM_MODEL` / `LLM_FAST_MODEL` | Any [LiteLLM-supported model string](https://docs.litellm.ai/docs/providers) | Varies |
| `LLM_BASE_URL` / `LLM_API_KEY` | Your gateway provider (e.g. Vercel AI Gateway) | Varies |

**Alternative providers**

LiteLLM handles provider routing — swap the model without touching code:

```env
# DeepSeek via Vercel AI Gateway
LLM_MODEL=deepseek/deepseek-chat
LLM_FAST_MODEL=deepseek/deepseek-chat
LLM_BASE_URL=https://ai-gateway.vercel.sh/v1
LLM_API_KEY=<your-vercel-ai-gateway-token>

# Direct DeepSeek API
LLM_MODEL=deepseek/deepseek-chat
DEEPSEEK_API_KEY=sk-...
```

> **Note:** Thinking/reasoning models (e.g. DeepSeek-R1) cannot be used as `LLM_FAST_MODEL` because extraction calls use `tool_choice`, which those models don't support.

**3. Run**

```bash
uv run main.py --both     # API on :8000 + React dev server on :5173
uv run main.py --api      # API only
uv run main.py --ui       # React dev server only (requires API running)
```

**Production build**

```bash
cd frontend && npm run build   # outputs to frontend/dist/
# Deploy dist/ to Vercel; deploy backend to Render (see CLAUDE.md for details)
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
FastAPI  (/api/trips, /api/chat/stream, /api/auth, ...)
    │
    ▼
chat()  [planning_agent.py]
    │
    ├── companion_mode ──────────────────────────────────────────────────┐
    │                                                                    │
    └── orchestrate()  [orchestrator.py]                                 │
         │                                                               │
         ├── extract_trip_details()  [fast model]                        │
         │                                                               │
         ├── EXTRACT_ONLY ──┐                                            │
         ├── INCREMENTAL ───┤ plan()  [planner_agent.py]                 │
         └── FULL_PLAN      │   └── run_agentic_loop() ◄────────────────┘
              │             │         ├── llm.py (LiteLLM)
              │   ┌─────────┘         │     └── Anthropic / DeepSeek / gateway
              │   │                   └── execute_tool()  [tool_executor.py]
              ▼   │                         ├── search_flights()  → SerpApi
         run_research()                     ├── search_hotels()   → SerpApi
         [research_agent.py]               ├── search_places()   → SerpApi
              │                            └── get_weather()     → OpenWeather
              └── ResearchEvidence
                  (injected into system prompt)
    │
    ▼  [after streaming]
_sse_stream()
    ├── eval_agent.check()   ┐ concurrent
    ├── judge_itinerary()    ┘ (fast model)
    ├── check_format()         deterministic
    └── repair()  [repair_agent.py]  if failed
         └── plan() with same ResearchEvidence — no re-research
    │
    ▼
extract + save to SQLite / Postgres
```

Tool results are disk-cached (weather: 1h, flights/hotels: 6h, places: 24h) to avoid redundant API calls. INCREMENTAL requests skip research entirely — the planner works from conversation context.

The LLM layer (`backend/llm.py`) wraps LiteLLM so no provider SDK is imported directly anywhere else. Switching providers only requires changing env vars — no code changes needed.
