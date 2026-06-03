import { useRef, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  RefreshCw, Navigation, RotateCcw, Download, Plane,
  Calendar, FileText, Wifi, Trash2, ArrowLeft, ExternalLink, LocateFixed, Map,
} from 'lucide-react'
import { buildMarkdown, buildICS, buildOfflineHTML, downloadFile } from '@/lib/exports'
import { saveDebrief, patchTrip } from '@/lib/api'
import { useTrip } from '@/hooks/useTrip'
import { useSSEChat } from '@/hooks/useSSEChat'
import { useWeatherCache } from '@/hooks/useWeatherCache'
import { useNearMe } from '@/hooks/useNearMe'
import { DayCard } from '@/components/DayCard'
import { TripMap } from '@/components/TripMap'
import { BudgetPanel } from '@/components/BudgetPanel'
import { ChatPanel } from '@/components/ChatPanel'
import { ExpenseTracker } from '@/components/ExpenseTracker'
import { ChecklistPanel } from '@/components/ChecklistPanel'
import { EmailBriefingConfig } from '@/components/EmailBriefingConfig'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'

export default function TripView() {
  const { id }   = useParams()
  const navigate = useNavigate()

  // ── Data & derived state (all trip concerns live in the hook) ──────────────
  const {
    tripData, loading,
    messages, days,
    status, label, dayNum,
    saveMessages, updateSpending, updateChecklist, updateEmailConfig,
    updateDayOverride, updateDebrief, updateNearMe, getCachedNearMeResponse, remove,
  } = useTrip(id)

  // ── UI-only state ──────────────────────────────────────────────────────────
  const { streaming, toolStatus, send } = useSSEChat()
  const { getWeather } = useWeatherCache()

  const { locate, locating } = useNearMe()

  const mapDays = useMemo(
    () => days.map(day => ({
      ...day,
      content: tripData?.day_overrides?.[String(day.num)] ?? day.content,
    })),
    [days, tripData?.day_overrides]
  )

  const [showMap, setShowMap]             = useState(false)
  const [showCompanion, setShowCompanion] = useState(false)
  const [weatherText, setWeatherText]     = useState(null)
  const [rebuilding, setRebuilding]       = useState(false)
  const [rebuildText, setRebuildText]     = useState('')
  const [nearMeActive, setNearMeActive]     = useState(false)
  const [nearMeText, setNearMeText]         = useState('')
  const [nearMeDismissed, setNearMeDismissed] = useState(false)
  const [debriefing, setDebriefing]       = useState(false)
  const [debriefText, setDebriefText]     = useState('')
  const [showExport, setShowExport]       = useState(false)
  const [emailPanelOpen, setEmailPanelOpen] = useState(false)
  const rebuildRef  = useRef('')
  const nearMeRef   = useRef('')
  const debriefRef  = useRef('')

  // ── Loading / not-found guards ─────────────────────────────────────────────
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

  // ── Companion toggle — fetch weather once on activation ───────────────────
  async function handleToggleCompanion() {
    const next = !showCompanion
    setShowCompanion(next)
    setRebuilding(false)

    if (next && status === 'active' && !weatherText) {
      const city = tripData.city || tripData.destination
      setWeatherText(await getWeather(city, tripData.country_code ?? ''))
    }
  }

  // ── Rebuild Today ──────────────────────────────────────────────────────────
  async function handleRebuildToday() {
    if (!dayNum) return
    setRebuilding(true)
    setShowCompanion(false)
    rebuildRef.current = ''
    setRebuildText('')

    const city   = tripData.city || tripData.destination
    const prompt = `Rebuild Day ${dayNum}'s itinerary based on today's actual weather in ${city}. Use the weather tool to check current conditions, then restructure: if rain or bad weather is forecast, move outdoor activities to better windows or swap for indoor alternatives. Keep the same neighbourhood and general vibe. Output ONLY the rebuilt day plan, starting with 'Day ${dayNum} — [New Title]'. No preamble.`

    await send({
      messages: [...messages, { role: 'user', content: prompt }],
      tripData,
      companionMode: true,
      onChunk: chunk => {
        rebuildRef.current += chunk
        setRebuildText(rebuildRef.current)
      },
      onDone: async () => {
        await updateDayOverride(dayNum, rebuildRef.current)
        setRebuilding(false)
        setRebuildText('')
      },
    })
  }

  // ── Near Me ───────────────────────────────────────────────────────────────
  async function handleNearMe(force = false) {
    setNearMeDismissed(false)

    // getCachedNearMeResponse reads from the module-level tripCache which is updated
    // synchronously inside patch() — always current, never affected by stale closures.
    const cached = getCachedNearMeResponse()
    if (!force && cached) {
      setNearMeText(cached)
      return
    }

    setNearMeActive(true)
    nearMeRef.current = ''
    setNearMeText('')

    const loc = await locate()
    if (!loc) { setNearMeActive(false); return }

    const prompt = `I'm currently at ${loc.display}. Based on today's itinerary, which activities or places are closest to where I am right now? What should I do next? Give me 2-3 specific, actionable options — keep it short and punchy.`

    await send({
      messages: [...messages, { role: 'user', content: prompt }],
      tripData,
      companionMode: true,
      onChunk: chunk => {
        nearMeRef.current += chunk
        setNearMeText(nearMeRef.current)
      },
      onDone: () => {
        setNearMeActive(false)
        updateNearMe(nearMeRef.current)
      },
    })
  }

  // ── Post-trip debrief ─────────────────────────────────────────────────────
  async function handleDebrief() {
    setDebriefing(true)
    setDebriefText('')
    debriefRef.current = ''

    const prompt = `This trip to ${tripData.destination} is now over — time for an honest debrief. Looking back at everything we planned and all our conversations: what worked really well about this itinerary, what would you change if we did it again, and what have you noticed about how I actually travel? Be specific about my preferences. Keep it under 250 words, no fluff.`

    await send({
      messages: [...messages, { role: 'user', content: prompt }],
      tripData,
      companionMode: false,
      onChunk: chunk => {
        debriefRef.current += chunk
        setDebriefText(debriefRef.current)
      },
      onDone: async () => {
        setDebriefing(false)
        // Save debrief + extract preferences via backend
        try {
          await saveDebrief(id, debriefRef.current)
          updateDebrief(debriefRef.current)
        } catch { /* non-critical — debrief text is still shown */ }
      },
    })
  }

  // ── Regenerate — re-open the plan form pre-filled ─────────────────────────
  function handleRegenerate() {
    const firstUser = messages.find(m => m.role === 'user')
    let origin = tripData.origin ?? ''
    if (!origin && firstUser) {
      const m = firstUser.content.match(/trip to .+ from ([^.]+)\./i)
      if (m) origin = m[1].trim()
    }
    navigate('/plan', {
      state: {
        prefill: {
          destination:            tripData.destination    ?? '',
          destinationCountryCode: tripData.country_code  ?? '',
          origin,
          startDate:  tripData.start_date ?? '',
          endDate:    tripData.end_date   ?? '',
          budget:     String(tripData.budget ?? ''),
          currency:   tripData.currency   ?? 'EUR',
          hasTwoWheelerLicence:  tripData.has_two_wheeler_licence  ?? false,
          hasFourWheelerLicence: tripData.has_four_wheeler_licence ?? false,
        },
      },
    })
  }

  // ── Continue planning (no itinerary yet) ─────────────────────────────────
  function handleContinuePlanning() {
    navigate('/plan', {
      state: {
        resume: {
          tripId:   id,
          messages: messages,
          meta: {
            destination:            tripData.destination    ?? '',
            destinationCountryCode: tripData.country_code   ?? '',
            origin:                 tripData.origin         ?? '',
            startDate:              tripData.start_date     ?? '',
            endDate:                tripData.end_date       ?? '',
            budget:                 String(tripData.budget ?? ''),
            currency:               tripData.currency       ?? 'EUR',
            hasTwoWheelerLicence:   tripData.has_two_wheeler_licence  ?? false,
            hasFourWheelerLicence:  tripData.has_four_wheeler_licence ?? false,
          },
        },
      },
    })
  }

  // ── Delete ─────────────────────────────────────────────────────────────────
  async function handleDelete() {
    if (!confirm('Delete this trip? This cannot be undone.')) return
    await remove()
    navigate('/')
  }

  // ── Render ─────────────────────────────────────────────────────────────────
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
            <Button
              variant="secondary"
              onClick={() => handleNearMe()}
              disabled={locating || nearMeActive || streaming}
              title="Find activities near your current location"
            >
              {locating || nearMeActive
                ? <Spinner className="w-3.5 h-3.5" />
                : <LocateFixed size={14} />}
              Near Me
            </Button>
          </>
        )}
        {status === 'past' && !tripData.debrief && (
          <Button
            variant="secondary"
            onClick={handleDebrief}
            disabled={debriefing || streaming}
          >
            {debriefing ? <Spinner className="w-3.5 h-3.5" /> : '📋'}
            {debriefing ? 'Getting debrief…' : 'Post-Trip Debrief'}
          </Button>
        )}
        {days.length === 0 && (
          <Button variant="primary" onClick={handleContinuePlanning}>
            <Plane size={14} /> Continue Planning
          </Button>
        )}
        <Button variant="secondary" onClick={handleRegenerate}>
          <RotateCcw size={14} /> Regenerate Plan
        </Button>
        {days.length > 0 && (
          <Button
            variant={showMap ? 'primary' : 'ghost'}
            onClick={() => setShowMap(m => !m)}
          >
            <Map size={14} /> {showMap ? 'Hide Map' : 'Map'}
          </Button>
        )}
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
      {(tripData.budget > 0 || (tripData.budget_breakdown && Object.keys(tripData.budget_breakdown).length > 0)) && (
        <div className="mb-4">
          <BudgetPanel
            breakdown={tripData.budget_breakdown}
            userBudget={tripData.budget}
            currency={tripData.currency ?? 'EUR'}
          />
        </div>
      )}

      {/* Expense tracker */}
      {(status === 'upcoming' || status === 'active' || status === 'past') && (
        <div className="mb-4">
          <ExpenseTracker
            tripId={id}
            spending={tripData.spending ?? []}
            breakdown={tripData.budget_breakdown ?? {}}
            currency={tripData.currency ?? 'EUR'}
            onUpdate={updateSpending}
          />
        </div>
      )}

      {/* Pre-trip checklist */}
      {(status === 'upcoming' || status === 'active') && (
        <div className="mb-4">
          <ChecklistPanel
            tripId={id}
            destination={tripData.destination}
            items={tripData.checklist ?? []}
            onUpdate={updateChecklist}
          />
        </div>
      )}

      {/* Daily briefing email */}
      {(status === 'upcoming' || status === 'active') && (
        <div className="mb-6 space-y-2">
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
            onUpdate={updateEmailConfig}
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
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{rebuildText}</ReactMarkdown>
            </div>
          )}
        </div>
      )}

      {/* Debrief — streaming output */}
      {debriefing && (
        <div className="rounded-xl border border-violet-700/50 bg-violet-950/20 p-5 mb-6">
          <div className="flex items-center gap-2 text-sm text-violet-300 mb-3">
            <Spinner className="w-4 h-4" />
            {toolStatus ?? 'Marco is writing your debrief…'}
          </div>
          {debriefText && (
            <div className="prose prose-sm max-w-none text-slate-200 streaming-cursor">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{debriefText}</ReactMarkdown>
            </div>
          )}
        </div>
      )}

      {/* Debrief — persisted display */}
      {!debriefing && tripData.debrief && (
        <div className="rounded-xl border border-violet-700/40 bg-violet-950/20 p-5 mb-6">
          <p className="text-xs font-semibold text-violet-400 uppercase tracking-wide mb-3">
            📋 Post-Trip Debrief
          </p>
          <div className="prose prose-sm max-w-none text-slate-300">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{tripData.debrief}</ReactMarkdown>
          </div>
          {tripData.preferences?.length > 0 && (
            <div className="mt-4 pt-4 border-t border-violet-700/30">
              <p className="text-xs font-semibold text-violet-400 uppercase tracking-wide mb-2">
                Your travel preferences
              </p>
              <div className="flex flex-wrap gap-2">
                {tripData.preferences.map((pref, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded-full text-xs border border-violet-600/40 bg-violet-900/20 text-violet-200"
                  >
                    {pref}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Near Me — streaming + persisted */}
      {!nearMeDismissed && (nearMeActive || nearMeText || tripData.near_me_response) && (
        <div className="rounded-xl border border-emerald-700/50 bg-emerald-950/20 p-5 mb-6">
          <div className="flex items-center justify-between gap-2 text-sm text-emerald-300 mb-3">
            <div className="flex items-center gap-2">
              {nearMeActive
                ? <><Spinner className="w-4 h-4" /> {locating ? 'Getting your location…' : (toolStatus ?? "Finding what's near you…")}</>
                : <><LocateFixed size={14} /> What's near you</>
              }
            </div>
            {!nearMeActive && (
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => handleNearMe(true)}
                  disabled={streaming}
                  className="text-xs text-emerald-600 hover:text-emerald-400 transition-colors cursor-pointer"
                >
                  <RefreshCw size={12} className="inline mr-1" />refresh
                </button>
                <button
                  type="button"
                  onClick={() => setNearMeDismissed(true)}
                  className="text-xs text-emerald-600 hover:text-emerald-400 transition-colors cursor-pointer"
                >
                  dismiss
                </button>
              </div>
            )}
          </div>
          {(nearMeText || tripData.near_me_response) && (
            <div className={`prose prose-sm max-w-none text-slate-200 ${nearMeActive ? 'streaming-cursor' : ''}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{nearMeText || tripData.near_me_response}</ReactMarkdown>
            </div>
          )}
        </div>
      )}

      {/* Map view */}
      {showMap && days.length > 0 && (
        <TripMap
          days={mapDays}
          destination={tripData.destination}
          city={tripData.city}
        />
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
              destination={tripData.city || tripData.destination}
            />
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-[#2e3248] p-8 mb-8 text-center">
          <p className="text-slate-400 text-sm">No itinerary yet.</p>
          <p className="text-slate-500 text-xs mt-1">Use "Continue Planning" above to finish building your trip.</p>
        </div>
      )}

      {/* Booking links */}
      {(() => {
        const dest   = tripData.destination ?? ''
        const origin = tripData.origin ?? ''
        const start  = tripData.start_date ?? ''
        const end    = tripData.end_date ?? ''
        if (!dest || !start || !end) return null

        const enc = encodeURIComponent
        const links = [
          ...(origin ? [{
            label: 'Search Flights',
            url: `https://www.google.com/travel/flights?q=flights+from+${enc(origin)}+to+${enc(dest)}+${start}+to+${end}`,
          }] : []),
          ...(tripData.hotel_suggestions?.length > 0
            ? tripData.hotel_suggestions.map(h => ({
                label: h.name,
                url: `https://www.booking.com/searchresults.html?ss=${enc(`${h.name} ${h.destination}`)}&checkin=${h.check_in}&checkout=${h.check_out}&group_adults=1`,
              }))
            : [{
                label: 'Search Hotels',
                url: `https://www.booking.com/searchresults.html?ss=${enc(dest)}&checkin=${start}&checkout=${end}&group_adults=1`,
              }]
          ),
          {
            label: 'Airbnb',
            url: `https://www.airbnb.com/s/${enc(dest)}/homes?checkin=${start}&checkout=${end}&adults=1`,
          },
        ]

        return (
          <div className="rounded-xl border border-[#2e3248] bg-[#1a1d27] p-4 mb-6">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Book Your Trip</p>
            <div className="flex flex-wrap gap-2">
              {links.map(({ label, url }) => (
                <a
                  key={label}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm
                    bg-[#22263a] border border-[#2e3248] text-slate-300
                    hover:border-indigo-500/60 hover:text-indigo-300 transition-colors"
                >
                  {label} <ExternalLink size={12} className="opacity-60" />
                </a>
              ))}
            </div>
          </div>
        )
      })()}

      {/* Companion / Chat panel */}
      {showCompanion && status === 'active' ? (
        <ChatPanel
          messages={messages}
          tripData={tripData}
          companion
          weatherText={weatherText}
          onSave={saveMessages}
        />
      ) : (
        <ChatPanel
          messages={messages}
          tripData={tripData}
          onSave={saveMessages}
        />
      )}
    </div>
  )
}
