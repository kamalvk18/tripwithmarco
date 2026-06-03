import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChevronDown, MapPin, AlignLeft, Clock } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'
import { parseTimeline } from '@/lib/parseTimeline'

function mapUrl(title, destination) {
  const theme = title
    .replace(/^Day\s+\d+(?:-\d+)?(?:\s*\([^)]*\))?\s*[—\-–:]+\s*/i, '')
    .replace(/^(?:\w+,\s+)?\w+\s+\d+[,:]\s*/i, '')
    .trim()
  const q = theme ? `${theme}, ${destination}` : destination
  return `https://maps.google.com/?q=${encodeURIComponent(q)}`
}

const SLOT_COLORS = {
  amber:  { dot: 'bg-amber-400',  label: 'text-amber-700',  border: 'border-amber-200',  bg: 'bg-amber-50'  },
  sky:    { dot: 'bg-sky-400',    label: 'text-sky-700',    border: 'border-sky-200',    bg: 'bg-sky-50'    },
  orange: { dot: 'bg-orange-400', label: 'text-orange-700', border: 'border-orange-200', bg: 'bg-orange-50' },
  violet: { dot: 'bg-violet-500', label: 'text-violet-700', border: 'border-violet-200', bg: 'bg-violet-50' },
  slate:  { dot: 'bg-slate-400',  label: 'text-slate-600',  border: 'border-slate-200',  bg: 'bg-slate-50'  },
}

const SLOT_ICONS = {
  amber:  '🌅',
  sky:    '☀️',
  orange: '🌆',
  violet: '🌙',
  slate:  '🕐',
}

function TimelineView({ timeline }) {
  return (
    <div className="mt-4 space-y-4">
      {timeline.intro && (
        <div className="prose prose-sm max-w-none text-slate-600">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{timeline.intro}</ReactMarkdown>
        </div>
      )}

      {/* Time slots */}
      <div className="relative">
        {/* Vertical connector line */}
        <div className="absolute left-[11px] top-5 bottom-5 w-px bg-slate-200" />

        <div className="space-y-3">
          {timeline.slots.map((slot, i) => {
            const c = SLOT_COLORS[slot.color] ?? SLOT_COLORS.slate
            const icon = SLOT_ICONS[slot.color] ?? '🕐'
            return (
              <div key={i} className="relative flex gap-4">
                {/* Dot */}
                <div className={cn('shrink-0 w-6 h-6 rounded-full flex items-center justify-center z-10 mt-0.5 border', c.bg, c.border)}>
                  <span className="text-xs leading-none">{icon}</span>
                </div>

                {/* Card */}
                <div className={cn('flex-1 rounded-lg border p-3', c.border, c.bg)}>
                  <p className={cn('text-xs font-semibold uppercase tracking-wide mb-2', c.label)}>
                    {slot.label}
                  </p>
                  {slot.content && (
                    <div className="prose prose-sm max-w-none text-slate-700
                      [&_ul]:mt-1 [&_ul]:space-y-1 [&_li]:leading-snug
                      [&_p]:mb-1 [&_strong]:text-slate-800">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{slot.content}</ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Budget today */}
      {timeline.budget && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-emerald-200 bg-emerald-50">
          <span className="text-sm">💰</span>
          <p className="text-xs text-emerald-700 font-medium">{timeline.budget}</p>
        </div>
      )}
    </div>
  )
}

export function DayCard({ day, isToday, isRebuilt, destination }) {
  const [open, setOpen] = useState(isToday)
  const [viewMode, setViewMode] = useState('timeline')

  const timeline = parseTimeline(day.content)
  const canTimeline = !!timeline

  const effectiveMode = canTimeline ? viewMode : 'text'

  return (
    <div
      className={cn(
        'rounded-xl border transition-all duration-200',
        isToday
          ? 'border-indigo-300 border-l-4 border-l-indigo-500 bg-indigo-50 shadow-md'
          : 'border-slate-200 bg-white shadow-sm hover:shadow-md',
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
            isToday ? 'bg-indigo-600 text-white shadow-sm' : 'bg-slate-100 text-slate-600',
          )}>
            {day.num}
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className={cn(
                'text-sm font-semibold truncate',
                isToday ? 'text-indigo-900' : 'text-slate-800',
              )}>
                {day.title || `Day ${day.num}`}
              </h3>
              {isToday && <Badge variant="active">← today</Badge>}
              {isRebuilt && <Badge variant="rebuilt">🔄 rebuilt</Badge>}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {destination && (
            <a
              href={mapUrl(day.title || '', destination)}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
              title="View on map"
            >
              <MapPin size={14} />
            </a>
          )}
          <ChevronDown
            size={16}
            className={cn(
              'transition-transform',
              isToday ? 'text-indigo-400' : 'text-slate-400',
              open ? 'rotate-180' : '',
            )}
          />
        </div>
      </button>

      {/* Content */}
      {open && (
        <div className={cn(
          'px-5 pb-5 border-t',
          isToday ? 'border-indigo-200' : 'border-slate-100',
        )}>
          {/* View toggle — only shown when timeline is available */}
          {canTimeline && (
            <div className="flex gap-1 mt-3 mb-1">
              <button
                type="button"
                onClick={() => setViewMode('timeline')}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer',
                  effectiveMode === 'timeline'
                    ? 'bg-indigo-100 text-indigo-700 border border-indigo-200'
                    : 'text-slate-500 hover:text-slate-700 border border-transparent hover:border-slate-200',
                )}
              >
                <Clock size={11} /> Timeline
              </button>
              <button
                type="button"
                onClick={() => setViewMode('text')}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer',
                  effectiveMode === 'text'
                    ? 'bg-indigo-100 text-indigo-700 border border-indigo-200'
                    : 'text-slate-500 hover:text-slate-700 border border-transparent hover:border-slate-200',
                )}
              >
                <AlignLeft size={11} /> Text
              </button>
            </div>
          )}

          {effectiveMode === 'timeline' && timeline ? (
            <TimelineView timeline={timeline} />
          ) : (
            <div className="prose prose-sm max-w-none mt-4 text-slate-700">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{day.content}</ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
