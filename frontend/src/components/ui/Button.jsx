import { cn } from '@/lib/utils'

const variants = {
  primary:  'bg-indigo-600 hover:bg-indigo-500 text-white border border-indigo-500 shadow-sm',
  secondary:'bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-sm',
  ghost:    'hover:bg-slate-100 text-slate-500 hover:text-slate-700 border border-transparent',
  danger:   'bg-red-50 hover:bg-red-100 text-red-600 border border-red-200',
}
const sizes = {
  sm:  'px-3 py-1.5 text-xs',
  md:  'px-4 py-2 text-sm',
  lg:  'px-5 py-2.5 text-base',
}

export function Button({ variant = 'secondary', size = 'md', className, children, ...props }) {
  return (
    <button
      className={cn(
        'inline-flex items-center gap-2 rounded-lg font-medium',
        'transition-colors duration-150 cursor-pointer',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}
