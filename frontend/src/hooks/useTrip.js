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

/** Call this after updating a trip from outside useTrip (e.g. PlanTrip save) so the
 *  next TripView visit fetches fresh data instead of serving the stale cache. */
export function invalidateTripCache(id) {
  tripCache.delete(id)
}

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

      // Background upgrade: on a fresh server fetch (not a session cache hit),
      // always re-extract to pick up any budget/itinerary changes made in chat.
      // On cache hits (SPA navigation) only run if data is actually missing.
      const missingBreakdown =
        !data.budget_breakdown || Object.keys(data.budget_breakdown).length === 0
      const missingDays = !data.days?.length
      const shouldExtract = missingBreakdown || missingDays
      if (shouldExtract && (data.messages ?? []).length > 0) {
        const extracted = await extractInfo(data.messages, data.currency ?? 'EUR', signal)
        const bd = extracted?.budget_breakdown
        const extractedDays = extracted?.days
        const newBudget = extracted?.budget
        const hasBd     = bd && Object.values(bd).some(v => v != null)
        const hasDays   = extractedDays?.length > 0
        const hasBudget = newBudget != null && newBudget > 0
        if (hasBd || hasDays || hasBudget) {
          // Read from cache — not from `data` — so that user changes made while
          // extractInfo was running (e.g. adding an expense) are not clobbered.
          const current = tripCache.get(id) ?? data
          const upgraded = {
            ...current,
            ...(hasBd     ? { budget_breakdown: bd }      : {}),
            ...(hasDays   ? { days: extractedDays }        : {}),
            ...(hasBudget ? { budget: newBudget }          : {}),
          }
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
  // Prefer structured days stored at save time; fall back to regex parsing for old trips.
  // Normalize `day` field from backend schema to `num` expected by DayCard.
  const days      = useMemo(() => {
    if (tripData?.days?.length > 0) {
      return tripData.days.map(d => ({
        num:     d.num  ?? d.day,
        title:   d.title,
        content: d.content,
      }))
    }
    return extractAllDays(itinerary)
  }, [tripData?.days, itinerary])
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
    updateMembers: newMembers => {
      const next = { ...tripData, members: newMembers }
      tripCache.set(id, next)
      setTripData(next)
    },
    saveMessages: msgs => {
      const newItinerary = computeItinerary(msgs)
      const newDays = extractAllDays(newItinerary)
      const updates = { messages: msgs }
      if (newDays.length > 0) updates.days = newDays

      // Background: re-extract budget breakdown from updated itinerary
      extractInfo(msgs, tripData?.currency ?? 'EUR')
        .then(extracted => {
          const bd = extracted?.budget_breakdown
          if (bd && Object.values(bd).some(v => v != null)) patch({ budget_breakdown: bd })
        })
        .catch(() => {})

      return patch(updates)
    },
    // Expense/settlement endpoints already persist to DB — only sync local state here.
    updateSpending: spending => {
      const next = { ...tripData, spending }
      tripCache.set(id, next)
      setTripData(next)
    },
    updateSettlements: settlements => {
      const next = { ...tripData, settlements }
      tripCache.set(id, next)
      setTripData(next)
    },
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
