import { useState, useEffect } from 'react'

/**
 * Fetches city suggestions from Photon (OpenStreetMap, by Komoot).
 * Free, no API key, CORS-enabled.
 *
 * - Debounces 300ms to avoid hammering the API
 * - Requires at least 2 characters
 * - Deduplicates by display label
 * - Fails silently — the input still works if the network is unavailable
 *
 * Each suggestion: { name, label, country, countryCode, state }
 */
export function useLocationSuggestions(query) {
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading]         = useState(false)

  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) {
      setSuggestions([])
      setLoading(false)
      return
    }

    setLoading(true)

    const timer = setTimeout(async () => {
      try {
        const url = `https://photon.komoot.io/api/?q=${encodeURIComponent(q)}&limit=6&layer=city`
        const res = await fetch(url, { signal: AbortSignal.timeout(5000) })
        if (!res.ok) throw new Error('Photon error')

        const data = await res.json()
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
        setSuggestions([])
      } finally {
        setLoading(false)
      }
    }, 300)

    return () => {
      clearTimeout(timer)
      setLoading(false)
    }
  }, [query])

  return { suggestions, loading }
}
