import { formatMoney } from '@/lib/utils'

const CATEGORY_ICONS = {
  travel:        '🚆',
  flights:       '✈️',  // legacy key from old trips
  accommodation: '🏨',
  food:          '🍽️',
  activities:    '🎟️',
  transport:     '🚌',
  misc:          '💼',
}

const CATEGORY_LABELS = {
  travel:        'Travel',
  flights:       'Flights',
  accommodation: 'Accommodation',
  food:          'Food',
  activities:    'Activities',
  transport:     'Local transport',
  misc:          'Misc',
}

export function BudgetPanel({ breakdown, userBudget, currency }) {
  const hasBreakdown = breakdown && Object.keys(breakdown).length > 0

  if (!hasBreakdown && !(userBudget > 0)) return null

  if (!hasBreakdown) {
    return (
      <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">💰 Budget</h3>
        <div className="flex justify-between items-center">
          <span className="text-sm text-slate-500 dark:text-slate-400">Your budget</span>
          <span className="text-base font-bold text-slate-800 dark:text-slate-100">{formatMoney(userBudget, currency)}</span>
        </div>
      </div>
    )
  }

  const total = breakdown.total_estimated ?? 0
  const overage = userBudget ? total - userBudget : 0
  const categories = Object.entries(breakdown).filter(([k]) => k !== 'total_estimated')

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm p-5">
      <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">💰 Budget Estimate</h3>

      <div className="space-y-3">
        {categories.map(([key, val]) => {
          const icon = CATEGORY_ICONS[key] ?? '💼'
          const pct  = total > 0 ? Math.round((val / total) * 100) : 0
          return (
            <div key={key}>
              <div className="flex justify-between text-xs mb-1.5">
                <span className="text-slate-500 dark:text-slate-400">{icon} {CATEGORY_LABELS[key] ?? key.charAt(0).toUpperCase() + key.slice(1)}</span>
                <span className="text-slate-700 dark:text-slate-200 font-medium">{formatMoney(val, currency)}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
                <div
                  className="h-full rounded-full bg-indigo-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center">
        <span className="text-sm text-slate-500 dark:text-slate-400">Total estimate</span>
        <span className="text-base font-bold text-slate-800 dark:text-slate-100">{formatMoney(total, currency)}</span>
      </div>

      {userBudget > 0 && (
        <div className="mt-2 flex justify-between items-center">
          <span className="text-sm text-slate-500 dark:text-slate-400">Your budget</span>
          <span className="text-sm text-slate-600 dark:text-slate-300">{formatMoney(userBudget, currency)}</span>
        </div>
      )}

      {overage > 0 && (
        <div className="mt-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 px-3 py-2 text-xs text-red-600 dark:text-red-400">
          ⚠️ Marco's estimate is {formatMoney(overage, currency)} over your budget.
          Ask Marco to find cheaper options.
        </div>
      )}
    </div>
  )
}
