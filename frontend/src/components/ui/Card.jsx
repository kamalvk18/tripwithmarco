import { cn } from '@/lib/utils'

export function Card({ className, children, ...props }) {
  return (
    <div
      className={cn(
        'rounded-xl border border-[#2e3248] bg-[#1a1d27] p-5',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardHeader({ className, children }) {
  return <div className={cn('mb-3', className)}>{children}</div>
}

export function CardTitle({ className, children }) {
  return (
    <h3 className={cn('text-base font-semibold text-slate-100', className)}>
      {children}
    </h3>
  )
}
