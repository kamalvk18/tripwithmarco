import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { ChevronDown } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'

export function DayCard({ day, isToday, isRebuilt }) {
  const [open, setOpen] = useState(isToday)

  return (
    <div
      className={cn(
        'rounded-xl border transition-colors',
        isToday
          ? 'border-indigo-600/60 bg-indigo-950/30'
          : 'border-[#2e3248] bg-[#1a1d27]',
      )}
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-3 px-5 py-4 text-left cursor-pointer"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className={cn(
            'shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold',
            isToday ? 'bg-indigo-600 text-white' : 'bg-[#22263a] text-slate-400',
          )}>
            {day.num}
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-semibold text-slate-100 truncate">
                {day.title || `Day ${day.num}`}
              </h3>
              {isToday && <Badge variant="active">← today</Badge>}
              {isRebuilt && <Badge variant="rebuilt">🔄 rebuilt</Badge>}
            </div>
          </div>
        </div>
        <ChevronDown
          size={16}
          className={`text-slate-500 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Content */}
      {open && (
        <div className="px-5 pb-5 border-t border-[#2e3248]/60">
          <div className="prose prose-sm max-w-none mt-4 text-slate-300">
            <ReactMarkdown>{day.content}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}
