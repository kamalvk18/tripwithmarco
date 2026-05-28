import { useEffect, useMemo, useState } from 'react'
import { loadTrip, updateTrip, deleteTrip, extractInfo } from '@/lib/api'
import { computeItinerary, extractAllDays, tripStatus } from '@/lib/utils'

/**
 * Module-level cache — survives route changes, cleared only on full page refresh.
 *
 * Key:   trip id string
 * Value: full trip object (kept in sync with every patch/write)
 *
 * This gives instant navigation to previously-visited trips without re-fetching,
 * while still showing a spinner on the first visit to a trip.
 */
const tripCache = new Map()

/**
 * useTrip — encapsulates everything about a single trip.
 *
 * Owns:
 *   - Data fetching, caching, and loading state
 *   - Derived state (messages, itinerary, days, status)
 *   - All persistence operations (patch, saveMessages, updateSpending, …)
 *
 * Components only deal with UI concerns; they never call the trip API directly.
 */
export function useTrip(id) {
  // Initialise synchronously from cache so the first render is already populated
  // on revisits — no stale-content flash, no spinner.
  const [tripData, setTripData] = useState(() => tripCache.get(id) ?? null)
  const [loading, setLoading]   = useState(() => !tripCache.has(id))

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller

    async function load() {
      let data = tripCache.get(id)

      if (data) {
        // Cache hit — serve from memory immediately, no network call
        setTripData(data)
        setLoading(false)
      } else {
        // Cache miss — first visit to this trip, fetch from backend
        setTripData(null)
        setLoading(true)
        data = await loadTrip(id, signal)
        if (!data) { setTripData(null); setLoading(false); return }
        tripCache.set(id, data)
        setTripData(data)
        setLoading(false)
      }

      // Background upgrade: extract budget breakdown if missing.
      // Runs after the trip is already displayed so there is no loading block.
      // The signal ensures the Haiku call is cancelled (not just ignored) if the
      // user navigates away before it completes.
      const missingBreakdown =
        !data.budget_breakdown || Object.keys(data.budget_breakdown).length === 0
      if (missingBreakdown && (data.messages ?? []).length > 0) {
        const extracted = await extractInfo(data.messages, data.currency ?? 'EUR', signal)
        const bd = extracted?.budget_breakdown
        if (bd && Object.values(bd).some(v => v != null)) {
          const upgraded = { ...data, budget_breakdown: bd }
          tripCache.set(id, upgraded)
          setTripData(upgraded)
          updateTrip(id, upgraded).catch(() => {})
        }
      }
    }

    load().catch(err => {
      if (err.name !== 'AbortError') {
        // Genuine load failure — clear the loading state so UI isn't stuck
        setTripData(null)
        setLoading(false)
      }
      // AbortError = user navigated away — no state update needed
    })

    return () => controller.abort()
  }, [id])

  // ── Derived state ──────────────────────────────────────────────────────────

  const messages  = useMemo(() => tripData?.messages ?? [], [tripData])
  const itinerary = useMemo(() => computeItinerary(messages), [messages])
  const days      = useMemo(() => extractAllDays(itinerary), [itinerary])
  const { status, label, dayNum } = useMemo(
    () => tripStatus(tripData ?? {}),
    [tripData]
  )

  // ── Persistence ────────────────────────────────────────────────────────────

  /** Apply partial updates, sync cache + local state, and persist to backend. */
  function patch(updates) {
    const next = { ...tripData, ...updates }
    tripCache.set(id, next)   // keep cache current so revisits stay fresh
    setTripData(next)
    return updateTrip(id, next).catch(() => {})
  }

  return {
    // State
    tripData,
    loading,
    // Derived
    messages,
    itinerary,
    days,
    status,
    label,
    dayNum,
    // Actions
    saveMessages:      msgs      => patch({ messages: msgs }),
    updateSpending:    spending  => patch({ spending }),
    updateChecklist:   checklist => patch({ checklist }),
    updateEmailConfig: cfg       => patch({ email_config: cfg }),
    updateDayOverride: (num, text) => patch({
      day_overrides: { ...(tripData?.day_overrides ?? {}), [String(num)]: text },
    }),
    updateDebrief:     debrief  => patch({ debrief }),
    updateNearMe:      text     => patch({ near_me_response: text }),
    // Read near_me_response directly from the module-level cache — always current,
    // never stale, regardless of React render timing or closure age.
    getCachedNearMeResponse: () => tripCache.get(id)?.near_me_response ?? '',
    remove: () => {
      tripCache.delete(id)    // evict so a re-visit would fetch fresh (won't happen — trip is gone)
      return deleteTrip(id)
    },
  }
}
