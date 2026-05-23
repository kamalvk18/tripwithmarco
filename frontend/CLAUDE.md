# Frontend CLAUDE.md

## Overview

Single Streamlit file: `app.py`. All UI state lives in `st.session_state`. The app has three views controlled by `st.session_state.view`: `"home"`, `"plan"`, and `"trip"`.

## Views

### Home (`view == "home"`)
Lists all saved trips from `trip_store.list_trips()`. Each trip card shows destination, dates, and a status badge. Buttons: "Resume Trip" (loads trip → `view = "trip"`) and "Delete Trip".

### Plan (`view == "plan"`)
A form with fields for destination, origin, dates, budget, currency, travel styles, dietary preferences, driver's license, and special notes. On submit, calls `chat()` with the user message and streams the response into the session.

### Trip (`view == "trip"`)
Main trip view. Composed of:
1. **Itinerary display** — `extract_all_days()` splits the itinerary into day sections shown as Streamlit expanders. Current trip day is highlighted.
2. **Ask Marco chat** — text input that appends to `messages`, calls `chat()`, streams response.
3. **Companion mode panel** — "Get Today's Advice" button calls `chat()` with `companion_mode=True`. Shows weather + today's itinerary. Conversation stored in `trip_data["companion_messages"]`.

## Session State Keys

| Key | Type | Description |
|---|---|---|
| `view` | str | Current view: `"home"`, `"plan"`, `"trip"` |
| `messages` | list | Full conversation history (OpenAI-style role/content dicts) |
| `trip_data` | dict | Current trip metadata + messages |
| `trip_id` | str | ID of currently loaded trip |
| `itinerary` | str | Raw itinerary text (extracted from first assistant message) |
| `itinerary_generated` | bool | Whether itinerary extraction has run |
| `companion_mode` | bool | Whether companion mode is active |
| `generating` | bool | Whether a streaming response is in progress |

## Streaming Pattern

```python
for chunk in chat(messages, trip_data, companion_mode):
    response_text += chunk
    placeholder.markdown(response_text + "▌")
placeholder.markdown(response_text)
```

The `▌` cursor gives a typing effect. After streaming completes, the final text replaces the placeholder and is appended to `messages`.

## Trip Auto-Save

After each assistant response, the app calls `update_trip(trip_id, trip_data)` to persist the updated conversation. On first assistant response in a new trip, `save_trip()` is called instead and the returned `trip_id` is stored in session state.

## Itinerary Extraction

After the first assistant response, `extract_itinerary(messages)` scans for a message containing "day 1" (case-insensitive). If found, `extract_all_days()` splits it into day dicts. Then `extract_trip_details()` (Haiku call) extracts `city`, `country_code`, `start_date`, `end_date`.

## Adding UI Features

- New form fields go in the Plan view's `st.form` block — pass them as part of the user message string.
- New trip metadata (extra fields on the trip dict) should be added to both the Plan view's submit handler and `trip_store.list_trips()` if they need to appear on the Home view.
- Companion mode context (what Marco sees) is controlled in `planning_agent.py:chat()`, not here.
