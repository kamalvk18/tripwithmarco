import { cn } from '@/lib/utils'

const variants = {
  upcoming: 'bg-blue-100 text-blue-700 border-blue-200',
  active:   'bg-emerald-100 text-emerald-700 border-emerald-200',
  past:     'bg-slate-100 text-slate-500 border-slate-200',
  rebuilt:  'bg-indigo-100 text-indigo-700 border-indigo-200',
  unknown:  'bg-slate-100 text-slate-500 border-slate-200',
}

export function Badge({ variant = 'past', className, children }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        variants[variant] ?? variants.past,
        className,
      )}
    >
      {children}
    </span>
  )
}
