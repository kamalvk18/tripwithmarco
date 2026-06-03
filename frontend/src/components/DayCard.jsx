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
  amber:  { dot: 'bg-amber-400',  label: 'text-amber-300',  border: 'border-amber-500/30',  bg: 'bg-amber-900/10'  },
  sky:    { dot: 'bg-sky-400',    label: 'text-sky-300',    border: 'border-sky-500/30',    bg: 'bg-sky-900/10'    },
  orange: { dot: 'bg-orange-400', label: 'text-orange-300', border: 'border-orange-500/30', bg: 'bg-orange-900/10' },
  violet: { dot: 'bg-violet-400', label: 'text-violet-300', border: 'border-violet-500/30', bg: 'bg-violet-900/10' },
  slate:  { dot: 'bg-slate-400',  label: 'text-slate-300',  border: 'border-slate-500/30',  bg: 'bg-slate-800/20'  },
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
        <div className="prose prose-sm max-w-none text-slate-400">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{timeline.intro}</ReactMarkdown>
        </div>
      )}

      {/* Time slots */}
      <div className="relative">
        {/* Vertical connector line */}
        <div className="absolute left-[11px] top-5 bottom-5 w-px bg-[#2e3248]" />

        <div className="space-y-3">
          {timeline.slots.map((slot, i) => {
            const c = SLOT_COLORS[slot.color] ?? SLOT_COLORS.slate
            const icon = SLOT_ICONS[slot.color] ?? '🕐'
            return (
              <div key={i} className="relative flex gap-4">
                {/* Dot */}
                <div className={cn('shrink-0 w-6 h-6 rounded-full flex items-center justify-center z-10 mt-0.5', c.bg, 'border', c.border)}>
                  <span className="text-xs leading-none">{icon}</span>
                </div>

                {/* Card */}
                <div className={cn('flex-1 rounded-lg border p-3', c.border, c.bg)}>
                  <p className={cn('text-xs font-semibold uppercase tracking-wide mb-2', c.label)}>
                    {slot.label}
                  </p>
                  {slot.content && (
                    <div className="prose prose-sm max-w-none text-slate-300
                      [&_ul]:mt-1 [&_ul]:space-y-1 [&_li]:leading-snug
                      [&_p]:mb-1 [&_strong]:text-slate-100">
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
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-emerald-700/30 bg-emerald-900/10">
          <span className="text-sm">💰</span>
          <p className="text-xs text-emerald-300">{timeline.budget}</p>
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

  // If timeline isn't parseable, force text mode
  const effectiveMode = canTimeline ? viewMode : 'text'

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
        <div className="flex items-center gap-2 shrink-0">
          {destination && (
            <a
              href={mapUrl(day.title || '', destination)}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-400 hover:bg-indigo-900/20 transition-colors"
              title="View on map"
            >
              <MapPin size={14} />
            </a>
          )}
          <ChevronDown
            size={16}
            className={`text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      {/* Content */}
      {open && (
        <div className="px-5 pb-5 border-t border-[#2e3248]/60">
          {/* View toggle — only shown when timeline is available */}
          {canTimeline && (
            <div className="flex gap-1 mt-3 mb-1">
              <button
                type="button"
                onClick={() => setViewMode('timeline')}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors cursor-pointer',
                  effectiveMode === 'timeline'
                    ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-600/40'
                    : 'text-slate-500 hover:text-slate-300 border border-transparent',
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
                    ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-600/40'
                    : 'text-slate-500 hover:text-slate-300 border border-transparent',
                )}
              >
                <AlignLeft size={11} /> Text
              </button>
            </div>
          )}

          {effectiveMode === 'timeline' && timeline ? (
            <TimelineView timeline={timeline} />
          ) : (
            <div className="prose prose-sm max-w-none mt-4 text-slate-300">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{day.content}</ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
