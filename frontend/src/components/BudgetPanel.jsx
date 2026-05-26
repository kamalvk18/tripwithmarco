import { formatMoney } from '@/lib/utils'

const CATEGORY_ICONS = {
  flights:       '✈️',
  accommodation: '🏨',
  food:          '🍽️',
  activities:    '🎟️',
  transport:     '🚌',
  misc:          '💼',
}

export function BudgetPanel({ breakdown, userBudget, currency }) {
  const hasBreakdown = breakdown && Object.keys(breakdown).length > 0

  // Nothing to show at all
  if (!hasBreakdown && !(userBudget > 0)) return null

  // ── Minimal view — breakdown extraction still pending ────────────────────
  if (!hasBreakdown) {
    return (
      <div className="rounded-xl border border-[#2e3248] bg-[#1a1d27] p-5">
        <h3 className="text-sm font-semibold text-slate-200 mb-3">💰 Budget</h3>
        <div className="flex justify-between items-center">
          <span className="text-sm text-slate-400">Your budget</span>
          <span className="text-base font-bold text-slate-100">{formatMoney(userBudget, currency)}</span>
        </div>
      </div>
    )
  }

  // ── Full breakdown view ────────────────────────────────────────────────────
  const total = breakdown.total_estimated ?? 0
  const overage = userBudget ? total - userBudget : 0
  const categories = Object.entries(breakdown).filter(([k]) => k !== 'total_estimated')

  return (
    <div className="rounded-xl border border-[#2e3248] bg-[#1a1d27] p-5">
      <h3 className="text-sm font-semibold text-slate-200 mb-4">💰 Budget Estimate</h3>

      <div className="space-y-2">
        {categories.map(([key, val]) => {
          const icon  = CATEGORY_ICONS[key] ?? '💼'
          const pct   = total > 0 ? Math.round((val / total) * 100) : 0
          return (
            <div key={key}>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>{icon} {key.charAt(0).toUpperCase() + key.slice(1)}</span>
                <span className="text-slate-300">{formatMoney(val, currency)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-[#22263a] overflow-hidden">
                <div
                  className="h-full rounded-full bg-indigo-500/70"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-4 pt-3 border-t border-[#2e3248] flex justify-between items-center">
        <span className="text-sm text-slate-400">Total estimate</span>
        <span className="text-base font-bold text-slate-100">{formatMoney(total, currency)}</span>
      </div>

      {userBudget > 0 && (
        <div className="mt-2 flex justify-between items-center">
          <span className="text-sm text-slate-400">Your budget</span>
          <span className="text-sm text-slate-300">{formatMoney(userBudget, currency)}</span>
        </div>
      )}

      {overage > 0 && (
        <div className="mt-3 rounded-lg bg-red-900/20 border border-red-800/40 px-3 py-2 text-xs text-red-400">
          ⚠️ Marco's estimate is {formatMoney(overage, currency)} over your budget.
          Ask Marco to find cheaper options.
        </div>
      )}
    </div>
  )
}
