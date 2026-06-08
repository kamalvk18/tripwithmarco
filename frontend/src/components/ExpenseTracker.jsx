import { useState } from 'react'
import { PlusCircle, Trash2, TrendingUp, ChevronDown } from 'lucide-react'
import { formatMoney } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { apiFetch } from '@/lib/api'

const CATEGORIES = ['flights', 'accommodation', 'food', 'activities', 'transport', 'misc']
const CAT_ICONS  = { flights: '✈️', accommodation: '🏨', food: '🍽️', activities: '🎟️', transport: '🚌', misc: '💼' }

async function apiAddExpense(tripId, expense) {
  const res = await apiFetch(`/api/trips/${tripId}/expenses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(expense),
  })
  if (!res.ok) throw new Error('Failed to add expense')
  return res.json()
}

async function apiDeleteExpense(tripId, expenseId) {
  const res = await apiFetch(`/api/trips/${tripId}/expenses/${expenseId}`, { method: 'DELETE' })
  return res.ok
}

/**
 * ExpenseTracker
 *
 * Props:
 *   tripId      — trip identifier
 *   spending    — full expenses array (all members)
 *   breakdown   — budget breakdown by category
 *   currency    — ISO currency code
 *   currentUserId — the logged-in user's ID (to determine delete permissions)
 *   isOwner     — true if current user owns the trip (can delete anyone's expenses)
 *   onUpdate    — callback(newSpendingArray) called after add/delete
 */
export function ExpenseTracker({
  tripId,
  spending = [],
  breakdown = {},
  currency = 'EUR',
  currentUserId,
  isOwner = false,
  onUpdate,
}) {
  const [open, setOpen]     = useState(false)
  const [form, setForm]     = useState({ category: 'food', amount: '', description: '', date: '' })
  const [adding, setAdding] = useState(false)
  // Filter: 'mine' | 'all'
  const [filter, setFilter] = useState('mine')

  // My expenses vs all expenses
  const mySpending  = spending.filter(e => e.added_by_user_id === currentUserId || !e.added_by_user_id)
  const hasOthers   = spending.some(e => e.added_by_user_id && e.added_by_user_id !== currentUserId)
  const viewSpending = (hasOthers && filter === 'all') ? spending : mySpending

  const totalSpent = viewSpending.reduce((s, e) => s + e.amount, 0)
  const myTotalSpent = mySpending.reduce((s, e) => s + e.amount, 0)
  const spentByCategory = viewSpending.reduce((acc, e) => {
    acc[e.category] = (acc[e.category] ?? 0) + e.amount
    return acc
  }, {})
  const estimatedTotal = breakdown.total_estimated ?? 0

  function canDelete(expense) {
    if (isOwner) return true
    return !expense.added_by_user_id || expense.added_by_user_id === currentUserId
  }

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

  const inputCls = "rounded-lg bg-white border border-slate-200 text-slate-800 px-3 py-2 text-sm placeholder-slate-400 focus:outline-none focus:border-indigo-400 shadow-sm"

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 cursor-pointer text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <TrendingUp size={16} className="text-indigo-600" />
          <span className="text-sm font-semibold text-slate-700">Expense Tracker</span>
          <span className="text-xs text-slate-400">
            {formatMoney(myTotalSpent, currency)} my spend
            {estimatedTotal > 0 && ` / ${formatMoney(estimatedTotal, currency)} budget`}
          </span>
        </div>
        <ChevronDown size={15} className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-slate-100">
          {/* Filter toggle — only shown in group trips */}
          {hasOthers && (
            <div className="flex gap-1 px-5 pt-3">
              {['mine', 'all'].map(f => (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors cursor-pointer ${
                    filter === f
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                  }`}
                >
                  {f === 'mine' ? 'My expenses' : 'All members'}
                </button>
              ))}
            </div>
          )}

          {/* Category summary bars */}
          {CATEGORIES.filter(cat => breakdown[cat] || spentByCategory[cat]).length > 0 && (
            <div className="px-5 py-4 border-b border-slate-100 space-y-2.5">
              {CATEGORIES.filter(cat => breakdown[cat] || spentByCategory[cat]).map(cat => {
                const estimated = breakdown[cat] ?? 0
                const spent     = spentByCategory[cat] ?? 0
                const max       = Math.max(estimated, spent, 1)
                const overBudget = estimated > 0 && spent > estimated
                return (
                  <div key={cat}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-500">{CAT_ICONS[cat]} {cat}</span>
                      <span className={overBudget ? 'text-red-500 font-medium' : 'text-slate-700'}>
                        {formatMoney(spent, currency)}
                        {estimated > 0 && <span className="text-slate-400 font-normal"> / {formatMoney(estimated, currency)}</span>}
                      </span>
                    </div>
                    <div className="relative h-2 rounded-full bg-slate-100 overflow-hidden">
                      {estimated > 0 && (
                        <div
                          className="absolute inset-y-0 left-0 rounded-full bg-slate-200"
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

              <div className="flex justify-between pt-2 border-t border-slate-100 text-sm font-semibold">
                <span className="text-slate-600">
                  {filter === 'all' ? 'Total (all members)' : 'My total'}
                </span>
                <span className={estimatedTotal > 0 && totalSpent > estimatedTotal ? 'text-red-500' : 'text-slate-800'}>
                  {formatMoney(totalSpent, currency)}
                  {estimatedTotal > 0 && (
                    <span className="text-slate-400 font-normal ml-1">
                      / {formatMoney(estimatedTotal, currency)}
                    </span>
                  )}
                </span>
              </div>
            </div>
          )}

          {/* Expense list */}
          {viewSpending.length > 0 && (
            <div className="px-5 py-3 border-b border-slate-100 space-y-1 max-h-56 overflow-y-auto">
              {[...viewSpending].reverse().map(exp => (
                <div key={exp.id} className="flex items-center gap-3 py-1.5 group">
                  <span className="text-base">{CAT_ICONS[exp.category] ?? '💼'}</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-slate-700 truncate block">{exp.description || exp.category}</span>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <span>{exp.date}</span>
                      {exp.added_by_name && exp.added_by_user_id !== currentUserId && (
                        <span className="text-indigo-500 font-medium">· {exp.added_by_name}</span>
                      )}
                    </div>
                  </div>
                  <span className="text-sm font-medium text-slate-700 shrink-0">
                    {formatMoney(exp.amount, currency)}
                  </span>
                  {canDelete(exp) && (
                    <button
                      onClick={() => handleDelete(exp.id)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-400
                        hover:text-red-500 cursor-pointer p-0.5"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Add expense form */}
          <form onSubmit={handleAdd} className="px-5 py-4 flex flex-col gap-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Log an expense</p>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={form.category}
                onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                className={inputCls}
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
                className={inputCls}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="Description (optional)"
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                className={inputCls}
              />
              <input
                type="date"
                value={form.date}
                onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
                className={inputCls}
              />
            </div>
            <Button type="submit" variant="primary" size="sm" disabled={adding || !form.amount} className="self-start">
              <PlusCircle size={14} /> {adding ? 'Adding…' : 'Log Expense'}
            </Button>
          </form>
        </div>
      )}
    </div>
  )
}
