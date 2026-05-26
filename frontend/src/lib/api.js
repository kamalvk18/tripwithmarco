/**
 * HTTP client for the Solo Travel Agent API.
 * Mirrors frontend/api_client.py — all backend calls go through here.
 */

const BASE = '/api'   // proxied to http://localhost:8000 by Vite

// ── Health ──────────────────────────────────────────────────────────────────

export async function isApiRunning() {
  try {
    const res = await fetch('/health', { signal: AbortSignal.timeout(2000) })
    return res.ok
  } catch {
    return false
  }
}

// ── Trip CRUD ────────────────────────────────────────────────────────────────

export async function listTrips() {
  const res = await fetch(`${BASE}/trips`)
  if (!res.ok) throw new Error('Failed to list trips')
  return res.json()
}

export async function loadTrip(tripId, signal) {
  const res = await fetch(`${BASE}/trips/${tripId}`, { signal })
  if (res.status === 404) return null
  if (!res.ok) throw new Error('Failed to load trip')
  return res.json()
}

export async function saveTrip(tripData) {
  const res = await fetch(`${BASE}/trips`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trip_data: tripData }),
  })
  if (!res.ok) throw new Error('Failed to save trip')
  const data = await res.json()
  return data.trip_id
}

export async function updateTrip(tripId, tripData) {
  const res = await fetch(`${BASE}/trips/${tripId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trip_data: tripData }),
  })
  return res.ok
}

export async function deleteTrip(tripId) {
  const res = await fetch(`${BASE}/trips/${tripId}`, { method: 'DELETE' })
  return res.ok
}

// ── Chat (SSE stream) ────────────────────────────────────────────────────────

/**
 * Stream Marco's response via SSE.
 *
 * @param {object[]} messages  - conversation history
 * @param {object|null} tripData
 * @param {boolean} companionMode
 * @param {(chunk: string) => void} onText      - called for each text chunk
 * @param {(name: string) => void} onToolCall   - called when Marco uses a tool
 * @param {AbortSignal} [signal]                - to cancel mid-stream
 */
export async function chatStream({
  messages,
  tripData = null,
  companionMode = false,
  onText,
  onToolCall,
  signal,
}) {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, trip_data: tripData, companion_mode: companionMode }),
    signal,
  })

  if (!res.ok) throw new Error(`API error ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()   // keep incomplete line

    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const raw = line.slice(5).trim()
      if (raw === '[DONE]') return
      try {
        const evt = JSON.parse(raw)
        if (evt.text !== undefined) onText?.(evt.text)
        if (evt.tool_call !== undefined) onToolCall?.(evt.tool_call)
      } catch { /* skip malformed */ }
    }
  }
}

// ── Weather ──────────────────────────────────────────────────────────────────

/**
 * Fetch a formatted 5-day weather forecast string for a city.
 * Returns { weather_text: "..." } or null on failure.
 * Call this once and cache the result — see useWeatherCache hook.
 */
export async function fetchWeather(city, countryCode = '') {
  try {
    const params = new URLSearchParams({ city })
    if (countryCode) params.set('country_code', countryCode)
    const res = await fetch(`${BASE}/chat/weather?${params}`, {
      signal: AbortSignal.timeout(10_000),
    })
    if (!res.ok) return null
    return res.json()   // { weather_text: "..." }
  } catch {
    return null
  }
}

// ── Extraction ───────────────────────────────────────────────────────────────

export async function extractInfo(messages, currency = 'EUR', signal) {
  const res = await fetch(`${BASE}/chat/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, currency }),
    signal,
  })
  if (!res.ok) return {}
  return res.json()
}
