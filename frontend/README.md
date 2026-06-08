# Marco — React Frontend

Vite + React 19 + Tailwind CSS v4 single-page application. Communicates exclusively with the FastAPI backend via the HTTP client in `src/lib/api.js`.

---

## Dev Setup

```bash
npm install
npm run dev        # http://localhost:5173 (proxies /api → http://localhost:8000)
npm run build      # outputs to dist/ (served by FastAPI in production)
npm run lint
npm run preview    # preview the production build locally
```

Requires the API server running on port 8000. Start both together from the project root:

```bash
uv run main.py --both
```

---

## Directory Layout

```
src/
├── main.jsx                   # React entry point, router setup
├── App.jsx                    # Root component, layout wrapper
├── pages/
│   ├── Home.jsx               # Trip list with status badges
│   ├── PlanTrip.jsx           # Trip planning form + streaming SSE chat
│   └── TripView.jsx           # Full trip view — all panels assembled here
├── components/
│   ├── ChatPanel.jsx          # Collapsible "Ask Marco" / companion chat
│   ├── DayCard.jsx            # Single trip day (expandable, override badge)
│   ├── BudgetPanel.jsx        # Budget breakdown vs. estimate
│   ├── ExpenseTracker.jsx     # Real-spending log with per-category tracking
│   ├── ChecklistPanel.jsx     # Auto-generated pre-trip checklist
│   ├── EmailBriefingConfig.jsx # Daily briefing email configuration
│   ├── Layout.jsx             # Page shell (nav, max-width container)
│   └── ui/
│       ├── Badge.jsx          # Status badge (upcoming / active / past)
│       ├── Button.jsx         # Primary / secondary / ghost variants
│       ├── Card.jsx           # Surface card
│       └── Spinner.jsx        # Inline loading spinner
├── hooks/
│   ├── useSSEChat.js          # SSE streaming state + tool-status messages
│   └── useWeatherCache.js     # Module-level 1-hour weather cache
└── lib/
    ├── api.js                 # All backend HTTP calls (fetch wrappers)
    ├── utils.js               # extractAllDays, tripStatus, formatMoney, cn
    └── exports.js             # buildMarkdown, buildICS, buildOfflineHTML
```

---

## Key Patterns

### SSE Streaming — `useSSEChat`

All chat and rebuild-today calls stream via `POST /api/chat/stream`. The hook manages `streaming` state and `toolStatus` (e.g. "✈️ Checking flights…") forwarded from the backend.

```js
const { streaming, toolStatus, send } = useSSEChat()

await send({
  messages,
  tripData,
  companionMode: true,
  onChunk: (chunk) => { /* append to accumulated text */ },
  onDone: () => { /* finalise and save */ },
})
```

### Weather Cache — `useWeatherCache`

Weather is fetched once per city per hour using a module-level `Map` (persists across re-renders and route changes, cleared on page refresh). On companion mode activation, `TripView` calls `getWeather()` and stores the result; it's then injected into every chat request so the backend skips its own live fetch.

```js
const { getWeather } = useWeatherCache()
const text = await getWeather('Munich', 'DE')   // cached after first call
```

### Trip Persistence Flow

1. User fills the plan form → `PlanTrip` streams Marco's response
2. On completion, `extractInfo()` (Haiku) extracts metadata → `saveTrip()` persists to backend
3. `TripView` loads the trip with `loadTrip(id)` and calls `updateTrip(id, data)` after every chat turn or panel action

### Day Overrides

Rebuilt days (from "Rebuild Today") are stored in `tripData.day_overrides[dayNum]`. `TripView` merges them at render time:

```js
content: tripData.day_overrides?.[String(day.num)] ?? day.content
```

---

## API Endpoints Used

| Method | Path | Used by |
|---|---|---|
| `GET` | `/api/trips` | `Home` |
| `GET` | `/api/trips/:id` | `TripView` |
| `POST` | `/api/trips` | `PlanTrip` (save) |
| `PUT` | `/api/trips/:id` | `ChatPanel`, `TripView` (update) |
| `DELETE` | `/api/trips/:id` | `TripView` |
| `POST` | `/api/chat/stream` | `useSSEChat` |
| `POST` | `/api/chat/extract` | `PlanTrip` |
| `GET` | `/api/chat/weather` | `useWeatherCache` |
| `POST` | `/api/trips/:id/expenses` | `ExpenseTracker` |
| `DELETE` | `/api/trips/:id/expenses/:eid` | `ExpenseTracker` |
| `POST` | `/api/trips/:id/checklist` | `ChecklistPanel` |
| `PUT` | `/api/trips/:id/checklist` | `ChecklistPanel` |
| `POST` | `/api/trips/:id}/email-config` | `EmailBriefingConfig` |
| `POST` | `/api/trips/:id/send-briefing` | `EmailBriefingConfig` |

---

## Vite Proxy

`vite.config.js` proxies `/api` and `/health` to `http://localhost:8000` in dev so you don't need CORS headers locally. In production, FastAPI serves the built `dist/` directly and handles all routes itself.
