import { useRef, useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  RefreshCw, Navigation, RotateCcw, Download, Plane,
  Calendar, FileText, Wifi, Trash2, ArrowLeft, ExternalLink, LocateFixed, Map, Share2,
} from 'lucide-react'
import { buildMarkdown, buildICS, buildOfflineHTML, downloadFile } from '@/lib/exports'
import { saveDebrief } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
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
import { SharePanel, MemberAvatarStack } from '@/components/SharePanel'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'

export default function TripView() {
  const { id }   = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()

  // ── Data & derived state (all trip concerns live in the hook) ──────────────
  const {
    tripData, loading,
    messages, days,
    status, label, dayNum,
    saveMessages, updateSpending, updateSettlements, updateChecklist, updateEmailConfig,
    updateDayOverride, updateDebrief, updateNearMe, getCachedNearMeResponse, remove,
    updateMembers,
  } = useTrip(id)

  const isOwner = tripData?.is_owner ?? true  // default true for own trips before load

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
  const [showShare, setShowShare]         = useState(false)
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
  const [chatError, setChatError]         = useState(null)
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
      onError: msg => { setRebuilding(false); setChatError(msg) },
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
      onError: msg => { setNearMeActive(false); setChatError(msg) },
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
      onError: msg => { setDebriefing(false); setChatError(msg) },
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
          numberOfTravelers: tripData.number_of_travelers ?? 1,
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
            numberOfTravelers:      tripData.number_of_travelers ?? 1,
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
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
      {/* Back */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 mb-6 cursor-pointer transition-colors"
      >
        <ArrowLeft size={14} /> All trips
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50 mb-1">{tripData.destination}</h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm">{tripData.dates}</p>
          <div className="mt-2 flex items-center gap-3 flex-wrap">
            <Badge variant={status}>{label}</Badge>
            {tripData.members?.length > 1 && (
              <MemberAvatarStack members={tripData.members} max={5} />
            )}
            {!isOwner && (
              <span className="text-xs text-slate-400 italic">
                Shared by {tripData.members?.find(m => m.role === 'owner')?.name ?? 'someone'}
              </span>
            )}
          </div>
        </div>
        {isOwner && (
          <button
            onClick={handleDelete}
            className="p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors cursor-pointer"
            title="Delete trip"
          >
            <Trash2 size={16} />
          </button>
        )}
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
        {isOwner && status === 'past' && !tripData.debrief && (
          <Button
            variant="secondary"
            onClick={handleDebrief}
            disabled={debriefing || streaming}
          >
            {debriefing ? <Spinner className="w-3.5 h-3.5" /> : '📋'}
            {debriefing ? 'Getting debrief…' : 'Post-Trip Debrief'}
          </Button>
        )}
        {days.length === 0 && isOwner && (
          <Button variant="primary" onClick={handleContinuePlanning}>
            <Plane size={14} /> Continue Planning
          </Button>
        )}
        {isOwner && (
          <Button variant="secondary" onClick={handleRegenerate}>
            <RotateCcw size={14} /> Regenerate Plan
          </Button>
        )}
        <Button
          variant="secondary"
          onClick={() => setShowShare(s => !s)}
        >
          <Share2 size={14} /> {showShare ? 'Hide Share' : 'Share'}
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
        <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm p-5 mb-6">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">📤 Export & Share</h3>
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

      {/* Share & Members panel */}
      {showShare && (
        <div className="mb-4">
          <SharePanel
            tripId={id}
            isOwner={isOwner}
            members={tripData.members ?? []}
            onMembersChange={updateMembers}
            onLeave={() => navigate('/')}
          />
        </div>
      )}

      {/* Budget — per-person budget */}
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
            settlements={tripData.settlements ?? []}
            breakdown={tripData.budget_breakdown ?? {}}
            currency={tripData.currency ?? 'EUR'}
            currentUserId={user?.id}
            isOwner={isOwner}
            members={tripData.members ?? []}
            onUpdate={updateSpending}
            onSettlementsUpdate={updateSettlements}
          />
        </div>
      )}

      {/* Pre-trip checklist */}
      {(status === 'upcoming' || status === 'active') && (
        <div className="mb-4">
          <ChecklistPanel
            tripId={id}
            destination={tripData.destination}
            originCountry={tripData.origin_country}
            items={tripData.checklist ?? []}
            onUpdate={updateChecklist}
          />
        </div>
      )}

      {/* Daily briefing email — owner only */}
      {isOwner && (status === 'upcoming' || status === 'active') && (
        <div className="mb-6 space-y-2">
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
        <div className="rounded-xl border border-indigo-200 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/20 p-5 mb-6">
          <div className="flex items-center gap-2 text-sm text-indigo-700 dark:text-indigo-300 mb-3">
            {toolStatus
              ? <><Spinner className="w-4 h-4" /> {toolStatus}</>
              : <><Spinner className="w-4 h-4" /> Rebuilding Day {dayNum} around today's weather…</>
            }
          </div>
          {rebuildText && (
            <div className={`prose prose-sm max-w-none text-slate-700 dark:text-slate-300 ${streaming ? 'streaming-cursor' : ''}`}>
              <ReactMarkdown remarkPlugins={[[remarkGfm, { singleTilde: false }]]}>{rebuildText}</ReactMarkdown>
            </div>
          )}
        </div>
      )}

      {/* Debrief — streaming output */}
      {debriefing && (
        <div className="rounded-xl border border-violet-200 dark:border-violet-700 bg-violet-50 dark:bg-violet-900/20 p-5 mb-6">
          <div className="flex items-center gap-2 text-sm text-violet-700 dark:text-violet-300 mb-3">
            <Spinner className="w-4 h-4" />
            {toolStatus ?? 'Marco is writing your debrief…'}
          </div>
          {debriefText && (
            <div className="prose prose-sm max-w-none text-slate-700 dark:text-slate-300 streaming-cursor">
              <ReactMarkdown remarkPlugins={[[remarkGfm, { singleTilde: false }]]}>{debriefText}</ReactMarkdown>
            </div>
          )}
        </div>
      )}

      {/* Debrief — persisted display */}
      {!debriefing && tripData.debrief && (
        <div className="rounded-xl border border-violet-200 dark:border-violet-700 bg-violet-50 dark:bg-violet-900/20 p-5 mb-6">
          <p className="text-xs font-semibold text-violet-600 dark:text-violet-400 uppercase tracking-wide mb-3">
            📋 Post-Trip Debrief
          </p>
          <div className="prose prose-sm max-w-none text-slate-700 dark:text-slate-300">
            <ReactMarkdown remarkPlugins={[[remarkGfm, { singleTilde: false }]]}>{tripData.debrief}</ReactMarkdown>
          </div>
          {tripData.preferences?.length > 0 && (
            <div className="mt-4 pt-4 border-t border-violet-200 dark:border-violet-700">
              <p className="text-xs font-semibold text-violet-600 dark:text-violet-400 uppercase tracking-wide mb-2">
                Your travel preferences
              </p>
              <div className="flex flex-wrap gap-2">
                {tripData.preferences.map((pref, i) => (
                  <span
                    key={i}
                    className="px-2.5 py-1 rounded-full text-xs border border-violet-200 dark:border-violet-700 bg-white dark:bg-slate-800 text-violet-700 dark:text-violet-300 shadow-sm"
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
        <div className="rounded-xl border border-emerald-200 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-900/20 p-5 mb-6">
          <div className="flex items-center justify-between gap-2 text-sm text-emerald-700 dark:text-emerald-300 mb-3">
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
                  className="text-xs text-emerald-600 hover:text-emerald-800 transition-colors cursor-pointer"
                >
                  <RefreshCw size={12} className="inline mr-1" />refresh
                </button>
                <button
                  type="button"
                  onClick={() => setNearMeDismissed(true)}
                  className="text-xs text-emerald-600 hover:text-emerald-800 transition-colors cursor-pointer"
                >
                  dismiss
                </button>
              </div>
            )}
          </div>
          {(nearMeText || tripData.near_me_response) && (
            <div className={`prose prose-sm max-w-none text-slate-700 dark:text-slate-300 ${nearMeActive ? 'streaming-cursor' : ''}`}>
              <ReactMarkdown remarkPlugins={[[remarkGfm, { singleTilde: false }]]}>{nearMeText || tripData.near_me_response}</ReactMarkdown>
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
        <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 p-8 mb-8 text-center shadow-sm">
          <p className="text-slate-600 dark:text-slate-300 text-sm font-medium">No itinerary yet.</p>
          <p className="text-slate-400 dark:text-slate-500 text-xs mt-1">Use "Continue Planning" above to finish building your trip.</p>
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
          ...(origin && (tripData.budget_breakdown?.flights || tripData.budget_breakdown?.travel) ? [{
            label: 'Search Flights',
            url: `https://www.google.com/travel/flights?q=flights+from+${enc(origin)}+to+${enc(dest)}+${start}+to+${end}`,
          }] : []),
          ...(tripData.hotel_suggestions?.length > 0
            ? tripData.hotel_suggestions.map(h => ({
                label: h.name,
                url: `https://www.booking.com/searchresults.html?ss=${enc(`${h.name} ${h.destination}`)}&checkin=${h.check_in}&checkout=${h.check_out}&group_adults=${tripData.number_of_travelers || 1}`,
              }))
            : [{
                label: 'Search Hotels',
                url: `https://www.booking.com/searchresults.html?ss=${enc(dest)}&checkin=${start}&checkout=${end}&group_adults=${tripData.number_of_travelers || 1}`,
              }]
          ),
          {
            label: 'Airbnb',
            url: `https://www.airbnb.com/s/${enc(dest)}/homes?checkin=${start}&checkout=${end}&adults=${tripData.number_of_travelers || 1}`,
          },
        ]

        return (
          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm p-4 mb-6">
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-3">Book Your Trip</p>
            <div className="flex flex-wrap gap-2">
              {links.map(({ label, url }) => (
                <a
                  key={label}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm
                    bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300
                    hover:border-indigo-300 dark:hover:border-indigo-600 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors shadow-sm"
                >
                  {label} <ExternalLink size={12} className="opacity-60" />
                </a>
              ))}
            </div>
          </div>
        )
      })()}

      {/* Rate limit / error banner */}
      {chatError && (
        <div className="rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 px-4 py-3 text-sm text-red-700 dark:text-red-400 flex items-center justify-between gap-2">
          <span>{chatError}</span>
          <button type="button" onClick={() => setChatError(null)} className="text-red-400 hover:text-red-600 shrink-0 text-base leading-none">✕</button>
        </div>
      )}

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
