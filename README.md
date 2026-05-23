# Solo Travel Agent

An AI-powered travel planning app built around **Marco** — a brutally honest, opinionated travel companion with experience in 70+ countries. Marco creates detailed trip itineraries using real-time flight, hotel, weather, and places data, then stays with you throughout the trip as an active companion.

## Features

- **Trip Planning** — Conversational itinerary generation with day-by-day breakdowns, budget estimates, and local tips
- **Real-time Data** — Live flights (Google Flights via SerpApi), hotels, restaurants, attractions, and 5-day weather forecasts
- **Agentic Tool Use** — Claude autonomously decides when to search flights, hotels, or weather to ground its advice
- **Companion Mode** — Once your trip starts, Marco gives daily context-aware advice based on your current itinerary and live weather
- **Trip Persistence** — All trips saved locally as JSON; reload and resume conversations at any time
- **Streaming Responses** — Text streams to the UI in real time as Claude generates it

## Architecture

```
User (Streamlit UI)
      │
      ▼
chat()  ←── system prompt + trip context + companion mode injections
      │
      ▼
run_agentic_loop()          ← streams Claude Sonnet 4.5
      │
      ├── tool_use? ──► execute_tool()
      │                      ├── search_flights()    → SerpApi
      │                      ├── search_hotels()     → SerpApi
      │                      ├── search_places()     → SerpApi
      │                      └── get_weather_forecast() → OpenWeather
      │
      └── end_turn → extract_itinerary() → save to data/trips/
```

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Anthropic Claude (Sonnet 4.5 for planning, Haiku 4.5 for extraction) |
| UI | Streamlit |
| External Data | SerpApi (flights, hotels, places), OpenWeather API |
| Persistence | Local JSON files (`data/trips/`) |
| Runtime | Python 3.14, [uv](https://docs.astral.sh/uv/) |

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

- **Anthropic API key** — [console.anthropic.com](https://console.anthropic.com)
- **OpenWeather API key** — [openweathermap.org/api](https://openweathermap.org/api) (free tier works)
- **SerpApi key** — [serpapi.com](https://serpapi.com) (free tier: 100 searches/month)

### 3. Run the app

```bash
streamlit run frontend/app.py
```

The app opens at `http://localhost:8501`.

## Usage

1. **Plan a Trip** — Click "Plan a New Trip", fill in destination, dates, budget, and travel style. Marco will ask follow-up questions and generate a full itinerary with real-time prices.

2. **Ask Follow-ups** — Use the "Ask Marco" chat below the itinerary to refine plans, check specific days, or get honest opinions.

3. **Companion Mode** — Once your trip is active (today's date falls within trip dates), click "Get Today's Advice" for weather-aware, day-specific guidance.

4. **Saved Trips** — All trips appear on the home screen with status badges (Upcoming / Active / Past). Click any trip to reload the full conversation.

## Project Structure

```
solo_travel_agent/
├── frontend/
│   └── app.py              # Streamlit UI — home, plan, and trip views
├── backend/
│   ├── agents/
│   │   ├── planning_agent.py   # Agentic loop, streaming, itinerary extraction
│   │   ├── tool_executor.py    # Dispatches tool calls to handlers
│   │   └── tools.py            # Tool schemas (JSON definitions for Claude)
│   ├── tools/
│   │   ├── flights.py          # SerpApi Google Flights
│   │   ├── hotels.py           # SerpApi Google Hotels
│   │   ├── places.py           # SerpApi Google Local search
│   │   └── weather.py          # OpenWeather 5-day forecast
│   ├── db/
│   │   └── trip_store.py       # JSON file-based trip persistence
│   └── prompts/
│       └── marco.md            # Marco's system prompt and personality
├── data/
│   └── trips/                  # Saved trip JSON files (gitignored)
├── main.py                     # Entry point placeholder
└── pyproject.toml              # Dependencies
```

## Marco's Persona

Marco is defined in [backend/prompts/marco.md](backend/prompts/marco.md). Key traits:

- Seasoned solo traveler, honest about risks and trade-offs
- Gives specific recommendations ("Marco's Pick 🎯"), not generic lists
- Pre-trip: detailed, structured, asks clarifying questions
- Companion mode: short, punchy, actionable, weather-aware
- Never uses corporate filler language ("Certainly!", "Of course!")

To adjust Marco's behavior, edit `backend/prompts/marco.md`.
