/**
 * HTTP client for the Solo Travel Agent API.
 * All requests include the stored JWT as a Bearer token.
 * On 401 the token is cleared and the browser is sent to /login.
 */

import { getToken } from '@/contexts/AuthContext'

const BASE = (import.meta.env.VITE_API_URL ?? '') + '/api'

function authHeaders(extra = {}) {
  const token = getToken()
  return {
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

export async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: authHeaders(options.headers),
  })
  if (res.status === 401) {
    localStorage.removeItem('sta_auth_token')
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  return res
}

// ── Health ──────────────────────────────────────────────────────────────────

export async function isApiRunning() {
  try {
    const url = (import.meta.env.VITE_API_URL ?? '') + '/health'
    const res = await fetch(url, { signal: AbortSignal.timeout(2000) })
    return res.ok
  } catch {
    return false
  }
}

// ── Trip CRUD ────────────────────────────────────────────────────────────────

export async function listTrips() {
  const res = await apiFetch(`${BASE}/trips`)
  if (!res.ok) throw new Error('Failed to list trips')
  return res.json()
}

export async function loadTrip(tripId, signal) {
  const res = await apiFetch(`${BASE}/trips/${tripId}`, { signal })
  if (res.status === 404) return null
  if (!res.ok) throw new Error('Failed to load trip')
  return res.json()
}

export async function saveTrip(tripData) {
  const res = await apiFetch(`${BASE}/trips`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trip_data: tripData }),
  })
  if (!res.ok) {
    let message = 'Failed to save trip'
    try { const body = await res.json(); if (body.detail) message = body.detail } catch {}
    throw new Error(message)
  }
  const data = await res.json()
  return data.trip_id
}

export async function updateTrip(tripId, tripData) {
  const res = await apiFetch(`${BASE}/trips/${tripId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ trip_data: tripData }),
  })
  return res.ok
}

export async function patchTrip(tripId, updates) {
  const res = await apiFetch(`${BASE}/trips/${tripId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
  return res.ok
}

export async function deleteTrip(tripId) {
  const res = await apiFetch(`${BASE}/trips/${tripId}`, { method: 'DELETE' })
  return res.ok
}

// ── Chat (SSE stream) ────────────────────────────────────────────────────────

export async function chatStream({
  messages,
  tripData = null,
  companionMode = false,
  onText,
  onToolCall,
  onBookingData,
  signal,
}) {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ messages, trip_data: tripData, companion_mode: companionMode }),
    signal,
  })

  if (res.status === 401) {
    localStorage.removeItem('sta_auth_token')
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  if (!res.ok) {
    let message = `API error ${res.status}`
    try { const body = await res.json(); if (body.detail) message = body.detail } catch {}
    throw new Error(message)
  }

  const reader  = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()

    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const raw = line.slice(5).trim()
      if (raw === '[DONE]') return
      try {
        const evt = JSON.parse(raw)
        if (evt.text        !== undefined) onText?.(evt.text)
        if (evt.tool_call   !== undefined) onToolCall?.(evt.tool_call)
        if (evt.booking_data !== undefined) onBookingData?.(evt.booking_data)
      } catch { /* skip malformed */ }
    }
  }
}

// ── Weather ──────────────────────────────────────────────────────────────────

export async function fetchWeather(city, countryCode = '') {
  try {
    const params = new URLSearchParams({ city })
    if (countryCode) params.set('country_code', countryCode)
    const res = await apiFetch(`${BASE}/chat/weather?${params}`, {
      signal: AbortSignal.timeout(10_000),
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

// ── Post-trip debrief ────────────────────────────────────────────────────────

export async function saveDebrief(tripId, debriefText) {
  const res = await apiFetch(`${BASE}/trips/${tripId}/debrief`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ debrief_text: debriefText }),
  })
  if (!res.ok) throw new Error('Failed to save debrief')
  return res.json()
}

// ── Extraction ───────────────────────────────────────────────────────────────

export async function extractInfo(messages, currency = 'EUR', signal) {
  const res = await apiFetch(`${BASE}/chat/extract`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, currency }),
    signal,
  })
  if (!res.ok) return {}
  return res.json()
}
