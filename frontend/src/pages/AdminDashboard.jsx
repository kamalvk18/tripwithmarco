import { useEffect, useState } from 'react'
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import { Users, Map, Activity, AlertTriangle, Zap, Brain, ChevronUp, ChevronDown } from 'lucide-react'
import { fetchAdminStats } from '@/lib/api'

function timeAgo(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins  < 1)   return 'just now'
  if (mins  < 60)  return `${mins}m ago`
  if (hours < 24)  return `${hours}h ago`
  if (days  < 30)  return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

function UsersTable({ users }) {
  const [sortCol, setSortCol] = useState('created_at')
  const [sortDir, setSortDir] = useState('desc')

  function toggleSort(col) {
    if (sortCol === col) setSortDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSortCol(col); setSortDir('desc') }
  }

  const sorted = [...users].sort((a, b) => {
    const av = a[sortCol] || ''
    const bv = b[sortCol] || ''
    return sortDir === 'desc' ? bv.localeCompare(av) : av.localeCompare(bv)
  })

  function SortIcon({ col }) {
    if (sortCol !== col) return <ChevronDown size={12} className="opacity-30" />
    return sortDir === 'desc'
      ? <ChevronDown size={12} className="text-indigo-500" />
      : <ChevronUp   size={12} className="text-indigo-500" />
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-3">Users</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wide border-b border-slate-100">
              <th className="pb-2 pr-4">Name</th>
              <th className="pb-2 pr-4">Email</th>
              <th className="pb-2 pr-6">
                <button onClick={() => toggleSort('created_at')} className="flex items-center gap-1 hover:text-slate-600 transition-colors">
                  Joined <SortIcon col="created_at" />
                </button>
              </th>
              <th className="pb-2">
                <button onClick={() => toggleSort('last_active_at')} className="flex items-center gap-1 hover:text-slate-600 transition-colors">
                  Last Active <SortIcon col="last_active_at" />
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(u => (
              <tr key={u.id} className="border-b border-slate-50 last:border-0 hover:bg-slate-50 transition-colors">
                <td className="py-2 pr-4 font-medium text-slate-700">{u.name || '—'}</td>
                <td className="py-2 pr-4 text-slate-500">{u.email}</td>
                <td className="py-2 pr-6 text-slate-400 text-xs whitespace-nowrap">
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                </td>
                <td className="py-2 text-slate-400 text-xs whitespace-nowrap">{timeAgo(u.last_active_at)}</td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={4} className="py-4 text-center text-slate-400 text-xs">No users yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Stat card ────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, sub, accent = 'indigo' }) {
  const colors = {
    indigo: 'bg-indigo-50 text-indigo-600',
    green:  'bg-green-50  text-green-600',
    amber:  'bg-amber-50  text-amber-600',
    red:    'bg-red-50    text-red-600',
  }
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-start gap-4 shadow-sm">
      <div className={`rounded-lg p-2.5 shrink-0 ${colors[accent]}`}>
        <Icon size={20} />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-slate-800 mt-0.5 leading-none">{value ?? '—'}</p>
        {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
      </div>
    </div>
  )
}

// ── Section heading ──────────────────────────────────────────────────────────

function SectionTitle({ children }) {
  return <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-3">{children}</h2>
}

// ── Chart colours ────────────────────────────────────────────────────────────

const INDIGO = '#6366f1'
const RED    = '#ef4444'
const DEST_COLORS = [
  '#6366f1','#8b5cf6','#a78bfa','#c4b5fd',
  '#818cf8','#7c3aed','#4f46e5','#4338ca','#3730a3','#312e81',
]

// ── Tooltip formatter ────────────────────────────────────────────────────────

function shortDate(d) { return d ? d.slice(5) : '' }

// ── Main page ────────────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const [stats,   setStats]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    fetchAdminStats()
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full py-32 text-slate-400 text-sm">
        Loading analytics…
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full py-32">
        <div className="text-center">
          <AlertTriangle className="mx-auto text-red-400 mb-3" size={32} />
          <p className="text-slate-700 font-medium">{error}</p>
          <p className="text-slate-400 text-sm mt-1">Make sure your email is in the ADMIN_EMAILS env var.</p>
        </div>
      </div>
    )
  }

  const { users, trips, usage, tools, claude } = stats

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">

      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-slate-800">Admin Dashboard</h1>
        <p className="text-sm text-slate-400 mt-0.5">Platform-wide usage and activity</p>
      </div>

      {/* ── Stat cards ────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Users}
          label="Total Users"
          value={users.total}
          sub={`+${users.new_this_week} this week · +${users.new_this_month} this month`}
          accent="indigo"
        />
        <StatCard
          icon={Map}
          label="Total Trips"
          value={trips.total}
          sub={`+${trips.created_this_week} this week${trips.avg_budget ? ` · avg $${trips.avg_budget.toLocaleString()}` : ''}`}
          accent="green"
        />
        <StatCard
          icon={Activity}
          label="API Calls Today"
          value={usage.requests_today.toLocaleString()}
          sub={`${usage.requests_this_week.toLocaleString()} this week`}
          accent="amber"
        />
        <StatCard
          icon={AlertTriangle}
          label="Error Rate Today"
          value={`${usage.error_rate_today}%`}
          sub={usage.avg_latency_ms != null ? `avg ${usage.avg_latency_ms} ms latency` : undefined}
          accent={usage.error_rate_today > 5 ? 'red' : 'indigo'}
        />
      </div>

      {/* ── Daily requests chart ───────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <SectionTitle>Daily API Requests — last 14 days</SectionTitle>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={usage.daily_requests} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11, fill: '#94a3b8' }} />
            <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
            <Tooltip
              contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
              labelFormatter={shortDate}
            />
            <Line type="monotone" dataKey="requests" stroke={INDIGO} strokeWidth={2} dot={false} name="Requests" />
            <Line type="monotone" dataKey="errors"   stroke={RED}    strokeWidth={1.5} dot={false} name="Errors" strokeDasharray="4 2" />
          </LineChart>
        </ResponsiveContainer>
        <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
          <span className="flex items-center gap-1.5"><span className="inline-block w-4 h-0.5 bg-indigo-500 rounded" /> Requests</span>
          <span className="flex items-center gap-1.5"><span className="inline-block w-4 h-0.5 bg-red-400 rounded border-dashed" /> Errors</span>
        </div>
      </div>

      {/* ── Bottom row: destinations + endpoints ──────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Top destinations */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <SectionTitle>Top Destinations</SectionTitle>
          {trips.top_destinations.length === 0 ? (
            <p className="text-sm text-slate-400">No trip data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={trips.top_destinations}
                layout="vertical"
                margin={{ top: 0, right: 8, left: 8, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                <YAxis type="category" dataKey="destination" width={110} tick={{ fontSize: 11, fill: '#475569' }} />
                <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }} />
                <Bar dataKey="count" name="Trips" radius={[0, 4, 4, 0]}>
                  {trips.top_destinations.map((_, i) => (
                    <Cell key={i} fill={DEST_COLORS[i % DEST_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Top endpoints */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <SectionTitle>Top Endpoints — last 7 days</SectionTitle>
          {usage.top_endpoints.length === 0 ? (
            <p className="text-sm text-slate-400">No usage data yet.</p>
          ) : (
            <div className="space-y-2">
              {usage.top_endpoints.map((ep, i) => {
                const max = usage.top_endpoints[0].count
                const pct = Math.round((ep.count / max) * 100)
                return (
                  <div key={i}>
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-xs font-mono text-slate-600 truncate max-w-[260px]">{ep.endpoint}</span>
                      <span className="text-xs font-semibold text-slate-700 ml-2 shrink-0">{ep.count.toLocaleString()}</span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 rounded-full transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── External APIs ─────────────────────────────────────────────────── */}
      <div>
        <SectionTitle>External APIs — this month</SectionTitle>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* SerpApi burn rate */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <div className="rounded-lg p-2 bg-amber-50 text-amber-600 shrink-0"><Zap size={16} /></div>
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">SerpApi usage</p>
                <p className="text-2xl font-bold text-slate-800 leading-none">
                  {tools.serpapi_calls_this_month}
                  <span className="text-sm font-normal text-slate-400"> / {tools.serpapi_monthly_cap}</span>
                </p>
              </div>
            </div>
            {/* Progress bar */}
            {(() => {
              const pct = Math.min(100, Math.round(tools.serpapi_calls_this_month / tools.serpapi_monthly_cap * 100))
              const color = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-400' : 'bg-green-500'
              return (
                <div>
                  <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden mb-1">
                    <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
                  </div>
                  <p className="text-xs text-slate-400">{pct}% of free-tier monthly cap used</p>
                </div>
              )
            })()}

            {/* Per-tool breakdown */}
            {tools.breakdown.length > 0 && (
              <div className="mt-4 space-y-2">
                {tools.breakdown.map((t) => (
                  <div key={t.tool} className="flex items-center justify-between text-xs">
                    <span className="font-mono text-slate-600 truncate">{t.tool}</span>
                    <div className="flex items-center gap-3 shrink-0 ml-2">
                      <span className="text-slate-400">{t.total} calls</span>
                      <span className="text-green-600 font-medium">{t.hit_rate}% cached</span>
                      {t.errors > 0 && <span className="text-red-500">{t.errors} err</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {tools.breakdown.length === 0 && (
              <p className="text-xs text-slate-400 mt-4">No tool calls recorded yet.</p>
            )}
          </div>

          {/* Anthropic token usage */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <div className="rounded-lg p-2 bg-indigo-50 text-indigo-600 shrink-0"><Brain size={16} /></div>
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Anthropic tokens</p>
                <p className="text-2xl font-bold text-slate-800 leading-none">
                  {claude.models.reduce((s, m) => s + m.input_tokens + m.output_tokens, 0).toLocaleString()}
                  <span className="text-sm font-normal text-slate-400"> total</span>
                </p>
              </div>
            </div>
            {claude.models.length === 0 ? (
              <p className="text-xs text-slate-400">No Claude calls recorded yet.</p>
            ) : (
              <div className="space-y-3 mt-2">
                {claude.models.map((m) => {
                  const shortModel = m.model.includes('haiku') ? 'Haiku' : m.model.includes('sonnet') ? 'Sonnet' : m.model.includes('opus') ? 'Opus' : m.model
                  const cacheHitPct = m.input_tokens > 0
                    ? Math.round(m.cache_read_tokens / (m.input_tokens + m.cache_read_tokens) * 100)
                    : 0
                  return (
                    <div key={m.model} className="rounded-lg bg-slate-50 p-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-semibold text-slate-700">{shortModel}</span>
                        <span className="text-xs text-slate-400">{m.calls.toLocaleString()} calls</span>
                      </div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-slate-500">
                        <span>Input: <b className="text-slate-700">{m.input_tokens.toLocaleString()}</b></span>
                        <span>Output: <b className="text-slate-700">{m.output_tokens.toLocaleString()}</b></span>
                        <span>Cache read: <b className="text-green-600">{m.cache_read_tokens.toLocaleString()}</b></span>
                        <span>Cache hit: <b className="text-green-600">{cacheHitPct}%</b></span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Claude daily tokens chart ──────────────────────────────────────── */}
      {claude.daily_tokens.some(d => d.tokens > 0) && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <SectionTitle>Anthropic tokens per day — last 14 days</SectionTitle>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={claude.daily_tokens} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11, fill: '#94a3b8' }} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v} />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
                labelFormatter={shortDate}
                formatter={v => [v.toLocaleString(), 'Tokens']}
              />
              <Bar dataKey="tokens" name="Tokens" fill={INDIGO} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Recent users table ─────────────────────────────────────────────── */}
      <UsersTable users={users.recent} />

    </div>
  )
}
