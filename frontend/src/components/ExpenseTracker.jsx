import { useState } from 'react'
import { PlusCircle, Trash2, TrendingUp } from 'lucide-react'
import { formatMoney } from '@/lib/utils'
import { Button } from '@/components/ui/Button'

const CATEGORIES = ['flights', 'accommodation', 'food', 'activities', 'transport', 'misc']
const CAT_ICONS  = { flights: '✈️', accommodation: '🏨', food: '🍽️', activities: '🎟️', transport: '🚌', misc: '💼' }

async function apiAddExpense(tripId, expense) {
  const res = await fetch(`/api/trips/${tripId}/expenses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(expense),
  })
  if (!res.ok) throw new Error('Failed to add expense')
  return res.json()
}

async function apiDeleteExpense(tripId, expenseId) {
  const res = await fetch(`/api/trips/${tripId}/expenses/${expenseId}`, { method: 'DELETE' })
  return res.ok
}

/**
 * Props:
 *   tripId        — trip identifier
 *   spending      — current list of expense objects from trip JSON
 *   breakdown     — Marco's budget_breakdown estimates {category: amount, ...}
 *   currency      — e.g. 'EUR'
 *   onUpdate      — (newSpending) => void — called after add/delete
 */
export function ExpenseTracker({ tripId, spending = [], breakdown = {}, currency = 'EUR', onUpdate }) {
  const [open, setOpen]     = useState(false)
  const [form, setForm]     = useState({ category: 'food', amount: '', description: '', date: '' })
  const [adding, setAdding] = useState(false)

  // ── Totals ────────────────────────────────────────────────────────────────

  const totalSpent = spending.reduce((s, e) => s + e.amount, 0)

  const spentByCategory = spending.reduce((acc, e) => {
    acc[e.category] = (acc[e.category] ?? 0) + e.amount
    return acc
  }, {})

  // ── Handlers ──────────────────────────────────────────────────────────────

  async function handleAdd(evt) {
    evt.preventDefault()
    if (!form.amount || isNaN(parseFloat(form.amount))) return
    setAdding(true)
    try {
      const saved = await apiAddExpense(tripId, {
        category:    form.category,
        amount:      parseFloat(form.amount),
        description: form.description,
        date:        form.date,
      })
      onUpdate?.([...spending, saved])
      setForm({ category: 'food', amount: '', description: '', date: '' })
    } finally {
      setAdding(false)
    }
  }

  async function handleDelete(expenseId) {
    await apiDeleteExpense(tripId, expenseId)
    onUpdate?.(spending.filter(e => e.id !== expenseId))
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const estimatedTotal = breakdown.total_estimated ?? 0

  return (
    <div className="rounded-xl border border-[#2e3248] bg-[#1a1d27] overflow-hidden">
      {/* Header */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 cursor-pointer text-left"
      >
        <div className="flex items-center gap-3">
          <TrendingUp size={16} className="text-indigo-400" />
          <span className="text-sm font-semibold text-slate-200">Expense Tracker</span>
          <span className="text-xs text-slate-500">
            {formatMoney(totalSpent, currency)} spent
            {estimatedTotal > 0 && ` of ${formatMoney(estimatedTotal, currency)} estimated`}
          </span>
        </div>
        <span className="text-slate-500 text-xs">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="border-t border-[#2e3248]">
          {/* Category summary bars */}
          {CATEGORIES.filter(cat => breakdown[cat] || spentByCategory[cat]).length > 0 && (
            <div className="px-5 py-4 border-b border-[#2e3248] space-y-2.5">
              {CATEGORIES.filter(cat => breakdown[cat] || spentByCategory[cat]).map(cat => {
                const estimated = breakdown[cat] ?? 0
                const spent     = spentByCategory[cat] ?? 0
                const max       = Math.max(estimated, spent, 1)
                const overBudget = estimated > 0 && spent > estimated
                return (
                  <div key={cat}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400">{CAT_ICONS[cat]} {cat}</span>
                      <span className={overBudget ? 'text-red-400' : 'text-slate-300'}>
                        {formatMoney(spent, currency)}
                        {estimated > 0 && ` / ${formatMoney(estimated, currency)}`}
                      </span>
                    </div>
                    {/* Two stacked bars: estimate (background) + actual (foreground) */}
                    <div className="relative h-1.5 rounded-full bg-[#22263a] overflow-hidden">
                      {estimated > 0 && (
                        <div
                          className="absolute inset-y-0 left-0 rounded-full bg-slate-600/40"
                          style={{ width: `${(estimated / max) * 100}%` }}
                        />
                      )}
                      <div
                        className={`absolute inset-y-0 left-0 rounded-full ${overBudget ? 'bg-red-500' : 'bg-indigo-500'}`}
                        style={{ width: `${(spent / max) * 100}%` }}
                      />
                    </div>
                  </div>
                )
              })}

              {/* Total row */}
              <div className="flex justify-between pt-2 border-t border-[#2e3248] text-sm font-semibold">
                <span className="text-slate-300">Total spent</span>
                <span className={estimatedTotal > 0 && totalSpent > estimatedTotal ? 'text-red-400' : 'text-slate-100'}>
                  {formatMoney(totalSpent, currency)}
                  {estimatedTotal > 0 && (
                    <span className="text-slate-500 font-normal ml-1">
                      / {formatMoney(estimatedTotal, currency)}
                    </span>
                  )}
                </span>
              </div>
            </div>
          )}

          {/* Expense list */}
          {spending.length > 0 && (
            <div className="px-5 py-3 border-b border-[#2e3248] space-y-1 max-h-52 overflow-y-auto">
              {[...spending].reverse().map(exp => (
                <div key={exp.id} className="flex items-center gap-3 py-1.5 group">
                  <span className="text-base">{CAT_ICONS[exp.category] ?? '💼'}</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-slate-200 truncate block">{exp.description || exp.category}</span>
                    <span className="text-xs text-slate-500">{exp.date}</span>
                  </div>
                  <span className="text-sm font-medium text-slate-200 shrink-0">
                    {formatMoney(exp.amount, currency)}
                  </span>
                  <button
                    onClick={() => handleDelete(exp.id)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-500
                      hover:text-red-400 cursor-pointer p-0.5"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Add expense form */}
          <form onSubmit={handleAdd} className="px-5 py-4 flex flex-col gap-3">
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Log an expense</p>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={form.category}
                onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                className="rounded-lg bg-[#22263a] border border-[#2e3248] text-slate-200 px-3 py-2 text-sm
                  focus:outline-none focus:border-indigo-500"
              >
                {CATEGORIES.map(c => (
                  <option key={c} value={c}>{CAT_ICONS[c]} {c}</option>
                ))}
              </select>
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="Amount"
                value={form.amount}
                onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
                required
                className="rounded-lg bg-[#22263a] border border-[#2e3248] text-slate-200 px-3 py-2 text-sm
                  placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Description (optional)"
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                className="rounded-lg bg-[#22263a] border border-[#2e3248] text-slate-200 px-3 py-2 text-sm
                  placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <input
                type="date"
                value={form.date}
                onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
                className="rounded-lg bg-[#22263a] border border-[#2e3248] text-slate-200 px-3 py-2 text-sm
                  focus:outline-none focus:border-indigo-500"
              />
            </div>
            <Button type="submit" variant="secondary" size="sm" disabled={adding || !form.amount} className="self-start">
              <PlusCircle size={14} /> {adding ? 'Adding…' : 'Log Expense'}
            </Button>
          </form>
        </div>
      )}
    </div>
  )
}
