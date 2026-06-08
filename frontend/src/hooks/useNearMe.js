import { useState } from 'react'

/**
 * Returns the user's current location as a human-readable area string,
 * using the browser Geolocation API + Nominatim reverse geocoding (free, no key).
 *
 * Usage:
 *   const { locate, locating, error } = useNearMe()
 *   const loc = await locate()   // { lat, lon, area, city, display }
 */
export function useNearMe() {
  const [locating, setLocating] = useState(false)
  const [error, setError]       = useState(null)

  async function locate() {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser')
      return null
    }
    setLocating(true)
    setError(null)

    try {
      const pos = await new Promise((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          timeout: 10_000,
          maximumAge: 60_000,
          enableHighAccuracy: false,
        })
      )
      const { latitude: lat, longitude: lon } = pos.coords

      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json&zoom=14`,
        { headers: { 'User-Agent': 'Marco/1.0 (marco)' } }
      )
      const data = await res.json()
      const a    = data.address ?? {}

      const area = a.quarter ?? a.neighbourhood ?? a.suburb ?? a.city_district ?? ''
      const city = a.city ?? a.town ?? a.village ?? a.county ?? ''
      const display = [area, city].filter(Boolean).join(', ') || 'your current location'

      return { lat, lon, area, city, display }
    } catch (e) {
      const msg =
        e.code === 1 ? 'Location access denied — please allow location in your browser'
        : e.code === 2 ? 'Location unavailable'
        : 'Could not get your location'
      setError(msg)
      return null
    } finally {
      setLocating(false)
    }
  }

  return { locate, locating, error }
}
