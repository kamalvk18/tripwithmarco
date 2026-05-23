import { cn } from '@/lib/utils'

const variants = {
  primary:  'bg-indigo-600 hover:bg-indigo-500 text-white border border-indigo-500',
  secondary:'bg-[#1a1d27] hover:bg-[#22263a] text-slate-200 border border-[#2e3248]',
  ghost:    'hover:bg-[#22263a] text-slate-400 hover:text-slate-200 border border-transparent',
  danger:   'bg-red-900/40 hover:bg-red-800/50 text-red-400 border border-red-800/60',
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
