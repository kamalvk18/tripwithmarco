import { useMemo, useState } from 'react'
import { PlusCircle, Trash2, TrendingUp, ChevronDown, Scale, CheckCircle2 } from 'lucide-react'
import { formatMoney } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { addExpense, deleteExpense, addSettlement, deleteSettlement } from '@/lib/api'

const CATEGORIES = ['flights', 'accommodation', 'food', 'activities', 'transport', 'misc']
const CAT_ICONS  = { flights: '✈️', accommodation: '🏨', food: '🍽️', activities: '🎟️', transport: '🚌', misc: '💼' }

// ── Balance computation ───────────────────────────────────────────────────────

function computeBalances(spending, settlements, members) {
  const net = {}
  members.forEach(m => { net[m.user_id] = 0 })

  for (const expense of spending) {
    const paidBy = expense.paid_by_user_id
    const splits = expense.splits ?? []
    if (!paidBy || splits.length === 0) continue
    for (const split of splits) {
      if (split.user_id !== paidBy) {
        net[paidBy] = (net[paidBy] ?? 0) + split.amount
        net[split.user_id] = (net[split.user_id] ?? 0) - split.amount
      }
    }
  }

  for (const s of (settlements ?? [])) {
    net[s.to_user_id]   = (net[s.to_user_id]   ?? 0) - s.amount
    net[s.from_user_id] = (net[s.from_user_id] ?? 0) + s.amount
  }

  const nameMap = Object.fromEntries(members.map(m => [m.user_id, m.name]))
  const creditors = Object.entries(net).filter(([, v]) => v > 0.005).map(([id, v]) => [+id, v]).sort((a, b) => b[1] - a[1])
  const debtors   = Object.entries(net).filter(([, v]) => v < -0.005).map(([id, v]) => [+id, -v]).sort((a, b) => b[1] - a[1])

  const balances = []
  let ci = 0, di = 0
  const creds = creditors.map(x => [...x])
  const debts = debtors.map(x => [...x])

  while (ci < creds.length && di < debts.length) {
    const [cuid, camt] = creds[ci]
    const [duid, damt] = debts[di]
    const transfer = Math.min(camt, damt)
    balances.push({
      from_user_id: duid,
      from_name: nameMap[duid] || 'Unknown',
      to_user_id: cuid,
      to_name: nameMap[cuid] || 'Unknown',
      amount: Math.round(transfer * 100) / 100,
    })
    creds[ci] = [cuid, camt - transfer]
    debts[di] = [duid, damt - transfer]
    if (creds[ci][1] < 0.005) ci++
    if (debts[di][1] < 0.005) di++
  }

  return balances
}

// ── Split helpers ─────────────────────────────────────────────────────────────

function buildEqualSplits(amount, memberSubset) {
  if (memberSubset.length === 0) return []
  const base = Math.floor((amount / memberSubset.length) * 100) / 100
  const remainder = Math.round((amount - base * memberSubset.length) * 100) / 100
  return memberSubset.map((m, i) => ({
    user_id: m.user_id,
    name: m.name,
    amount: i === 0 ? Math.round((base + remainder) * 100) / 100 : base,
  }))
}

// ── Sub-components ────────────────────────────────────────────────────────────

const inputCls = "rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-slate-100 px-3 py-2 text-sm placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-indigo-400 shadow-sm"

