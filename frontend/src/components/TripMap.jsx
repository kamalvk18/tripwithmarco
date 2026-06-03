import { useMemo } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
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

export function TripMap({ days, destination, city }) {
  const centerQuery = city ? `${city}, ${destination}` : destination

  const geocodeItems = useMemo(() => {
    const items = [{ id: '__city__', query: centerQuery }]
    for (const day of days) {
      const places = extractPlaces(day.content || '')
      for (const place of places) {
        items.push({ id: `day${day.num}:${place}`, query: `${place}, ${destination}` })
      }
    }
    return items
  }, [days, destination, centerQuery])

  const { locations, loading } = useGeocode(geocodeItems)
  const cityLoc = locations['__city__']

  const markers = geocodeItems
    .filter(i => i.id !== '__city__' && locations[i.id])
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
      {!cityLoc && loading ? (
        <div className="flex items-center justify-center h-[360px] bg-[#12141e] gap-2 text-slate-500 text-sm">
          <Spinner className="w-4 h-4" /> Locating {centerQuery}…
        </div>
      ) : !cityLoc ? (
        <div className="flex items-center justify-center h-[360px] bg-[#12141e] gap-2 text-slate-500 text-sm">
          Map unavailable — location not found for "{centerQuery}"
        </div>
      ) : (
        <MapContainer
          center={[cityLoc.lat, cityLoc.lon]}
          zoom={10}
          style={{ height: 360 }}
          scrollWheelZoom={false}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          />
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
