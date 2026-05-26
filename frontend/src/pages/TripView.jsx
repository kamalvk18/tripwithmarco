import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import {
  RefreshCw, Navigation, RotateCcw, Download,
  Calendar, FileText, Wifi, Trash2, ArrowLeft,
} from 'lucide-react'
import { loadTrip, updateTrip, deleteTrip } from '@/lib/api'
import { extractAllDays, tripStatus } from '@/lib/utils'
import { buildMarkdown, buildICS, buildOfflineHTML, downloadFile } from '@/lib/exports'
import { useSSEChat } from '@/hooks/useSSEChat'
import { useWeatherCache } from '@/hooks/useWeatherCache'
import { DayCard } from '@/components/DayCard'
import { BudgetPanel } from '@/components/BudgetPanel'
import { ChatPanel } from '@/components/ChatPanel'
import { ExpenseTracker } from '@/components/ExpenseTracker'
import { ChecklistPanel } from '@/components/ChecklistPanel'
import { EmailBriefingConfig } from '@/components/EmailBriefingConfig'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'

export default function TripView() {
  const { id }      = useParams()
  const navigate    = useNavigate()
  const { streaming, toolStatus, send } = useSSEChat()
  const { getWeather } = useWeatherCache()

  const [tripData, setTripData]       = useState(null)
  const [loading, setLoading]         = useState(true)
  const [showCompanion, setShowCompanion] = useState(false)
  const [weatherText, setWeatherText] = useState(null)
  const [rebuilding, setRebuilding]   = useState(false)
  const [rebuildText, setRebuildText] = useState('')
  const [showExport, setShowExport] = useState(false)
  const [emailPanelOpen, setEmailPanelOpen] = useState(false)
  const rebuildRef = useRef('')

  useEffect(() => {
    setLoading(true)
    loadTrip(id).then(data => {
      setTripData(data)
      setLoading(false)
    })
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 gap-2 text-slate-400">
        <Spinner /> Loading trip…
      </div>
    )
  }
  if (!tripData) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-slate-500">
        <p>Trip not found.</p>
        <Button onClick={() => navigate('/')}>← Back home</Button>
      </div>
    )
  }

  const messages     = tripData.messages ?? []
  const assistantMsgs = messages.filter(m => m.role === 'assistant')
  // Use the LAST assistant message that contains day-by-day content.
  // In a multi-turn planning conversation the first assistant message is often
  // Marco asking clarifying questions / presenting options — not the itinerary.
  const rawItinerary = (
    [...assistantMsgs].reverse().find(m => /\bday\s+\d+\b/i.test(m.content))
    ?? assistantMsgs[0]
  )?.content ?? ''
  // Strip any [OPTION: ...] markers left over from the planning conversation
  const itinerary = rawItinerary
    .replace(/\[OPTION:[^\]]*\]/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
  const days      = extractAllDays(itinerary)
  const { status, label, dayNum } = tripStatus(tripData)

  // ── Companion toggle — fetch weather once on activation ───────────────────
  async function handleToggleCompanion() {
    const next = !showCompanion
    setShowCompanion(next)
    setRebuilding(false)

    if (next && tripData && status === 'active' && !weatherText) {
      const city        = tripData.city || tripData.destination
      const countryCode = tripData.country_code ?? ''
      const text = await getWeather(city, countryCode)
      setWeatherText(text)   // null on failure — backend falls back to its own fetch
    }
  }

  // ── Rebuild Today ──────────────────────────────────────────────────────────
  async function handleRebuildToday() {
    if (!dayNum) return
    setRebuilding(true)
    setShowCompanion(false)
    rebuildRef.current = ''
    setRebuildText('')

    const city = tripData.city || tripData.destination
    const prompt = `Rebuild Day ${dayNum}'s itinerary based on today's actual weather in ${city}. Use the weather tool to check current conditions, then restructure: if rain or bad weather is forecast, move outdoor activities to better windows or swap for indoor alternatives. Keep the same neighbourhood and general vibe. Output ONLY the rebuilt day plan, starting with 'Day ${dayNum} — [New Title]'. No preamble.`

    const msgs = [...messages, { role: 'user', content: prompt }]

    await send({
      messages: msgs,
      tripData,
      companionMode: true,
      onChunk: (chunk) => {
        rebuildRef.current += chunk
        setRebuildText(rebuildRef.current)
      },
      onDone: async () => {
        const rebuilt = rebuildRef.current
        const overrides = { ...(tripData.day_overrides ?? {}), [String(dayNum)]: rebuilt }
        const updated   = { ...tripData, day_overrides: overrides }
        setTripData(updated)
        await updateTrip(id, updated)
        setRebuilding(false)
        setRebuildText('')
      },
    })
  }

  // ── Regenerate ─────────────────────────────────────────────────────────────
  async function handleRegenerate() {
    const firstUser = messages.find(m => m.role === 'user')
    if (!firstUser) return
    navigate('/plan')   // simplest: send back to plan with same prompt pre-filled
  }

  // ── Save (called by ChatPanel after each message) ──────────────────────────
  async function handleSave(updatedMessages) {
    const updated = { ...tripData, messages: updatedMessages }
    setTripData(updated)
    await updateTrip(id, updated)
  }

  // ── Expense / Checklist local updates ────────────────────────────────────
  function handleSpendingUpdate(newSpending) {
    setTripData(t => ({ ...t, spending: newSpending }))
  }

  function handleChecklistUpdate(newItems) {
    setTripData(t => ({ ...t, checklist: newItems }))
  }

  function handleEmailConfigUpdate(newConfig) {
    setTripData(t => ({ ...t, email_config: newConfig }))
  }

  // ── Delete ─────────────────────────────────────────────────────────────────
  async function handleDelete() {
    if (!confirm('Delete this trip? This cannot be undone.')) return
    await deleteTrip(id)
    navigate('/')
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      {/* Back */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-300 mb-6 cursor-pointer"
      >
        <ArrowLeft size={14} /> All trips
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 mb-1">{tripData.destination}</h1>
          <p className="text-slate-400 text-sm">{tripData.dates}</p>
          <div className="mt-2">
            <Badge variant={status}>{label}</Badge>
          </div>
        </div>
        <button
          onClick={handleDelete}
          className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-900/20 transition-colors cursor-pointer"
          title="Delete trip"
        >
          <Trash2 size={16} />
        </button>
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2 mb-6">
        {status === 'active' && (
          <>
            <Button
              variant={showCompanion ? 'primary' : 'secondary'}
              onClick={handleToggleCompanion}
            >
              <Navigation size={14} />
              {showCompanion ? 'Hide Companion' : '🧭 Companion Mode'}
            </Button>
            <Button
              variant="secondary"
              onClick={handleRebuildToday}
              disabled={rebuilding || streaming}
            >
              {rebuilding ? <Spinner className="w-3.5 h-3.5" /> : <RefreshCw size={14} />}
              Rebuild Today
            </Button>
          </>
        )}
        <Button variant="secondary" onClick={handleRegenerate}>
          <RotateCcw size={14} /> Regenerate Plan
        </Button>
        <Button variant="ghost" onClick={() => setShowExport(e => !e)}>
          <Download size={14} /> Export
        </Button>
      </div>

      {/* Export panel */}
      {showExport && (
        <div className="rounded-xl border border-[#2e3248] bg-[#1a1d27] p-5 mb-6">
          <h3 className="text-sm font-semibold text-slate-200 mb-3">📤 Export & Share</h3>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              onClick={() => {
                const md = buildMarkdown(tripData, days)
                downloadFile(md, `${tripData.destination.replace(/[^a-z0-9]/gi, '_')}.md`, 'text/markdown')
              }}
            >
              <FileText size={13} /> Markdown (.md)
            </Button>
            <Button
              size="sm"
              onClick={() => {
                const ics = buildICS(tripData, days)
                downloadFile(ics, `${tripData.destination.replace(/[^a-z0-9]/gi, '_')}.ics`, 'text/calendar')
              }}
            >
              <Calendar size={13} /> Calendar (.ics)
            </Button>
            <Button
              size="sm"
              onClick={() => {
                const html = buildOfflineHTML(tripData, days)
                downloadFile(html, `${tripData.destination.replace(/[^a-z0-9]/gi, '_')}_offline.html`, 'text/html')
              }}
            >
              <Wifi size={13} /> Offline HTML
            </Button>
          </div>
        </div>
      )}

      {/* Budget */}
      {tripData.budget_breakdown && Object.keys(tripData.budget_breakdown).length > 0 && (
        <div className="mb-4">
          <BudgetPanel
            breakdown={tripData.budget_breakdown}
            userBudget={tripData.budget}
            currency={tripData.currency ?? 'EUR'}
          />
        </div>
      )}

      {/* Expense tracker — active or past trips */}
      {(status === 'active' || status === 'past') && (
        <div className="mb-4">
          <ExpenseTracker
            tripId={id}
            spending={tripData.spending ?? []}
            breakdown={tripData.budget_breakdown ?? {}}
            currency={tripData.currency ?? 'EUR'}
            onUpdate={handleSpendingUpdate}
          />
        </div>
      )}

      {/* Pre-trip checklist — upcoming or active trips */}
      {(status === 'upcoming' || status === 'active') && (
        <div className="mb-4">
          <ChecklistPanel
            tripId={id}
            destination={tripData.destination}
            items={tripData.checklist ?? []}
            onUpdate={handleChecklistUpdate}
          />
        </div>
      )}

      {/* Daily briefing email — upcoming or active trips */}
      {(status === 'upcoming' || status === 'active') && (
        <div className="mb-6 space-y-2">
          {/* Nudge banner — only shown when email not yet configured */}
          {!tripData.email_config?.email && (
            <button
              type="button"
              onClick={() => setEmailPanelOpen(true)}
              className="w-full flex items-center justify-between gap-3 rounded-xl
                border border-indigo-700/40 bg-indigo-900/20 px-4 py-3
                text-left hover:bg-indigo-900/30 transition-colors cursor-pointer group"
            >
              <div className="flex items-center gap-3">
                <span className="text-lg">📧</span>
                <div>
                  <p className="text-sm font-medium text-indigo-200">
                    Get Marco's daily briefing in your inbox
                  </p>
                  <p className="text-xs text-indigo-400 mt-0.5">
                    Weather + today's plan + budget — every morning, automatically
                  </p>
                </div>
              </div>
              <span className="text-xs text-indigo-400 group-hover:text-indigo-200 shrink-0 transition-colors">
                Set up →
              </span>
            </button>
          )}

          <EmailBriefingConfig
            tripId={id}
            emailConfig={tripData.email_config ?? {}}
            onUpdate={handleEmailConfigUpdate}
            forceOpen={emailPanelOpen}
            onOpenChange={setEmailPanelOpen}
          />
        </div>
      )}

      {/* Rebuild Today — streaming output */}
      {rebuilding && (
        <div className="rounded-xl border border-indigo-700/50 bg-indigo-950/30 p-5 mb-6">
          <div className="flex items-center gap-2 text-sm text-indigo-300 mb-3">
            {toolStatus
              ? <><Spinner className="w-4 h-4" /> {toolStatus}</>
              : <><Spinner className="w-4 h-4" /> Rebuilding Day {dayNum} around today's weather…</>
            }
          </div>
          {rebuildText && (
            <div className={`prose prose-sm max-w-none ${streaming ? 'streaming-cursor' : ''}`}>
              <ReactMarkdown>{rebuildText}</ReactMarkdown>
            </div>
          )}
        </div>
      )}

      {/* Day cards */}
      {days.length > 0 ? (
        <div className="flex flex-col gap-3 mb-8">
          {days.map(day => (
            <DayCard
              key={day.num}
              day={{
                ...day,
                content: tripData.day_overrides?.[String(day.num)] ?? day.content,
              }}
              isToday={day.num === dayNum}
              isRebuilt={!!tripData.day_overrides?.[String(day.num)]}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-[#2e3248] bg-[#1a1d27] p-5 mb-8">
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{itinerary}</ReactMarkdown>
          </div>
        </div>
      )}

      {/* Companion / Chat panel */}
      {showCompanion && status === 'active' ? (
        <ChatPanel
          messages={messages}
          tripData={tripData}
          companion
          weatherText={weatherText}
          onSave={handleSave}
        />
      ) : (
        <ChatPanel
          messages={messages}
          tripData={tripData}
          onSave={handleSave}
        />
      )}
    </div>
  )
}
