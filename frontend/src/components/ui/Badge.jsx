import { cn } from '@/lib/utils'

const variants = {
  upcoming: 'bg-blue-900/40  text-blue-300  border-blue-800/50',
  active:   'bg-green-900/40 text-green-300 border-green-800/50',
  past:     'bg-slate-800/60 text-slate-400 border-slate-700/50',
  rebuilt:  'bg-indigo-900/40 text-indigo-300 border-indigo-700/50',
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
