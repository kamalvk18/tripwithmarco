import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlusCircle, Trash2, Map, ChevronRight, Globe } from 'lucide-react'
import { listTrips, deleteTrip } from '@/lib/api'
import { tripStatus } from '@/lib/utils'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'

const STATUS_ICON   = { upcoming: '🗓️', active: '✈️', past: '✅', unknown: '📋' }
const STATUS_BORDER = {
  upcoming: 'border-l-blue-400',
  active:   'border-l-emerald-500',
  past:     'border-l-slate-300',
  unknown:  'border-l-slate-300',
}

export default function Home() {
  const [trips, setTrips]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [deleting, setDeleting] = useState(null)
  const navigate = useNavigate()

  async function load() {
    try { setTrips(await listTrips()) } catch { setTrips([]) }
    setLoading(false)
  }

  useEffect(() => {
    listTrips()
      .then(setTrips)
      .catch(() => setTrips([]))
      .finally(() => setLoading(false))
  }, [])

  async function handleDelete(e, tripId) {
    e.stopPropagation()
    if (!confirm('Delete this trip?')) return
    setDeleting(tripId)
    await deleteTrip(tripId)
    setDeleting(null)
    load()
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
      {/* Hero */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-md">
            <Globe className="text-white" size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Hey, where to next?</h1>
            <p className="text-slate-500 text-sm">
              Marco will plan your trip, find flights and hotels, and guide you every day.
            </p>
          </div>
        </div>
        <Button
          variant="primary"
          size="lg"
          className="mt-2"
          onClick={() => navigate('/plan')}
        >
          <PlusCircle size={18} /> Plan a New Trip
        </Button>
      </div>

      {/* Trip list */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 rounded-xl bg-white border border-slate-200 shadow-sm animate-pulse" />
          ))}
        </div>
      )}

      {!loading && trips.length === 0 && (
        <div className="flex flex-col items-center gap-4 py-20 bg-white rounded-2xl border border-slate-200 shadow-sm text-center">
          <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center">
            <Map size={28} className="text-slate-400" />
          </div>
          <div>
            <p className="text-slate-700 font-medium">No trips yet</p>
            <p className="text-slate-400 text-sm mt-1">Plan your first adventure with Marco!</p>
          </div>
          <Button variant="primary" onClick={() => navigate('/plan')}>
            <PlusCircle size={16} /> Plan your first trip
          </Button>
        </div>
      )}

      <div className="grid gap-3">
        {trips.map(trip => {
          const { status, label } = tripStatus(trip)
          return (
            <div
              key={trip.trip_id}
              onClick={() => navigate(`/trips/${trip.trip_id}`)}
              className={cn(
                'group cursor-pointer rounded-xl border border-slate-200 border-l-4 bg-white',
                'shadow-sm hover:shadow-md transition-all duration-200',
                STATUS_BORDER[status] ?? STATUS_BORDER.unknown,
              )}
            >
              <div className="flex items-center gap-4 p-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xl">{STATUS_ICON[status]}</span>
                    <h2 className="text-base font-bold text-slate-800 truncate">
                      {trip.destination}
                    </h2>
                  </div>
                  <p className="text-sm text-slate-500 ml-8">{trip.dates}</p>
                  <div className="mt-2 ml-8">
                    <Badge variant={status}>{label}</Badge>
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={(e) => handleDelete(e, trip.trip_id)}
                    disabled={deleting === trip.trip_id}
                    className="opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity p-1.5 rounded-lg
                      text-slate-400 hover:text-red-500 hover:bg-red-50 cursor-pointer"
                    title="Delete trip"
                  >
                    <Trash2 size={15} />
                  </button>
                  <ChevronRight
                    size={18}
                    className="text-slate-300 group-hover:text-indigo-500 transition-colors"
                  />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
