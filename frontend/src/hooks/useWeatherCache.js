import { useCallback } from 'react'
import { fetchWeather } from '@/lib/api'

/**
 * Module-level cache — survives component re-renders and route changes,
 * cleared only on full page refresh (which is exactly what we want).
 *
 * Key:   "city|countryCode"
 * Value: { weatherText: string, fetchedAt: number (ms timestamp) }
 */
const _cache = new Map()
const TTL_MS = 60 * 60 * 1000   // 1 hour — weather doesn't change message-to-message

/**
 * useWeatherCache — fetch weather once per city per hour, reuse the rest.
 *
 * Usage:
 *   const { getWeather } = useWeatherCache()
 *   const text = await getWeather('Munich', 'DE')   // cached after first call
 *
 * Returns null silently on network/API failures so callers can degrade gracefully
 * (backend will fall back to its own OpenWeather fetch in that case).
 */
export function useWeatherCache() {
  const getWeather = useCallback(async (city, countryCode = '') => {
    if (!city) return null

    const key = `${city}|${countryCode}`
    const now = Date.now()
    const cached = _cache.get(key)

    if (cached && (now - cached.fetchedAt) < TTL_MS) {
      return cached.weatherText   // cache hit — no network call
    }

    // Cache miss or stale — fetch from the backend weather endpoint
    const data = await fetchWeather(city, countryCode)
    const text = data?.weather_text ?? null

    if (text) {
      _cache.set(key, { weatherText: text, fetchedAt: now })
    }

    return text   // null if the fetch failed (backend will handle it)
  }, [])

  return { getWeather }
}
