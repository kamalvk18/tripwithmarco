import { useState, useEffect, useRef } from 'react'

// Module-level cache so results survive re-mounts and map open/close toggles
const cache = new Map()

async function geocodeOne(query) {
  if (cache.has(query)) return cache.get(query)
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1`,
      {
        headers: { 'Accept-Language': 'en', 'User-Agent': 'Marco/1.0' },
        signal: AbortSignal.timeout(6000),
      }
    )
    const data = await res.json()
    const result = data[0] ? { lat: +data[0].lat, lon: +data[0].lon } : null
    cache.set(query, result)
    return result
  } catch {
    cache.set(query, null)
    return null
  }
}

// Geocodes an array of {id, query} items sequentially, respecting Nominatim's
// 1 req/sec rate limit. Cached results skip the delay. Returns locations map
// keyed by id, plus a loading flag.
export function useGeocode(items) {
  const [locations, setLocations] = useState({})
  const [loading, setLoading] = useState(!!items?.length)
  const runRef = useRef(null)

  useEffect(() => {
    if (!items?.length) {
      setLoading(false)
      return
    }
    const key = items.map(i => i.id).join('|')

    // Same key = same places, current run is still valid — don't restart or cancel it
    if (runRef.current?.key === key) return

    // New key = supersede the previous run (it checks runRef.current itself)
    const run = { key }
    runRef.current = run
    setLocations({})
    setLoading(true)

    ;(async () => {
      for (let i = 0; i < items.length; i++) {
        if (runRef.current !== run) break
        const { id, query } = items[i]
        if (i > 0 && !cache.has(query)) {
          await new Promise(r => setTimeout(r, 1200))
        }
        if (runRef.current !== run) break
        const result = await geocodeOne(query)
        if (runRef.current !== run) break
        if (result) {
          setLocations(prev => ({ ...prev, [id]: result }))
        } else if (id === '__city__') {
          break  // city not found — skip individual places
        }
      }
      if (runRef.current === run) setLoading(false)
    })()
  }, [items])

  return { locations, loading }
}
