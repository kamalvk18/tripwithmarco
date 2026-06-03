import { useState } from 'react'
import { ClipboardList, RefreshCw, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { apiFetch } from '@/lib/api'

const CAT_ICONS  = { visa: '🛂', health: '💉', insurance: '🛡️', documents: '📄', kit: '🎒' }
const CAT_ORDER  = ['visa', 'health', 'insurance', 'documents', 'kit']
const PRIORITY_CLASS = { high: 'text-red-600', normal: 'text-slate-700', low: 'text-slate-500' }

async function apiGenerate(tripId, passportCountry) {
  const params = passportCountry ? `?passport_country=${encodeURIComponent(passportCountry)}` : ''
  const res = await apiFetch(`/api/trips/${tripId}/checklist${params}`, { method: 'POST' })
  if (!res.ok) {
    let detail = `Server error ${res.status}`
    try { detail = (await res.json()).detail ?? detail } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

async function apiToggle(tripId, itemId, completed) {
  const res = await apiFetch(
    `/api/trips/${tripId}/checklist/${itemId}?completed=${completed}`,
    { method: 'PATCH' },
  )
  return res.ok
}

export function ChecklistPanel({ tripId, destination, items = [], onUpdate }) {
  const [open, setOpen]             = useState(false)
  const [generating, setGenerating] = useState(false)
  const [passport, setPassport]     = useState('')
  const [showForm, setShowForm]     = useState(false)
  const [error, setError]           = useState(null)

  const done  = items.filter(i => i.completed).length
  const total = items.length

  async function handleGenerate(e) {
    e.preventDefault()
    setGenerating(true)
    setShowForm(false)
    setError(null)
    try {
      const res = await apiGenerate(tripId, passport)
      onUpdate?.(res.items)
    } catch (err) {
      console.error(err)
      setError(err.message ?? 'Something went wrong. Is the API server running?')
      setShowForm(true)
    } finally {
      setGenerating(false)
    }
  }

  async function handleToggle(itemId, current) {
    const newCompleted = !current
    await apiToggle(tripId, itemId, newCompleted)
    onUpdate?.(items.map(i => i.id === itemId ? { ...i, completed: newCompleted } : i))
  }

  const grouped = CAT_ORDER.reduce((acc, cat) => {
    const catItems = items.filter(i => i.category === cat)
    if (catItems.length) acc[cat] = catItems
    return acc
  }, {})

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 cursor-pointer text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <ClipboardList size={16} className="text-indigo-600" />
          <span className="text-sm font-semibold text-slate-700">Pre-Trip Checklist</span>
          {total > 0 && (
            <span className="text-xs text-slate-400">{done}/{total} done</span>
          )}
        </div>
        <ChevronDown size={15} className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-slate-100">
          {items.length === 0 && !generating && (
            <div className="px-5 py-5 text-center">
              {error && (
                <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-2.5 text-sm text-red-600 text-left">
                  ⚠️ {error}
                </div>
              )}
              <p className="text-sm text-slate-500 mb-4">
                Generate a personalised checklist: visa requirements, vaccinations,
                insurance, documents and kit — specific to {destination}.
              </p>
              {showForm ? (
                <form onSubmit={handleGenerate} className="flex gap-2 justify-center">
                  <input
                    type="text"
                    placeholder="Your passport country (e.g. UK)"
                    value={passport}
                    onChange={e => setPassport(e.target.value)}
                    className="rounded-lg bg-white border border-slate-200 text-slate-800 px-3 py-2
                      text-sm placeholder-slate-400 focus:outline-none focus:border-indigo-400 shadow-sm w-52"
                  />
                  <Button type="submit" variant="primary" size="sm">Generate</Button>
                </form>
              ) : (
                <Button variant="primary" size="sm" onClick={() => setShowForm(true)}>
                  <ClipboardList size={14} /> Generate Checklist
                </Button>
              )}
            </div>
          )}

          {generating && (
            <div className="flex items-center justify-center gap-2 py-8 text-sm text-indigo-600">
              <Spinner className="w-4 h-4" /> Marco is building your checklist…
            </div>
          )}

          {items.length > 0 && !generating && (
            <>
              {/* Progress bar */}
              <div className="px-5 pt-4 pb-2">
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-indigo-500 transition-all"
                    style={{ width: total > 0 ? `${(done / total) * 100}%` : '0%' }}
                  />
                </div>
                <p className="text-xs text-slate-400 mt-1 text-right">{done} of {total} complete</p>
              </div>

              <div className="px-5 pb-4 space-y-4">
                {Object.entries(grouped).map(([cat, catItems]) => (
                  <div key={cat}>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                      {CAT_ICONS[cat] ?? '📋'} {cat}
                    </p>
                    <div className="space-y-2">
                      {catItems.map(item => (
                        <label
                          key={item.id}
                          className="flex items-start gap-3 cursor-pointer group"
                        >
                          <input
                            type="checkbox"
                            checked={item.completed}
                            onChange={() => handleToggle(item.id, item.completed)}
                            className="mt-0.5 w-4 h-4 rounded accent-indigo-500 cursor-pointer"
                          />
                          <span className={`text-sm leading-snug select-none transition-colors
                            ${item.completed
                              ? 'line-through text-slate-300'
                              : PRIORITY_CLASS[item.priority] ?? 'text-slate-700'}`}
                          >
                            {item.priority === 'high' && !item.completed && (
                              <span className="text-red-500 mr-1">!</span>
                            )}
                            {item.item}
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {/* Regenerate */}
              <div className="px-5 pb-4">
                <button
                  type="button"
                  onClick={() => { setShowForm(true); setOpen(true) }}
                  className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 cursor-pointer transition-colors"
                >
                  <RefreshCw size={11} /> Regenerate with different passport
                </button>
                {showForm && (
                  <form onSubmit={handleGenerate} className="flex gap-2 mt-2">
                    <input
                      type="text"
                      placeholder="Passport country"
                      value={passport}
                      onChange={e => setPassport(e.target.value)}
                      className="rounded-lg bg-white border border-slate-200 text-slate-800 px-3 py-1.5
                        text-sm placeholder-slate-400 focus:outline-none focus:border-indigo-400 shadow-sm flex-1"
                    />
                    <Button type="submit" variant="primary" size="sm">Regenerate</Button>
                  </form>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
