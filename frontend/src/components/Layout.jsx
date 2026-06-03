import { useEffect, useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { PlusCircle, Map, Globe, ChevronRight, LogOut } from 'lucide-react'
import { listTrips } from '@/lib/api'
import { tripStatus } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import { Badge } from '@/components/ui/Badge'

export function Layout({ children }) {
  const [trips, setTrips]         = useState([])
  const [collapsed, setCollapsed] = useState(false)
  const { user, logout }          = useAuth()
  const navigate  = useNavigate()
  const location  = useLocation()

  // Reload sidebar trips whenever route changes
  useEffect(() => {
    listTrips()
      .then(setTrips)
      .catch(() => setTrips([]))
  }, [location.pathname])

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex w-full min-h-screen">
      {/* Sidebar */}
      <aside
        className={`flex flex-col shrink-0 bg-[#1a1d27] border-r border-[#2e3248] transition-all duration-200 ${collapsed ? 'w-14' : 'w-64'}`}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 py-4 border-b border-[#2e3248]">
          <Globe className="text-indigo-400 shrink-0" size={22} />
          {!collapsed && (
            <span className="text-slate-100 font-semibold tracking-tight truncate">
              Solo Travel
            </span>
          )}
          <button
            onClick={() => setCollapsed(c => !c)}
            className="ml-auto text-slate-500 hover:text-slate-300 cursor-pointer"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <ChevronRight size={16} className={`transition-transform ${collapsed ? '' : 'rotate-180'}`} />
          </button>
        </div>

        {/* New trip button */}
        <div className="px-3 py-3">
          <button
            onClick={() => navigate('/plan')}
            className={`flex items-center gap-2 w-full rounded-lg px-3 py-2 text-sm font-medium
              bg-indigo-600 hover:bg-indigo-500 text-white transition-colors cursor-pointer
              ${collapsed ? 'justify-center' : ''}`}
            title="Plan a new trip"
          >
            <PlusCircle size={16} />
            {!collapsed && 'Plan a Trip'}
          </button>
        </div>

        {/* Trip list */}
        {!collapsed && (
          <div className="flex-1 overflow-y-auto px-3 pb-4">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider px-1 mb-2">
              Saved Trips
            </p>
            {trips.length === 0 && (
              <p className="text-xs text-slate-600 px-1">No trips yet.</p>
            )}
            {trips.map(trip => {
              const { status, label } = tripStatus(trip)
              const isActive = location.pathname === `/trips/${trip.trip_id}`
              return (
                <Link
                  key={trip.trip_id}
                  to={`/trips/${trip.trip_id}`}
                  className={`flex flex-col gap-0.5 rounded-lg px-3 py-2 mb-1 text-sm transition-colors
                    ${isActive
                      ? 'bg-indigo-900/30 text-slate-100'
                      : 'text-slate-400 hover:bg-[#22263a] hover:text-slate-200'}`}
                >
                  <span className="font-medium truncate leading-tight">{trip.destination}</span>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Badge variant={status}>{label}</Badge>
                  </div>
                </Link>
              )
            })}
          </div>
        )}

        {/* Collapsed — show icons only */}
        {collapsed && (
          <div className="flex-1 overflow-y-auto flex flex-col items-center gap-1 py-2">
            {trips.map(trip => (
              <Link
                key={trip.trip_id}
                to={`/trips/${trip.trip_id}`}
                title={trip.destination}
                className="p-2 rounded-lg text-slate-500 hover:bg-[#22263a] hover:text-slate-200 transition-colors"
              >
                <Map size={16} />
              </Link>
            ))}
          </div>
        )}

        {/* User footer */}
        <div className={`border-t border-[#2e3248] px-3 py-3 ${collapsed ? 'flex justify-center' : ''}`}>
          {collapsed ? (
            <button
              onClick={handleLogout}
              title="Sign out"
              className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-900/20 transition-colors cursor-pointer"
            >
              <LogOut size={16} />
            </button>
          ) : (
            <div className="flex items-center gap-2.5">
              {user?.picture ? (
                <img
                  src={user.picture}
                  alt={user.name}
                  className="w-7 h-7 rounded-full shrink-0 ring-1 ring-[#2e3248]"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-indigo-700 shrink-0 flex items-center justify-center text-xs text-white font-semibold">
                  {user?.name?.[0]?.toUpperCase() ?? '?'}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-slate-200 truncate">{user?.name}</p>
                <p className="text-xs text-slate-500 truncate">{user?.email}</p>
              </div>
              <button
                onClick={handleLogout}
                title="Sign out"
                className="shrink-0 p-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-900/20 transition-colors cursor-pointer"
              >
                <LogOut size={14} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto min-w-0">
        {children}
      </main>
    </div>
  )
}
