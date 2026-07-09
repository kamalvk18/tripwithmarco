import { useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { useGeocode } from '@/hooks/useGeocode'
import { Spinner } from '@/components/ui/Spinner'

const DAY_COLORS = [
  '#6366f1', '#10b981', '#f59e0b', '#3b82f6', '#ec4899',
  '#8b5cf6', '#06b6d4', '#f97316', '#84cc16', '#14b8a6',
]

// Bold text in Marco's output that isn't a place name
const SKIP_RE = /^(morning|afternoon|evening|night|late|budget|note|tip|option|day\s|\d)/i

function extractPlaces(content) {
  return [...(content.matchAll(/\*\*([^*]{3,50})\*\*/g))]
    .map(m => m[1].trim())
    .filter(name => !SKIP_RE.test(name))
    .slice(0, 3)
}

// "Day 3 — Ghent: Canals & Beer Halls" → "Ghent" (multi-stop day-title convention)
function dayBaseCity(title) {
  return (title || '').match(/—\s*([^:—]{2,40}):/)?.[1]?.trim() || ''
}

/** Fit the viewport around the route once stop coordinates resolve. */
function FitBounds({ points }) {
  const map = useMap()
  const key = points.map(p => p.join(',')).join('|')
  useEffect(() => {
    if (points.length >= 2) map.fitBounds(points, { padding: [40, 40] })
  }, [map, key]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

export function TripMap({ days, destination, city, stops = [] }) {
  // Multi-stop trips label the destination as a route ("A → B → C") —
  // that's a name, not a geocodable place. Never put it in a query.
  const isRouteLabel = !!destination?.includes('→')
  const region = isRouteLabel ? '' : (destination || '')
  const stopCities = (stops || []).map(s => s.city).filter(Boolean)

  const centerQuery = region
    ? (city ? `${city}, ${region}` : region)
    : (city || stopCities[0] || (destination || '').split('→')[0].trim())

  const geocodeItems = useMemo(() => {
    const items = [{ id: '__city__', query: centerQuery }]
    stopCities.forEach((c, i) => items.push({ id: `stop${i}:${c}`, query: c }))
    for (const day of days) {
      const base = dayBaseCity(day.title) || region || city
      for (const place of extractPlaces(day.content || '')) {
        items.push({ id: `day${day.num}:${place}`, query: base ? `${place}, ${base}` : place })
      }
    }
    return items
  }, [days, destination, city, centerQuery, stopCities.join('|')]) // eslint-disable-line react-hooks/exhaustive-deps

  const { locations, loading } = useGeocode(geocodeItems)

  const stopMarkers = stopCities
    .map((name, i) => ({ name, order: i, loc: locations[`stop${i}:${name}`] }))
    .filter(s => s.loc)
  const routePoints = stopMarkers.map(s => [s.loc.lat, s.loc.lon])

  const mapCenter = locations['__city__'] || stopMarkers[0]?.loc

  const markers = geocodeItems
    .filter(i => i.id.startsWith('day') && locations[i.id])
    .map(item => {
      const [, dayNum, placeName] = item.id.match(/^day(\d+):(.+)$/)
      return { id: item.id, loc: locations[item.id], dayNum: +dayNum, placeName }
    })

  const uniqueDays = [...new Set(markers.map(m => m.dayNum))].sort((a, b) => a - b)

  return (
    <div className="rounded-xl border border-[#2e3248] overflow-hidden mb-6">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#1a1d27] border-b border-[#2e3248]">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Trip Map</p>
        {loading && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Spinner className="w-3 h-3" /> Locating places…
          </div>
        )}
      </div>

      {/* Map or loading state */}
      {!mapCenter && loading ? (
        <div className="flex items-center justify-center h-[360px] bg-[#12141e] gap-2 text-slate-500 text-sm">
          <Spinner className="w-4 h-4" /> Locating {centerQuery}…
        </div>
      ) : !mapCenter ? (
        <div className="flex items-center justify-center h-[360px] bg-[#12141e] gap-2 text-slate-500 text-sm">
          Map unavailable — location not found for "{centerQuery}"
        </div>
      ) : (
        <MapContainer
          center={[mapCenter.lat, mapCenter.lon]}
          zoom={stopMarkers.length >= 2 ? 7 : 10}
          style={{ height: 360 }}
          scrollWheelZoom={false}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          />
          <FitBounds points={routePoints} />

          {/* Route line + numbered stop markers (multi-stop trips) */}
          {routePoints.length >= 2 && (
            <Polyline positions={routePoints} pathOptions={{ color: '#6366f1', weight: 3, dashArray: '6 8', opacity: 0.8 }} />
          )}
          {stopMarkers.map(({ name, order, loc }) => (
            <CircleMarker
              key={`stop-${order}`}
              center={[loc.lat, loc.lon]}
              radius={12}
              pathOptions={{ fillColor: '#1a1d27', color: '#6366f1', weight: 3, fillOpacity: 1 }}
            >
              <Popup>
                <span className="font-semibold">Stop {order + 1}</span>
                <br />
                {name}
              </Popup>
            </CircleMarker>
          ))}

          {/* Per-day place markers */}
          {markers.map(({ id, loc, dayNum, placeName }) => (
            <CircleMarker
              key={id}
              center={[loc.lat, loc.lon]}
              radius={9}
              pathOptions={{
                fillColor: DAY_COLORS[(dayNum - 1) % DAY_COLORS.length],
                color: 'white',
                weight: 2,
                fillOpacity: 0.9,
              }}
            >
              <Popup>
                <span className="font-semibold">Day {dayNum}</span>
                <br />
                {placeName}
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      )}

      {/* Day legend */}
      {uniqueDays.length > 0 && (
        <div className="flex flex-wrap gap-3 px-4 py-3 bg-[#1a1d27] border-t border-[#2e3248]">
          {uniqueDays.map(dayNum => (
            <div key={dayNum} className="flex items-center gap-1.5 text-xs text-slate-400">
              <span
                className="w-2.5 h-2.5 rounded-full inline-block shrink-0"
                style={{ backgroundColor: DAY_COLORS[(dayNum - 1) % DAY_COLORS.length] }}
              />
              Day {dayNum}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
