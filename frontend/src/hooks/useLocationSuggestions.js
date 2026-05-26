import { useState, useEffect } from 'react'

/**
 * Fetches city suggestions from Photon (OpenStreetMap, by Komoot).
 * Free, no API key, CORS-enabled.
 *
 * - Debounces 300ms for real queries; clears instantly when < 2 chars
 * - Deduplicates by display label
 * - Fails silently — input still works if network is unavailable
 *
 * Each suggestion: { name, label, country, countryCode, state }
 */
export function useLocationSuggestions(query) {
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading]         = useState(false)

  useEffect(() => {
    const q = query.trim()
    let cancelled = false

    // All state updates live inside the setTimeout callback so none are
    // synchronous in the effect body (satisfies react-hooks/set-state-in-effect).
    // Use 0ms delay for instant clear when query is too short, 300ms otherwise.
    const timer = setTimeout(async () => {
      if (cancelled) return

      if (q.length < 2) {
        setSuggestions([])
        setLoading(false)
        return
      }

      setLoading(true)

      try {
        const url =
          `https://photon.komoot.io/api/?q=${encodeURIComponent(q)}&limit=6&layer=city`
        const res = await fetch(url, { signal: AbortSignal.timeout(5000) })

        if (cancelled) return
        if (!res.ok) throw new Error('Photon error')

        const data = await res.json()
        if (cancelled) return

        const seen  = new Set()
        const items = (data.features ?? [])
          .map(f => {
            const p = f.properties
            return {
              name:        p.name       ?? '',
              country:     p.country    ?? '',
              countryCode: (p.countrycode ?? '').toUpperCase(),
              state:       p.state      ?? '',
              label: [p.name, p.state, p.country].filter(Boolean).join(', '),
            }
          })
          .filter(r => {
            if (!r.name || seen.has(r.label)) return false
            seen.add(r.label)
            return true
          })

        setSuggestions(items)
      } catch {
        if (!cancelled) setSuggestions([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, q.length < 2 ? 0 : 300)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query])

  return { suggestions, loading }
}