function BalancesTab({ balances, currentUserId, currency, tripId, settlements, onSettlementsUpdate }) {
  const [settlingId, setSettlingId] = useState(null)
  const [settleAmount, setSettleAmount] = useState('')
  const [settleNote, setSettleNote] = useState('')
  const [settling, setSettling] = useState(false)
  const [showHistory, setShowHistory] = useState(false)

  function openSettle(balance) {
    setSettlingId(`${balance.from_user_id}-${balance.to_user_id}`)
    setSettleAmount(String(balance.amount))
    setSettleNote('')
  }

  function cancelSettle() {
    setSettlingId(null)
    setSettleAmount('')
    setSettleNote('')
  }

  async function handleSettle(balance) {
    setSettling(true)
    try {
      const saved = await addSettlement(tripId, {
        to_user_id: balance.to_user_id,
        amount: parseFloat(settleAmount),
        note: settleNote,
      })
      onSettlementsUpdate?.([...(settlements ?? []), saved])
      cancelSettle()
    } finally {
      setSettling(false)
    }
  }

  async function handleDeleteSettlement(settlementId) {
    await deleteSettlement(tripId, settlementId)
    onSettlementsUpdate?.((settlements ?? []).filter(s => s.id !== settlementId))
  }

  const key = (b) => `${b.from_user_id}-${b.to_user_id}`

  if (balances.length === 0) {
    return (
      <div className="px-5 py-8 text-center">
        <Scale size={28} className="mx-auto text-slate-300 dark:text-slate-600 mb-2" />
        <p className="text-sm text-slate-400 dark:text-slate-500">All settled up!</p>
        <p className="text-xs text-slate-300 dark:text-slate-600 mt-1">Log shared expenses to see balances here.</p>
        {(settlements ?? []).length > 0 && (
          <button
            type="button"
            onClick={() => setShowHistory(h => !h)}
            className="mt-4 text-xs text-indigo-500 dark:text-indigo-400 hover:underline cursor-pointer"
          >
            {showHistory ? 'Hide' : 'Show'} settlement history ({settlements.length})
          </button>
        )}
        {showHistory && <SettlementHistory settlements={settlements} currentUserId={currentUserId} currency={currency} onDelete={handleDeleteSettlement} />}
      </div>
    )
  }

  return (
    <div className="px-5 py-4 space-y-3">
      {balances.map(b => {
        const isMe = b.from_user_id === currentUserId
        const owesMe = b.to_user_id === currentUserId
        const isActive = settlingId === key(b)

        return (
          <div key={key(b)} className="space-y-2">
            <div className={`flex items-center gap-3 p-3 rounded-lg border ${
              isMe    ? 'bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-700'
              : owesMe ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700'
              : 'bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700'
            }`}>
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                  {isMe ? 'You' : b.from_name}
                </span>
                <span className="text-sm text-slate-400 dark:text-slate-500 mx-1.5">owe{isMe ? '' : 's'}</span>
                <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                  {owesMe ? 'you' : b.to_name}
                </span>
                <span className={`ml-2 text-sm font-semibold ${
                  isMe ? 'text-orange-600 dark:text-orange-400'
                  : owesMe ? 'text-green-600 dark:text-green-400'
                  : 'text-slate-700 dark:text-slate-200'
                }`}>
                  {formatMoney(b.amount, currency)}
                </span>
              </div>
              {(isMe || owesMe) && !isActive && (
                <button
                  type="button"
                  onClick={() => openSettle(b)}
                  className="text-xs font-medium px-2.5 py-1 rounded-full bg-indigo-600 text-white hover:bg-indigo-700 transition-colors cursor-pointer shrink-0"
                >
                  Settle
                </button>
              )}
            </div>

            {isActive && (
              <div className="flex gap-2 flex-wrap pl-1">
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={settleAmount}
                  onChange={e => setSettleAmount(e.target.value)}
                  className={`${inputCls} w-28`}
                  placeholder="Amount"
                />
                <input
                  type="text"
                  value={settleNote}
                  onChange={e => setSettleNote(e.target.value)}
                  className={`${inputCls} flex-1 min-w-0`}
                  placeholder="Note (optional)"
                />
                <Button
                  type="button"
                  variant="primary"
                  size="sm"
                  disabled={settling || !settleAmount}
                  onClick={() => handleSettle(b)}
                  className="shrink-0"
                >
                  <CheckCircle2 size={13} />
                  {settling ? 'Saving…' : 'Record'}
                </Button>
                <button type="button" onClick={cancelSettle} className="text-xs text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer px-1">
                  Cancel
                </button>
              </div>
            )}
          </div>
        )
      })}

      {(settlements ?? []).length > 0 && (
        <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
          <button
            type="button"
            onClick={() => setShowHistory(h => !h)}
            className="text-xs text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 cursor-pointer"
          >
            {showHistory ? '▾' : '▸'} Settlement history ({settlements.length})
          </button>
          {showHistory && <SettlementHistory settlements={settlements} currentUserId={currentUserId} currency={currency} onDelete={handleDeleteSettlement} />}
        </div>
      )}
    </div>
  )
}

