import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Globe, Users, LogIn } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { getInvitePreview, joinTrip } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'

export default function JoinTrip() {
  const { token }   = useParams()
  const navigate    = useNavigate()
  const { user }    = useAuth()

  const [preview, setPreview]   = useState(null)
  const [loading, setLoading]   = useState(true)
  const [joining, setJoining]   = useState(false)
  const [error, setError]       = useState(null)

  useEffect(() => {
    getInvitePreview(token).then(data => {
      setPreview(data)
      setLoading(false)
    })
  }, [token])

  async function handleJoin() {
    setJoining(true)
    setError(null)
    try {
      const { trip_id } = await joinTrip(token)
      navigate(`/trips/${trip_id}`, { replace: true })
    } catch (err) {
      setError(err.message)
      setJoining(false)
    }
  }

  function handleLoginToJoin() {
    localStorage.setItem('sta_pending_join', `/join/${token}`)
    navigate('/login')
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <Spinner className="w-6 h-6 text-indigo-500" />
      </div>
    )
  }

  if (!preview) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 px-4">
        <div className="max-w-sm w-full bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-md p-8 text-center">
          <div className="w-14 h-14 rounded-2xl bg-red-100 dark:bg-red-900/20 flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">🔗</span>
          </div>
          <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100 mb-2">Link not found</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
            This invite link may have expired or been revoked by the trip owner.
          </p>
          <Button variant="primary" onClick={() => navigate('/')}>Go Home</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 px-4">
      <div className="max-w-sm w-full bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-md p-8">
        {/* Trip card */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-xl bg-indigo-600 flex items-center justify-center shadow-md shrink-0">
            <Globe className="text-white" size={22} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-50">{preview.destination}</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">{preview.dates}</p>
          </div>
        </div>

        {/* Owner info */}
        <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 mb-6">
          {preview.owner_picture ? (
            <img
              src={preview.owner_picture}
              alt={preview.owner_name}
              className="w-8 h-8 rounded-full object-cover"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-indigo-200 dark:bg-indigo-800 flex items-center justify-center text-indigo-700 dark:text-indigo-300 font-bold text-sm">
              {preview.owner_name?.[0]?.toUpperCase() ?? '?'}
            </div>
          )}
          <p className="text-sm text-slate-600 dark:text-slate-300">
            <span className="font-medium text-slate-800 dark:text-slate-100">{preview.owner_name}</span> invited you to join this trip
          </p>
        </div>

        {/* Budget note */}
        <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg px-3 py-2 mb-6">
          <Users size={13} className="text-amber-600 dark:text-amber-400 shrink-0" />
          <span>Budget is per person — you'll track your own expenses separately.</span>
        </div>

        {error && (
          <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg px-3 py-2 mb-4">
            {error}
          </div>
        )}

        {user ? (
          <Button
            variant="primary"
            className="w-full justify-center"
            onClick={handleJoin}
            disabled={joining}
          >
            {joining ? <><Spinner className="w-4 h-4" /> Joining…</> : <><Users size={16} /> Join Trip</>}
          </Button>
        ) : (
          <>
            <p className="text-xs text-slate-500 dark:text-slate-400 text-center mb-3">
              Sign in with Google to join this trip.
            </p>
            <Button
              variant="primary"
              className="w-full justify-center"
              onClick={handleLoginToJoin}
            >
              <LogIn size={16} /> Sign in to Join
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
