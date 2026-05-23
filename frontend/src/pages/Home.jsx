import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlusCircle, Trash2, Map } from 'lucide-react'
import { listTrips, deleteTrip } from '@/lib/api'
import { tripStatus } from '@/lib/utils'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'

const STATUS_ICON = { upcoming: '🗓️', active: '✈️', past: '✅', unknown: '📋' }

export default function Home() {
  const [trips, setTrips]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [deleting, setDeleting] = useState(null)
  const navigate = useNavigate()

  async function load() {
    setLoading(true)
    try { setTrips(await listTrips()) } catch { setTrips([]) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  async function handleDelete(e, tripId) {
    e.stopPropagation()
    if (!confirm('Delete this trip?')) return
    setDeleting(tripId)
    await deleteTrip(tripId)
    setDeleting(null)
    load()
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      {/* Hero */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-slate-100 mb-2">
          Hey, where to next?
        </h1>
        <p className="text-slate-400 text-base">
          Marco will plan your trip, find flights and hotels, and guide you every day.
        </p>
        <Button
          variant="primary"
          size="lg"
          className="mt-5"
          onClick={() => navigate('/plan')}
        >
          <PlusCircle size={18} /> Plan a New Trip
        </Button>
      </div>

      {/* Trip list */}
      {loading && (
        <p className="text-slate-500 text-sm">Loading trips…</p>
      )}

      {!loading && trips.length === 0 && (
        <div className="flex flex-col items-center gap-3 py-20 text-slate-500">
          <Map size={40} className="opacity-30" />
          <p className="text-sm">No trips yet. Plan your first one!</p>
        </div>
      )}

      <div className="grid gap-3">
        {trips.map(trip => {
          const { status, label } = tripStatus(trip)
          return (
            <Card
              key={trip.trip_id}
              className="cursor-pointer hover:border-indigo-700/50 hover:bg-[#1e2235] transition-colors group"
              onClick={() => navigate(`/trips/${trip.trip_id}`)}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">{STATUS_ICON[status]}</span>
                    <h2 className="text-base font-semibold text-slate-100 truncate">
                      {trip.destination}
                    </h2>
                  </div>
                  <p className="text-sm text-slate-400">{trip.dates}</p>
                  <div className="mt-2">
                    <Badge variant={status}>{label}</Badge>
                  </div>
                </div>
                <button
                  onClick={(e) => handleDelete(e, trip.trip_id)}
                  disabled={deleting === trip.trip_id}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-900/20 cursor-pointer"
                  title="Delete trip"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