function SettlementHistory({ settlements, currentUserId, currency, onDelete }) {
  return (
    <div className="mt-2 space-y-1">
      {[...settlements].reverse().map(s => (
        <div key={s.id} className="flex items-center gap-2 py-1 group text-xs text-slate-500 dark:text-slate-400">
          <CheckCircle2 size={12} className="text-green-500 dark:text-green-400 shrink-0" />
          <span className="flex-1 min-w-0 truncate">
            <span className="font-medium">{s.from_user_id === currentUserId ? 'You' : s.from_name}</span>
            {' paid '}
            <span className="font-medium">{s.to_user_id === currentUserId ? 'you' : s.to_name}</span>
            {' · '}{formatMoney(s.amount, currency)}
            {s.note && <span className="text-slate-400 dark:text-slate-500"> · {s.note}</span>}
            {' · '}{s.date}
          </span>
          {(s.from_user_id === currentUserId) && (
            <button
              onClick={() => onDelete(s.id)}
              className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-400 hover:text-red-500 cursor-pointer"
            >
              <Trash2 size={11} />
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

/**
 * ExpenseTracker
 *
 * Props:
 *   tripId            — trip identifier
 *   spending          — full expenses array (all members)
 *   settlements       — recorded payments between members
 *   breakdown         — budget breakdown by category
 *   currency          — ISO currency code
 *   currentUserId     — the logged-in user's ID
 *   isOwner           — true if current user owns the trip
 *   members           — array of {user_id, name, picture} for all trip members
 *   onUpdate          — callback(newSpendingArray) called after add/delete expense
 *   onSettlementsUpdate — callback(newSettlementsArray) called after settle/delete
 */
export function ExpenseTracker({
  tripId,
  spending = [],
  settlements = [],
  breakdown = {},
  currency = 'EUR',
  currentUserId,
  isOwner = false,
  members = [],
  onUpdate,
  onSettlementsUpdate,
}) {
  const isGroupTrip = members.length > 1

  const [open, setOpen]     = useState(false)
  const [tab, setTab]       = useState('expenses')
  const [form, setForm]     = useState({ category: 'food', amount: '', description: '', date: '' })
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState(null)
  const [filter, setFilter] = useState('mine')

  const [paidByUserId, setPaidByUserId] = useState(currentUserId)
  const [splitMode, setSplitMode]       = useState('all')
  const [splitWith, setSplitWith]       = useState([])

  const mySpending    = spending.filter(e => e.added_by_user_id === currentUserId || !e.added_by_user_id)
  const hasOthers     = spending.some(e => e.added_by_user_id && e.added_by_user_id !== currentUserId)
  const viewSpending  = (hasOthers && filter === 'all') ? spending : mySpending

  function myShare(expense) {
    if (!expense.splits?.length) return expense.amount
    const split = expense.splits.find(s => s.user_id === currentUserId)
    return split ? split.amount : 0
  }

  const totalSpent     = viewSpending.reduce((s, e) => s + (filter === 'mine' ? myShare(e) : e.amount), 0)
  const myTotalSpent   = mySpending.reduce((s, e) => s + myShare(e), 0)
  const spentByCategory = viewSpending.reduce((acc, e) => {
    acc[e.category] = (acc[e.category] ?? 0) + (filter === 'mine' ? myShare(e) : e.amount)
    return acc
  }, {})
  const estimatedTotal = breakdown.total_estimated ?? 0

  const balances = useMemo(
    () => isGroupTrip ? computeBalances(spending, settlements, members) : [],
    [spending, settlements, members, isGroupTrip]
  )

  const myDebtCount = balances.filter(b => b.from_user_id === currentUserId).length

  function canDelete(expense) {
    if (isOwner) return true
    return !expense.added_by_user_id || expense.added_by_user_id === currentUserId
  }

  function toggleSplitWith(userId) {
    setSplitWith(prev =>
      prev.includes(userId) ? prev.filter(id => id !== userId) : [...prev, userId]
    )
  }

  async function handleAdd(evt) {
    evt.preventDefault()
    if (!form.amount || isNaN(parseFloat(form.amount))) return
    setAdding(true)
    setAddError(null)
    try {
      const amount = parseFloat(form.amount)
      let splits = []

      if (isGroupTrip && splitMode !== 'none') {
        const targetMembers = splitMode === 'all'
          ? members
          : members.filter(m => splitWith.includes(m.user_id))
        splits = buildEqualSplits(amount, targetMembers)
      }

      const saved = await addExpense(tripId, {
        category:         form.category,
        amount,
        description:      form.description,
        date:             form.date,
        paid_by_user_id:  isGroupTrip ? (paidByUserId || currentUserId) : undefined,
        splits,
      })
      onUpdate?.([...spending, saved])
      setForm({ category: 'food', amount: '', description: '', date: '' })
      if (splitMode === 'select') setSplitWith([])
    } catch {
      setAddError('Failed to log expense. Please try again.')
    } finally {
      setAdding(false)
    }
  }

  async function handleDelete(expenseId) {
    await deleteExpense(tripId, expenseId)
    onUpdate?.(spending.filter(e => e.id !== expenseId))
  }

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
      {/* Header */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 cursor-pointer text-left hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
      >
        <div className="flex items-center gap-3">
          <TrendingUp size={16} className="text-indigo-600" />
          <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">Expenses</span>
          <span className="text-xs text-slate-400 dark:text-slate-500">
            {formatMoney(myTotalSpent, currency)} my spend
            {estimatedTotal > 0 && ` / ${formatMoney(estimatedTotal, currency)} budget`}
          </span>
          {myDebtCount > 0 && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400">
              {myDebtCount} debt{myDebtCount > 1 ? 's' : ''}
            </span>
          )}
        </div>
        <ChevronDown size={15} className={`text-slate-400 dark:text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-slate-100 dark:border-slate-800">
          {/* Tabs — only in group trips */}
          {isGroupTrip && (
            <div className="flex gap-1 px-5 pt-3">
              {[['expenses', 'Expenses'], ['balances', 'Balances']].map(([t, label]) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTab(t)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors cursor-pointer ${
                    tab === t
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-600'
                  }`}
                >
                  {label}
                  {t === 'balances' && myDebtCount > 0 && (
                    <span className="ml-1.5 inline-flex items-center justify-center w-4 h-4 rounded-full bg-orange-500 text-white text-[10px] font-bold">
                      {myDebtCount}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}

          {/* ── Expenses tab ── */}
          {tab === 'expenses' && (
            <>
              {/* Filter toggle */}
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
                          : 'bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-600'
                      }`}
                    >
                      {f === 'mine' ? 'My expenses' : 'All members'}
                    </button>
                  ))}
                </div>
              )}

              {/* Category summary bars */}
              {CATEGORIES.filter(cat => breakdown[cat] || spentByCategory[cat]).length > 0 && (
                <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800 space-y-2.5">
                  {CATEGORIES.filter(cat => breakdown[cat] || spentByCategory[cat]).map(cat => {
                    const estimated  = breakdown[cat] ?? 0
                    const spent      = spentByCategory[cat] ?? 0
                    const max        = Math.max(estimated, spent, 1)
                    const overBudget = estimated > 0 && spent > estimated
                    return (
                      <div key={cat}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-slate-500 dark:text-slate-400">{CAT_ICONS[cat]} {cat}</span>
                          <span className={overBudget ? 'text-red-500 dark:text-red-400 font-medium' : 'text-slate-700 dark:text-slate-200'}>
                            {formatMoney(spent, currency)}
                            {estimated > 0 && <span className="text-slate-400 dark:text-slate-500 font-normal"> / {formatMoney(estimated, currency)}</span>}
                          </span>
                        </div>
                        <div className="relative h-2 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                          {estimated > 0 && (
                            <div className="absolute inset-y-0 left-0 rounded-full bg-slate-200 dark:bg-slate-600" style={{ width: `${(estimated / max) * 100}%` }} />
                          )}
                          <div
                            className={`absolute inset-y-0 left-0 rounded-full ${overBudget ? 'bg-red-500' : 'bg-indigo-500'}`}
                            style={{ width: `${(spent / max) * 100}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}

                  <div className="flex justify-between pt-2 border-t border-slate-100 dark:border-slate-800 text-sm font-semibold">
                    <span className="text-slate-600 dark:text-slate-300">{filter === 'all' ? 'Total (all members)' : 'My total'}</span>
                    <span className={estimatedTotal > 0 && totalSpent > estimatedTotal ? 'text-red-500 dark:text-red-400' : 'text-slate-800 dark:text-slate-100'}>
                      {formatMoney(totalSpent, currency)}
                      {estimatedTotal > 0 && (
                        <span className="text-slate-400 dark:text-slate-500 font-normal ml-1">/ {formatMoney(estimatedTotal, currency)}</span>
                      )}
                    </span>
                  </div>
                </div>
              )}

              {/* Expense list */}
              {viewSpending.length > 0 && (
                <div className="px-5 py-3 border-b border-slate-100 dark:border-slate-800 space-y-1 max-h-56 overflow-y-auto">
                  {[...viewSpending].reverse().map(exp => (
                    <div key={exp.id} className="flex items-center gap-3 py-1.5 group">
                      <span className="text-base">{CAT_ICONS[exp.category] ?? '💼'}</span>
                      <div className="flex-1 min-w-0">
                        <span className="text-sm text-slate-700 dark:text-slate-200 truncate block">{exp.description || exp.category}</span>
                        <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
                          <span>{exp.date}</span>
                          {exp.paid_by_name && exp.paid_by_user_id !== currentUserId && (
                            <span className="text-indigo-500 dark:text-indigo-400 font-medium">· paid by {exp.paid_by_name}</span>
                          )}
                          {exp.splits?.length > 1 && (
                            <span className="text-slate-300 dark:text-slate-600">· split {exp.splits.length} ways</span>
                          )}
                        </div>
                      </div>
                      <span className="text-sm font-medium text-slate-700 dark:text-slate-200 shrink-0">
                        {formatMoney(exp.amount, currency)}
                      </span>
                      {canDelete(exp) && (
                        <button
                          onClick={() => handleDelete(exp.id)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-400 hover:text-red-500 cursor-pointer p-0.5"
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
                <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Log an expense</p>
                <div className="grid grid-cols-2 gap-2">
                  <select
                    value={form.category}
                    onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                    className={inputCls}
                  >
                    {CATEGORIES.map(c => <option key={c} value={c}>{CAT_ICONS[c]} {c}</option>)}
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

                {/* Group-trip split controls */}
                {isGroupTrip && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-xs text-slate-400 dark:text-slate-500 mb-1 block">Paid by</label>
                        <select
                          value={paidByUserId ?? currentUserId}
                          onChange={e => setPaidByUserId(+e.target.value)}
                          className={inputCls + ' w-full'}
                        >
                          {members.map(m => (
                            <option key={m.user_id} value={m.user_id}>
                              {m.user_id === currentUserId ? `${m.name} (you)` : m.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="text-xs text-slate-400 dark:text-slate-500 mb-1 block">Split</label>
                        <select
                          value={splitMode}
                          onChange={e => { setSplitMode(e.target.value); setSplitWith([]) }}
                          className={inputCls + ' w-full'}
                        >
                          <option value="all">Equally — all members</option>
                          <option value="select">Equally — select who</option>
                          <option value="none">Don't split</option>
                        </select>
                      </div>
                    </div>

                    {splitMode === 'select' && (
                      <div className="flex flex-wrap gap-2">
                        {members.map(m => (
                          <label key={m.user_id} className="flex items-center gap-1.5 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={splitWith.includes(m.user_id)}
                              onChange={() => toggleSplitWith(m.user_id)}
                              className="rounded border-slate-300 dark:border-slate-600 text-indigo-600 focus:ring-indigo-400"
                            />
                            <span className="text-xs text-slate-600 dark:text-slate-300">
                              {m.user_id === currentUserId ? 'You' : m.name}
                            </span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {addError && (
                  <p className="text-xs text-red-500 dark:text-red-400">{addError}</p>
                )}
                <Button type="submit" variant="primary" size="sm" disabled={adding || !form.amount} className="self-start">
                  <PlusCircle size={14} /> {adding ? 'Adding…' : 'Log Expense'}
                </Button>
              </form>
            </>
          )}

          {/* ── Balances tab ── */}
          {tab === 'balances' && (
            <BalancesTab
              balances={balances}
              currentUserId={currentUserId}
              currency={currency}
              tripId={tripId}
              settlements={settlements}
              onSettlementsUpdate={onSettlementsUpdate}
            />
          )}
        </div>
      )}
    </div>
  )
}
