import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlusCircle, Trash2, Map, ChevronRight, Globe, Users } from 'lucide-react'
import { listTrips, deleteTrip } from '@/lib/api'
import { tripStatus } from '@/lib/utils'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'

const STATUS_ICON   = { upcoming: '🗓️', active: '✈️', past: '✅', unknown: '📋' }
const STATUS_BORDER = {
  upcoming: 'border-l-blue-400',
  active:   'border-l-emerald-500',
  past:     'border-l-slate-300 dark:border-l-slate-600',
  unknown:  'border-l-slate-300 dark:border-l-slate-600',
}

function TripCard({ trip, onDelete, deleting }) {
  const navigate = useNavigate()
  const { status, label } = tripStatus(trip)
  return (
    <div
      onClick={() => navigate(`/trips/${trip.trip_id}`)}
      className={cn(
        'group cursor-pointer rounded-xl border border-slate-200 dark:border-slate-700 border-l-4 bg-white dark:bg-slate-900',
        'shadow-sm hover:shadow-md transition-all duration-200',
        STATUS_BORDER[status] ?? STATUS_BORDER.unknown,
      )}
    >
      <div className="flex items-center gap-4 p-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">{STATUS_ICON[status]}</span>
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 truncate">
              {trip.destination}
            </h2>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 ml-8">{trip.dates}</p>
          <div className="mt-2 ml-8 flex items-center gap-2 flex-wrap">
            <Badge variant={status}>{label}</Badge>
            {trip.is_member && trip.owner_name && (
              <span className="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1">
                <Users size={11} /> {trip.owner_name}'s trip
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {!trip.is_member && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(trip.trip_id) }}
              disabled={deleting === trip.trip_id}
              className="opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity p-1.5 rounded-lg
                text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 cursor-pointer"
              title="Delete trip"
            >
              <Trash2 size={15} />
            </button>
          )}
          <ChevronRight
            size={18}
            className="text-slate-300 dark:text-slate-600 group-hover:text-indigo-500 transition-colors"
          />
        </div>
      </div>
    </div>
  )
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

  async function handleDelete(tripId) {
    if (!confirm('Delete this trip?')) return
    setDeleting(tripId)
    await deleteTrip(tripId)
    setDeleting(null)
    load()
  }

  const myTrips     = trips.filter(t => !t.is_member)
  const sharedTrips = trips.filter(t => t.is_member)

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
      {/* Hero */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-md">
            <Globe className="text-white" size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">Hey, where to next?</h1>
            <p className="text-slate-500 dark:text-slate-400 text-sm">
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

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-24 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-sm animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && trips.length === 0 && (
        <div className="flex flex-col items-center gap-4 py-20 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm text-center">
          <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
            <Map size={28} className="text-slate-400 dark:text-slate-500" />
          </div>
          <div>
            <p className="text-slate-700 dark:text-slate-200 font-medium">No trips yet</p>
            <p className="text-slate-400 dark:text-slate-500 text-sm mt-1">Plan your first adventure with Marco!</p>
          </div>
          <Button variant="primary" onClick={() => navigate('/plan')}>
            <PlusCircle size={16} /> Plan your first trip
          </Button>
        </div>
      )}

      {/* My trips */}
      {!loading && myTrips.length > 0 && (
        <div className="mb-8">
          {sharedTrips.length > 0 && (
            <h2 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
              My Trips
            </h2>
          )}
          <div className="grid gap-3">
            {myTrips.map(trip => (
              <TripCard
                key={trip.trip_id}
                trip={trip}
                onDelete={handleDelete}
                deleting={deleting}
              />
            ))}
          </div>
        </div>
      )}

      {/* Shared trips */}
      {!loading && sharedTrips.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
            <Users size={13} /> Shared With Me
          </h2>
          <div className="grid gap-3">
            {sharedTrips.map(trip => (
              <TripCard
                key={trip.trip_id}
                trip={trip}
                onDelete={handleDelete}
                deleting={deleting}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
