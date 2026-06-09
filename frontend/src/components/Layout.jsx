import { useEffect, useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { PlusCircle, Map, Globe, ChevronRight, LogOut, Menu, X, BarChart2, Moon, Sun } from 'lucide-react'
import { listTrips } from '@/lib/api'
import { tripStatus } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import { useTheme } from '@/contexts/ThemeContext'
import { Badge } from '@/components/ui/Badge'

function SidebarContent({ trips, location, user, collapsed, isMobile, onLogout, onNavigate, onCollapse, onClose, dark, toggleDark }) {
  const isExpanded = isMobile || !collapsed

  return (
    <>
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-4 border-b border-slate-100 dark:border-slate-800">
        <Globe className="text-indigo-600 shrink-0" size={22} />
        {isExpanded && (
          <span className="text-slate-800 dark:text-slate-100 font-bold tracking-tight truncate">Marco</span>
        )}
        {isMobile ? (
          <button
            onClick={onClose}
            className="ml-auto text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer transition-colors p-1"
          >
            <X size={18} />
          </button>
        ) : (
          <button
            onClick={onCollapse}
            className="ml-auto text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer transition-colors"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <ChevronRight size={16} className={`transition-transform ${collapsed ? '' : 'rotate-180'}`} />
          </button>
        )}
      </div>

      {/* User profile */}
      <div className={`border-b border-slate-100 dark:border-slate-800 px-3 py-2.5 ${!isExpanded ? 'flex justify-center' : ''}`}>
        {!isExpanded ? (
          <button
            onClick={onLogout}
            title="Sign out"
            className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer"
          >
            <LogOut size={16} />
          </button>
        ) : (
          <div className="flex items-center gap-2.5">
            {user?.picture ? (
              <img
                src={user.picture}
                alt={user.name}
                className="w-7 h-7 rounded-full shrink-0 ring-2 ring-slate-200 dark:ring-slate-700"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-indigo-600 shrink-0 flex items-center justify-center text-xs text-white font-semibold">
                {user?.name?.[0]?.toUpperCase() ?? '?'}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">{user?.name}</p>
              <p className="text-xs text-slate-400 dark:text-slate-500 truncate">{user?.email}</p>
            </div>
            <button
              onClick={onLogout}
              title="Sign out"
              className="shrink-0 p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer"
            >
              <LogOut size={14} />
            </button>
          </div>
        )}
      </div>

      {/* New trip button */}
      <div className="px-3 py-3">
        <button
          onClick={() => onNavigate('/plan')}
          className={`flex items-center gap-2 w-full rounded-lg px-3 py-2 text-sm font-medium
            bg-indigo-600 hover:bg-indigo-500 text-white transition-colors cursor-pointer shadow-sm
            ${!isExpanded ? 'justify-center' : ''}`}
          title="Plan a new trip"
        >
          <PlusCircle size={16} />
          {isExpanded && 'Plan a Trip'}
        </button>
      </div>

      {/* Admin link (admin users only) */}
      {user?.is_admin && (
        <div className="px-3 pb-1">
          <Link
            to="/admin"
            className={`flex items-center gap-2 w-full rounded-lg px-3 py-2 text-sm font-medium transition-colors
              ${!isExpanded ? 'justify-center' : ''}
              ${location.pathname === '/admin'
                ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300'
                : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-800 dark:hover:text-slate-100'}`}
            title="Admin dashboard"
          >
            <BarChart2 size={16} />
            {isExpanded && 'Admin'}
          </Link>
        </div>
      )}

      {/* Trip list */}
      {isExpanded ? (
        <div className="flex-1 overflow-y-auto px-3 pb-4">
          <p className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider px-1 mb-2">
            Saved Trips
          </p>
          {trips.length === 0 && (
            <p className="text-xs text-slate-400 dark:text-slate-500 px-1">No trips yet.</p>
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
                    ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300'
                    : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 hover:text-slate-800 dark:hover:text-slate-100'}`}
              >
                <span className="font-medium truncate leading-tight">{trip.destination}</span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Badge variant={status}>{label}</Badge>
                </div>
              </Link>
            )
          })}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto flex flex-col items-center gap-1 py-2">
          {trips.map(trip => (
            <Link
              key={trip.trip_id}
              to={`/trips/${trip.trip_id}`}
              title={trip.destination}
              className="p-2 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-300 transition-colors"
            >
              <Map size={16} />
            </Link>
          ))}
        </div>
      )}

      {/* Dark mode toggle */}
      <div className={`border-t border-slate-100 dark:border-slate-800 px-3 py-3 ${!isExpanded ? 'flex justify-center' : ''}`}>
        <button
          onClick={toggleDark}
          title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium
            text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800
            hover:text-slate-700 dark:hover:text-slate-200 transition-colors cursor-pointer
            ${!isExpanded ? 'justify-center w-full' : 'w-full'}`}
        >
          {dark ? <Sun size={15} /> : <Moon size={15} />}
          {isExpanded && (dark ? 'Light mode' : 'Dark mode')}
        </button>
      </div>
    </>
  )
}

export function Layout({ children }) {
  const [trips, setTrips]           = useState([])
  const [collapsed, setCollapsed]   = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { user, logout }            = useAuth()
  const { dark, toggleDark }        = useTheme()
  const navigate  = useNavigate()
  const location  = useLocation()

  useEffect(() => {
    listTrips()
      .then(setTrips)
      .catch(() => setTrips([]))
  }, [location.pathname])

  // Close mobile drawer on route change
  useEffect(() => { setMobileOpen(false) }, [location.pathname])

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  const sharedProps = {
    trips,
    location,
    user,
    dark,
    toggleDark,
    onLogout: handleLogout,
    onNavigate: navigate,
    onCollapse: () => setCollapsed(c => !c),
    onClose: () => setMobileOpen(false),
  }

  return (
    <div className="flex w-full min-h-screen bg-slate-100 dark:bg-slate-950">
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-20 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Mobile slide-in drawer */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 w-72 flex flex-col bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800
          transition-transform duration-200 md:hidden
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <SidebarContent {...sharedProps} isMobile collapsed={false} />
      </aside>

      {/* Desktop sidebar */}
      <aside
        className={`hidden md:flex flex-col shrink-0 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800
          transition-all duration-200 ${collapsed ? 'w-14' : 'w-64'}`}
      >
        <SidebarContent {...sharedProps} isMobile={false} collapsed={collapsed} />
      </aside>

      {/* Mobile top bar */}
      <header className="md:hidden fixed top-0 left-0 right-0 z-10 h-14 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center gap-3 px-4">
        <button
          onClick={() => setMobileOpen(true)}
          className="text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 p-1 cursor-pointer"
          title="Open menu"
        >
          <Menu size={22} />
        </button>
        <Globe className="text-indigo-600" size={20} />
        <span className="font-bold text-slate-800 dark:text-slate-100 text-sm tracking-tight">Marco</span>
        <button
          onClick={() => navigate('/plan')}
          className="ml-auto flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer"
        >
          <PlusCircle size={14} /> Plan Trip
        </button>
      </header>

      {/* Main — offset top on mobile for fixed header */}
      <main className="flex-1 overflow-y-auto min-w-0 pt-14 md:pt-0">
        {children}
      </main>
    </div>
  )
}
