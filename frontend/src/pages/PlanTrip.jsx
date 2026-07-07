import { useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Plane, Send, Save } from 'lucide-react'
import { toolLabel } from '@/lib/utils'
import { extractInfo, getSurprise, listTrips, reverseGeocode, saveTrip, updateTrip } from '@/lib/api'
import { invalidateTripCache } from '@/hooks/useTrip'
import { useSSEChat } from '@/hooks/useSSEChat'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'

const TRAVEL_STYLES = ['Backpacker', 'Budget', 'Mid-range', 'Luxury', 'Adventure', 'Cultural', 'Relaxation', 'Foodie']
const DIETARY = ['None', 'Vegetarian', 'Vegan', 'Halal', 'Kosher', 'Gluten-free', 'Dairy-free']
const CURRENCIES = ['EUR', 'USD', 'GBP', 'AUD', 'CAD', 'JPY', 'SGD', 'INR']

function Label({ children }) {
  return <label className="block text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">{children}</label>
}
function Input({ className = '', ...props }) {
  return (
    <input
      className={`w-full rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-slate-100
        px-3 py-2 text-sm placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-indigo-400
        focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-900 transition-all shadow-sm ${className}`}
      {...props}
    />
  )
}
function Select({ children, ...props }) {
  return (
    <select
      className="w-full rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-slate-100
        px-3 py-2 text-sm focus:outline-none focus:border-indigo-400 focus:ring-2
        focus:ring-indigo-100 dark:focus:ring-indigo-900 transition-all shadow-sm"
      {...props}
    >
      {children}
    </select>
  )
}

/** Returns true if the message looks like a complete day-by-day itinerary. */
function hasFullItinerary(text) {
  // Require BOTH Day 1 and Day 2 to be present — guards against false positives
  // where Marco mentions "Day 1" in passing while still asking clarifying questions.
  return /\bday\s+1\b/i.test(text) && /\bday\s+2\b/i.test(text)
}

/** Extract [OPTION: label] markers from Marco's response. */
function extractOptions(text) {
  return [...text.matchAll(/\[OPTION:\s*([^\]]+)\]/g)].map(m => m[1].trim())
}

/** Strip [OPTION: ...] markers from text before displaying (handles inline or own-line). */
function stripOptions(text) {
  return text.replace(/\[OPTION:[^\]]*\]/g, '').replace(/\n{3,}/g, '\n\n').trim()
}

export default function PlanTrip() {
  const navigate = useNavigate()
  const location = useLocation()
  const { streaming, toolStatus, send } = useSSEChat()

  // Pre-fill from navigation state when regenerating an existing trip
  const prefill = location.state?.prefill ?? {}
  // Resume an existing draft mid-conversation
  const resume  = location.state?.resume  ?? null

  const [form, setForm] = useState({
    destination:            (resume?.meta ?? prefill).destination            ?? '',
    destinationCountryCode: (resume?.meta ?? prefill).destinationCountryCode ?? '',
    origin:                 (resume?.meta ?? prefill).origin                 ?? '',
    startDate:              (resume?.meta ?? prefill).startDate              ?? '',
    endDate:                (resume?.meta ?? prefill).endDate                ?? '',
    budget:                 (resume?.meta ?? prefill).budget                 ?? '',
    currency:               (resume?.meta ?? prefill).currency               ?? 'EUR',
    numberOfTravelers:      (resume?.meta ?? prefill).numberOfTravelers      ?? 1,
    travelStyles: [],
    dietary: 'None',
    hasTwoWheelerLicence:  (resume?.meta ?? prefill).hasTwoWheelerLicence  ?? false,
    hasFourWheelerLicence: (resume?.meta ?? prefill).hasFourWheelerLicence ?? false,
    notes: '',
  })

  // Past trip preferences — loaded once, injected into planning prompts
  const [pastPreferences, setPastPreferences] = useState([])
  const [existingTrips, setExistingTrips]     = useState([])
  const [duplicateTrip, setDuplicateTrip]     = useState(null)
  useEffect(() => {
    listTrips()
      .then(trips => {
        setExistingTrips(trips)
        const prefs = trips
          .filter(t => t.preferences?.length > 0)
          .flatMap(t => t.preferences)
        // Deduplicate and cap to avoid bloating the prompt
        const unique = [...new Set(prefs)].slice(0, 10)
        setPastPreferences(unique)

        // Pre-fill origin from the most common home city across past trips
        if (!form.origin && !prefill.origin && !resume?.meta?.origin) {
          const origins = trips
            .filter(t => !t.is_member && t.origin)
            .map(t => t.origin.trim())
            .filter(Boolean)
          if (origins.length > 0) {
            const freq = origins.reduce((acc, o) => ({ ...acc, [o]: (acc[o] ?? 0) + 1 }), {})
            const top = Object.entries(freq).sort((a, b) => b[1] - a[1])[0][0]
            setField('origin', top)
          }
        }
      })
      .catch(() => {})
  }, [])

  // Conversation state — seed from resume if continuing an existing draft
  const [started, setStarted]           = useState(!!resume)
  const [messages, setMessages]         = useState(resume?.messages ?? [])
  const [streamingText, setStreamText]  = useState('')
  const [quickReplies, setQuickReplies] = useState([])
  const [input, setInput]               = useState('')
  const [saving, setSaving]             = useState(false)
  const [draftSaved, setDraftSaved]     = useState(!!resume)
  const [surpriseLoading, setSurpriseLoading] = useState(false)
  const [surpriseReason, setSurpriseReason]   = useState('')
  // True once Marco has written a full day-by-day itinerary — shows the Save button
  const [itineraryReady, setItineraryReady] = useState(false)
  // Planning screen state (new trip only — hidden for resume)
  const [stepHistory, setStepHistory]     = useState([])
  const [writingItinerary, setWritingItinerary] = useState(false)
  const [planningFailed, setPlanningFailed]     = useState(false)
  const [chatError, setChatError]               = useState(null)
  const responseRef      = useRef('')
  const draftIdRef       = useRef(resume?.tripId ?? null)
  const draftMetaRef     = useRef(resume?.meta   ?? null)
  const bookingDataRef   = useRef({})     // accumulated booking data (hotel suggestions, etc.)
  const bottomRef         = useRef(null)
  const inputRef          = useRef(null)
  const shouldScrollRef   = useRef(true)

  // Track whether user has scrolled away from the bottom
  useEffect(() => {
    const container = document.querySelector('main')
    if (!container) return
    const onScroll = () => {
      const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 120
      shouldScrollRef.current = nearBottom
    }
    container.addEventListener('scroll', onScroll, { passive: true })
    return () => container.removeEventListener('scroll', onScroll)
  }, [])

  // Auto-scroll only when already near the bottom
  useEffect(() => {
    if (shouldScrollRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, streamingText])

  // Focus input after Marco finishes
  useEffect(() => {
    if (!streaming && started && !saving) {
      inputRef.current?.focus()
    }
  }, [streaming, started, saving])

  function setField(key, val) {
    setForm(f => ({ ...f, [key]: val }))
  }
  function toggleStyle(style) {
    setForm(f => ({
      ...f,
      travelStyles: f.travelStyles.includes(style)
        ? f.travelStyles.filter(s => s !== style)
        : [...f.travelStyles, style],
    }))
  }

  /** Build minimal trip metadata from the form — used for draft saves without Haiku extraction. */
  function buildDraftMeta() {
    return {
      destination: form.destination,
      dates: `${form.startDate} to ${form.endDate}`,
      start_date: form.startDate,
      end_date: form.endDate,
      city: form.destination,
      country_code: form.destinationCountryCode,
      origin: form.origin,
      has_two_wheeler_licence:  form.hasTwoWheelerLicence,
      has_four_wheeler_licence: form.hasFourWheelerLicence,
      budget: parseFloat(form.budget) || 0,
      currency: form.currency,
      number_of_travelers: form.numberOfTravelers || 1,
      budget_breakdown: {},
      day_overrides: {},
    }
  }

  function buildPrompt() {
    const nights = form.startDate && form.endDate
      ? Math.round((new Date(form.endDate) - new Date(form.startDate)) / 86400000)
      : '?'
    const styles = form.travelStyles.join(', ') || 'flexible'
    const travelers = form.numberOfTravelers || 1
    return [
      `Plan my trip with these details:`,
      `Destination: ${form.destination}.`,
      `Travelling from: ${form.origin}.`,
      `Dates: ${form.startDate} to ${form.endDate} (${nights} nights).`,
      travelers > 1 ? `Traveling as a group of ${travelers} people.` : '',
      form.budget ? `Budget: ${form.budget} ${form.currency} per person.` : '',
      `Travel style: ${styles}.`,
      form.dietary !== 'None' ? `Dietary: ${form.dietary}.` : '',
      form.hasTwoWheelerLicence && form.hasFourWheelerLicence
        ? "Driving licences: two-wheeler and four-wheeler."
        : form.hasTwoWheelerLicence  ? "Driving licence: two-wheeler (bike/scooter)."
        : form.hasFourWheelerLicence ? "Driving licence: four-wheeler (car)."
        : '',
      form.notes ? `Extra notes: ${form.notes}.` : '',
      pastPreferences.length > 0
        ? `My past travel preferences: ${pastPreferences.join('; ')}.`
        : '',
    ].filter(Boolean).join(' ')
  }

  /** Core: send a message to Marco, stream response, handle auto-save on itinerary. */
  async function sendMessage(userContent, prevMessages = messages) {
    shouldScrollRef.current = true   // snap to bottom for the new turn
    const userMsg  = { role: 'user', content: userContent }
    const withUser = [...prevMessages, userMsg]
    setMessages(withUser)
    setQuickReplies([])        // clear option buttons on every new send
    responseRef.current = ''
    setStreamText('')
    // Reset planning screen state for each new planning turn
    if (!resume) {
      setStepHistory([])
      setWritingItinerary(false)
      setPlanningFailed(false)
    }
    setChatError(null)

    await send({
      messages: withUser,
      onToolCall: (name) => {
        if (!resume) {
          setStepHistory(prev => [...prev, name])
        }
      },
      onChunk: (chunk) => {
        if (!resume) setWritingItinerary(true)
        responseRef.current += chunk
        setStreamText(responseRef.current)
      },
      onBookingData: (data) => {
        bookingDataRef.current = { ...bookingDataRef.current, ...data }
      },
      onEvalCorrection: () => {
        // Discard the original response — only the corrected text that follows
        // will be saved as the assistant message and used as the itinerary.
        responseRef.current = ''
        setStreamText('')
      },
      onDone: () => {
        const assistantMsg = { role: 'assistant', content: responseRef.current }
        const finalMessages = [...withUser, assistantMsg]
        setMessages(finalMessages)
        setStreamText('')

        const gotItinerary = hasFullItinerary(responseRef.current)

        // Surface any [OPTION: ...] choices as quick-reply buttons
        setQuickReplies(extractOptions(responseRef.current))

        if (gotItinerary) {
          setItineraryReady(true)
        }

        // New trip: auto-navigate to trip view once itinerary is ready.
        // Resume/chat mode: keep the conversation going with Save button.
        if (gotItinerary && !resume) {
          saveAndNavigate(finalMessages)
          return
        }

        if (!gotItinerary && !resume) {
          // Marco asked a clarifying question — fall back to chat mode
          setPlanningFailed(true)
        }

        // Auto-persist as draft after every turn (fire-and-forget — onDone isn't
        // awaited by useSSEChat so we use .then() to keep intent clear).
        const meta = draftMetaRef.current ?? buildDraftMeta()
        const tripWithMessages = { ...meta, ...bookingDataRef.current, messages: finalMessages }

        if (!draftIdRef.current) {
          saveTrip(tripWithMessages)
            .then(id => {
              draftIdRef.current   = id
              draftMetaRef.current = meta
              setDraftSaved(true)
            })
            .catch(err => console.warn('Draft auto-save failed:', err))
        } else {
          updateTrip(draftIdRef.current, tripWithMessages)
            .catch(err => console.warn('Draft auto-update failed:', err))
        }
      },
      onError: msg => setChatError(msg),
    })
  }

  async function saveAndNavigate(msgs) {
    setSaving(true)
    try {
      const extracted = await extractInfo(msgs, form.currency)
      const base = draftMetaRef.current ?? buildDraftMeta()
      const finalStart = extracted.start_date || form.startDate
      const finalEnd   = extracted.end_date   || form.endDate
      const tripData = {
        ...base,
        ...bookingDataRef.current,
        destination:   form.destination || extracted.destination,
        dates:         `${finalStart} to ${finalEnd}`,
        start_date:    finalStart,
        end_date:      finalEnd,
        city:          extracted.city || form.destination,
        country_code:  extracted.country_code || form.destinationCountryCode || '',
        origin_country: extracted.origin_country || '',
        is_domestic:   extracted.is_domestic ?? null,
        budget:        parseFloat(form.budget) || 0,
        currency:      form.currency,
        number_of_travelers: form.numberOfTravelers || 1,
        budget_breakdown: extracted.budget_breakdown || {},
        days:          extracted.days?.length > 0 ? extracted.days : undefined,
        messages:      msgs,
        day_overrides: {},
      }
      if (draftIdRef.current) {
        await updateTrip(draftIdRef.current, tripData)
        invalidateTripCache(draftIdRef.current)
        navigate(`/trips/${draftIdRef.current}`)
      } else {
        const tripId = await saveTrip(tripData)
        navigate(`/trips/${tripId}`)
      }
    } catch {
      if (draftIdRef.current) {
        invalidateTripCache(draftIdRef.current)
        navigate(`/trips/${draftIdRef.current}`)
      } else {
        navigate('/')
      }
    }
  }

  // ── Surprise Me ─────────────────────────────────────────────────────────────
  async function handleSurprise() {
    if (!form.startDate || !form.endDate) {
      setSurpriseReason('__dates_missing__')
      return
    }
    setSurpriseLoading(true)
    setSurpriseReason('')
    try {
      // Resolve origin: use the form value if set, otherwise ask the browser
      let origin = form.origin
      if (!origin && navigator.geolocation) {
        origin = await new Promise(resolve => {
          navigator.geolocation.getCurrentPosition(
            async pos => {
              try {
                const { city } = await reverseGeocode(pos.coords.latitude, pos.coords.longitude)
                resolve(city || '')
              } catch { resolve('') }
            },
            () => resolve(''),
            { timeout: 5000 },
          )
        })
        if (origin) setField('origin', origin)
      }

      if (!origin) {
        setSurpriseReason('__origin_missing__')
        setSurpriseLoading(false)
        return
      }

      const pick = await getSurprise({
        origin,
        startDate:        form.startDate,
        endDate:          form.endDate,
        pastDestinations: existingTrips.map(t => t.destination).filter(Boolean),
        preferences:      pastPreferences,
        budget:           form.budget || null,
        currency:         form.currency,
        travelStyles:     form.travelStyles,
      })
      setForm(f => ({ ...f, destination: pick.destination }))
      setSurpriseReason(pick.reason)
    } catch {
      // silently ignore — user can try again
    } finally {
      setSurpriseLoading(false)
    }
  }

  // ── Form submit (first turn) ────────────────────────────────────────────────
  async function handleFormSubmit(e) {
    e.preventDefault()
    if (!form.destination || !form.origin || !form.startDate || !form.endDate) return

    const dest = form.destination.trim().toLowerCase()
    const dupe = existingTrips
      .filter(t => !t.is_member)
      .find(t => t.destination?.trim().toLowerCase() === dest)
    if (dupe) { setDuplicateTrip(dupe); return }

    setStarted(true)
    await sendMessage(buildPrompt(), [])
  }

  // ── Subsequent turns ────────────────────────────────────────────────────────
  async function handleChat(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || streaming || saving) return
    setInput('')
    await sendMessage(text)
  }

  // ── Render: form (before first send) ───────────────────────────────────────
  if (!started) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-md">
            <Plane className="text-white" size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-50">Plan a Trip</h1>
            <p className="text-slate-500 dark:text-slate-400 text-sm">Marco will research transport options, hotels & weather</p>
          </div>
        </div>

        {duplicateTrip && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
            <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl max-w-sm w-full p-6 border border-slate-200 dark:border-slate-700">
              <h2 className="text-base font-bold text-slate-900 dark:text-slate-50 mb-2">Trip already exists</h2>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-5">
                You already have a trip to <strong>{duplicateTrip.destination}</strong>
                {duplicateTrip.dates ? ` (${duplicateTrip.dates})` : ''}. Would you like to view it instead?
              </p>
              <div className="flex flex-col gap-2">
                <Button
                  variant="primary"
                  className="justify-center"
                  onClick={() => navigate(`/trips/${duplicateTrip.trip_id}`)}
                >
                  View Existing Trip
                </Button>
                <Button
                  variant="secondary"
                  className="justify-center"
                  onClick={() => {
                    setDuplicateTrip(null)
                    setStarted(true)
                    sendMessage(buildPrompt(), [])
                  }}
                >
                  Create Anyway
                </Button>
                <button
                  type="button"
                  onClick={() => setDuplicateTrip(null)}
                  className="text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 text-center py-1"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        <form onSubmit={handleFormSubmit} className="space-y-5">
          {surpriseReason === '__dates_missing__' ? (
            <div className="flex items-start gap-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 px-4 py-3 text-sm text-amber-700 dark:text-amber-400">
              <span className="shrink-0 text-base leading-snug">📅</span>
              <span className="flex-1">Pick your travel dates first — Marco will find the best destination for them.</span>
              <button type="button" onClick={() => setSurpriseReason('')} className="shrink-0 text-amber-400 hover:text-amber-600 dark:hover:text-amber-300 leading-none text-base">✕</button>
            </div>
          ) : surpriseReason === '__origin_missing__' ? (
            <div className="flex items-start gap-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 px-4 py-3 text-sm text-amber-700 dark:text-amber-400">
              <span className="shrink-0 text-base leading-snug">📍</span>
              <span className="flex-1">Fill in where you're travelling from — Marco needs your location to suggest nearby destinations.</span>
              <button type="button" onClick={() => setSurpriseReason('')} className="shrink-0 text-amber-400 hover:text-amber-600 dark:hover:text-amber-300 leading-none text-base">✕</button>
            </div>
          ) : surpriseReason ? (
            <div className="flex items-start gap-2 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 border border-indigo-200 dark:border-indigo-700 px-4 py-3 text-sm text-indigo-700 dark:text-indigo-300">
              <span className="shrink-0 text-base leading-snug">✨</span>
              <span className="flex-1">{surpriseReason}</span>
              <button type="button" onClick={() => setSurpriseReason('')} className="shrink-0 text-indigo-400 hover:text-indigo-600 dark:hover:text-indigo-200 leading-none text-base">✕</button>
            </div>
          ) : null}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label>Travelling from *</Label>
              <Input
                placeholder="e.g. London"
                value={form.origin}
                onChange={e => setField('origin', e.target.value)}
                required
              />
            </div>
            <div>
              <Label>Destination *</Label>
              <Input
                placeholder="e.g. Tokyo, Japan"
                value={form.destination}
                onChange={e => setForm(f => ({ ...f, destination: e.target.value }))}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label>Start date *</Label>
              <Input
                type="date"
                value={form.startDate}
                min={new Date().toISOString().split('T')[0]}
                onChange={e => {
                  const newStart = e.target.value
                  // If end date is now before the new start, clear it
                  setForm(f => ({
                    ...f,
                    startDate: newStart,
                    endDate: f.endDate && f.endDate <= newStart ? '' : f.endDate,
                  }))
                }}
                required
              />
            </div>
            <div>
              <Label>End date *</Label>
              <Input
                type="date"
                value={form.endDate}
                min={form.startDate || new Date().toISOString().split('T')[0]}
                onChange={e => setField('endDate', e.target.value)}
                required
              />
            </div>
          </div>

          <button
            type="button"
            onClick={handleSurprise}
            disabled={surpriseLoading}
            className="w-full flex items-center justify-center gap-2 rounded-lg border-2 border-dashed border-indigo-300 dark:border-indigo-700
              text-indigo-600 dark:text-indigo-400 text-sm font-medium py-2.5
              hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-900/20
              disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {surpriseLoading
              ? <><Spinner className="w-4 h-4" /> Marco is picking the best destination…</>
              : <>✨ Surprise me — Marco picks the destination</>}
          </button>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label>Budget per person</Label>
              <Input
                type="number"
                min="0"
                placeholder="e.g. 2000"
                value={form.budget}
                onChange={e => setField('budget', e.target.value)}
              />
            </div>
            <div>
              <Label>Currency</Label>
              <Select value={form.currency} onChange={e => setField('currency', e.target.value)}>
                {CURRENCIES.map(c => <option key={c}>{c}</option>)}
              </Select>
            </div>
            <div>
              <Label>Travelers</Label>
              <Input
                type="number"
                min="1"
                max="50"
                placeholder="e.g. 1"
                value={form.numberOfTravelers}
                onChange={e => {
                  const val = e.target.value;
                  if (val === '') { setField('numberOfTravelers', ''); return; }
                  const n = parseInt(val);
                  if (!isNaN(n)) setField('numberOfTravelers', Math.max(1, n));
                }}
                onBlur={() => {
                  if (!form.numberOfTravelers || form.numberOfTravelers < 1)
                    setField('numberOfTravelers', 1);
                }}
              />
            </div>
          </div>

          <div>
            <Label>Travel style</Label>
            <div className="flex flex-wrap gap-2">
              {TRAVEL_STYLES.map(style => (
                <button
                  type="button"
                  key={style}
                  onClick={() => toggleStyle(style)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors cursor-pointer
                    ${form.travelStyles.includes(style)
                      ? 'bg-indigo-600 border-indigo-500 text-white shadow-sm'
                      : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:border-indigo-300 dark:hover:border-indigo-600 hover:text-indigo-600 dark:hover:text-indigo-400 shadow-sm'}`}
                >
                  {style}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Dietary needs</Label>
              <Select value={form.dietary} onChange={e => setField('dietary', e.target.value)}>
                {DIETARY.map(d => <option key={d}>{d}</option>)}
              </Select>
            </div>
            <div>
              <Label>Driving licence</Label>
              <div className="flex flex-col gap-1.5">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    className="w-4 h-4 rounded accent-indigo-500"
                    checked={form.hasTwoWheelerLicence}
                    onChange={e => setField('hasTwoWheelerLicence', e.target.checked)}
                  />
                  <span className="text-sm text-slate-600 dark:text-slate-300">Two-wheeler (bike / scooter)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    className="w-4 h-4 rounded accent-indigo-500"
                    checked={form.hasFourWheelerLicence}
                    onChange={e => setField('hasFourWheelerLicence', e.target.checked)}
                  />
                  <span className="text-sm text-slate-600 dark:text-slate-300">Four-wheeler (car)</span>
                </label>
              </div>
            </div>
          </div>

          <div>
            <Label>Extra notes</Label>
            <textarea
              rows={3}
              placeholder="Accessibility needs, must-see places, avoid crowds…"
              value={form.notes}
              onChange={e => setField('notes', e.target.value)}
              className="w-full rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-slate-100
                px-3 py-2 text-sm placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-indigo-400
                focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-900 transition-all shadow-sm resize-none"
            />
          </div>

          <Button type="submit" variant="primary" size="lg" className="w-full justify-center">
            <Plane size={16} /> Generate My Trip Plan
          </Button>
        </form>
      </div>
    )
  }

  // ── Render: planning screen (new trip — handles loading, clarification, saving) ─
  if (started && !resume) {
    const steps = stepHistory.map((name, i) => {
      const isLast = i === stepHistory.length - 1
      const isDone = !isLast || writingItinerary || !streaming
      return { name, isDone }
    })
    const lastMarcoMsg = [...messages].reverse().find(m => m.role === 'assistant')
    const showLoader = !planningFailed && !saving && (streaming || steps.length > 0 || writingItinerary)
    const showClarify = planningFailed && !streaming && !saving

    return (
      <div className="max-w-lg mx-auto px-4 sm:px-6 py-8 sm:py-10 flex flex-col min-h-[calc(100vh-4rem)]">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-md">
            <Plane className="text-white" size={18} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-50">{form.destination}</h1>
            <p className="text-slate-500 dark:text-slate-400 text-xs">
              {form.startDate} → {form.endDate}
              {form.budget ? ` · ${form.budget} ${form.currency}/person` : ''}
              {form.numberOfTravelers > 1 ? ` · ${form.numberOfTravelers} travelers` : ''}
            </p>
          </div>
        </div>

        {/* Rate limit / error banner */}
        {chatError && (
          <div className="mb-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 px-4 py-3 text-sm text-red-700 dark:text-red-400 flex items-center justify-between gap-2">
            <span>{chatError}</span>
            <button type="button" onClick={() => setChatError(null)} className="text-red-400 hover:text-red-600 shrink-0 text-base leading-none">✕</button>
          </div>
        )}

        {/* Tool-step loader */}
        {showLoader && (
          <div className="flex-1 flex flex-col justify-center">
            <div className="space-y-3 max-w-xs">
              {steps.length === 0 && streaming && (
                <div className="flex items-center gap-3 text-sm text-indigo-600 bg-indigo-50 rounded-lg px-3 py-2">
                  <Spinner className="w-4 h-4 shrink-0" />
                  <span>Marco is thinking…</span>
                </div>
              )}
              {steps.map(({ name, isDone }, i) => (
                <div
                  key={i}
                  className={`flex items-center gap-3 text-sm transition-colors px-3 py-2 rounded-lg ${
                    isDone ? 'text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800' : 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30'
                  }`}
                >
                  {isDone
                    ? <span className="text-emerald-500 w-4 shrink-0 text-base leading-none">✓</span>
                    : <Spinner className="w-4 h-4 shrink-0" />}
                  <span>{toolLabel(name)}</span>
                </div>
              ))}
              {writingItinerary && (
                <div className={`flex items-center gap-3 text-sm px-3 py-2 rounded-lg ${streaming ? 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30' : 'text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800'}`}>
                  {streaming
                    ? <Spinner className="w-4 h-4 shrink-0" />
                    : <span className="text-emerald-500 w-4 shrink-0 text-base leading-none">✓</span>}
                  <span>✍️ Writing your itinerary…</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Saving */}
        {saving && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <Spinner className="w-6 h-6 text-indigo-400" />
            <p className="text-sm text-slate-400 dark:text-slate-500">Saving your trip…</p>
          </div>
        )}

        {/* Clarification — Marco needs input before generating the plan */}
        {showClarify && lastMarcoMsg && (
          <div className="flex-1 flex flex-col gap-4 overflow-y-auto">
            <div className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center
                text-white text-xs font-bold shrink-0 mt-0.5 shadow-sm">M</div>
              <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl rounded-tl-sm shadow-sm
                px-4 py-3 text-sm text-slate-700 dark:text-slate-200 flex-1">
                <div className="prose prose-sm max-w-none
                  prose-p:my-1 prose-ul:my-1 prose-li:my-0.5">
                  <ReactMarkdown remarkPlugins={[[remarkGfm, { singleTilde: false }]]}>{stripOptions(lastMarcoMsg.content)}</ReactMarkdown>
                </div>
              </div>
            </div>

            {quickReplies.length > 0 && (
              <div className="flex flex-wrap gap-2 pl-10">
                {quickReplies.map((opt, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => sendMessage(opt)}
                    className="px-4 py-2 rounded-full text-sm border border-indigo-200 dark:border-indigo-700
                      bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/50
                      hover:border-indigo-300 dark:hover:border-indigo-600 transition-colors cursor-pointer"
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Input — visible when Marco is waiting for a reply (clarification or mid-stream) */}
        {!saving && (showClarify || (streaming && planningFailed)) && (
          <form onSubmit={handleChat} className="flex gap-2 mt-4 sticky bottom-4">
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={streaming}
              placeholder={streaming ? 'Marco is thinking…' : 'Reply to Marco…'}
              className="flex-1 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-slate-100
                px-4 py-3 text-sm placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-indigo-400
                focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-900 transition-all shadow-sm disabled:opacity-50"
            />
            <Button type="submit" variant="primary" disabled={streaming || !input.trim()} className="px-4">
              <Send size={16} />
            </Button>
          </form>
        )}
      </div>
    )
  }

  // ── Render: chat (resume mode only) ────────────────────────────────────────
  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 sm:py-10 flex flex-col min-h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center shadow-md">
          <Plane className="text-white" size={16} />
        </div>
        <div className="flex-1">
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-50">
            Planning: {form.destination}
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-xs">{form.startDate} → {form.endDate} · {form.budget} {form.currency}</p>
        </div>
        {draftSaved && (
          <span className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1">
            <span className="text-emerald-500">✓</span> Draft saved
          </span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 mb-6">
        {messages.map((msg, i) => (
          <div key={i} className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            {/* Avatar */}
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center
                text-white text-xs font-bold shrink-0 mt-0.5 shadow-sm">
                M
              </div>
            )}

            {/* Bubble */}
            <div className={`rounded-2xl px-4 py-3 text-sm max-w-[88%] ${
              msg.role === 'user'
                ? 'bg-indigo-600 text-white rounded-tr-sm shadow-sm'
                : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 rounded-tl-sm shadow-sm'
            }`}>
              {msg.role === 'assistant'
                ? (
                  <div className="prose prose-sm max-w-none
                    prose-p:my-1 prose-ul:my-1 prose-li:my-0.5">
                    <ReactMarkdown remarkPlugins={[[remarkGfm, { singleTilde: false }]]}>{stripOptions(msg.content)}</ReactMarkdown>
                  </div>
                )
                : msg.content
              }
            </div>
          </div>
        ))}

        {/* Quick-reply option buttons — shown after Marco's last message */}
        {quickReplies.length > 0 && !streaming && (
          <div className="flex flex-wrap gap-2 pl-10">
            {quickReplies.map((opt, i) => (
              <button
                key={i}
                type="button"
                onClick={() => sendMessage(opt)}
                className="px-4 py-2 rounded-full text-sm border border-indigo-200
                  bg-indigo-50 text-indigo-700 hover:bg-indigo-100
                  hover:border-indigo-300 transition-colors cursor-pointer"
              >
                {opt}
              </button>
            ))}
          </div>
        )}

        {/* Streaming bubble */}
        {streamingText && (
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center
              text-white text-xs font-bold shrink-0 mt-0.5 shadow-sm">
              M
            </div>
            <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl rounded-tl-sm shadow-sm
              px-4 py-3 text-sm max-w-[88%] text-slate-700 dark:text-slate-200">
              <div className="prose prose-sm max-w-none
                prose-p:my-1 prose-ul:my-1 prose-li:my-0.5 streaming-cursor">
                <ReactMarkdown remarkPlugins={[[remarkGfm, { singleTilde: false }]]}>{stripOptions(streamingText)}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {/* Tool status */}
        {toolStatus && (
          <div className="flex items-center gap-2 text-xs text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30
            border border-indigo-200 dark:border-indigo-700 rounded-lg px-3 py-2 w-fit">
            <Spinner className="w-3 h-3" /> {toolStatus}
          </div>
        )}

        {/* Thinking (no text yet) */}
        {streaming && !streamingText && !toolStatus && (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center
              text-white text-xs font-bold shrink-0 shadow-sm">M</div>
            <span className="animate-pulse text-slate-500 dark:text-slate-400">Marco is thinking…</span>
          </div>
        )}

        {/* Saving */}
        {saving && (
          <div className="flex items-center gap-2 text-xs text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30
            border border-indigo-200 dark:border-indigo-700 rounded-lg px-3 py-2 w-fit">
            <Spinner className="w-3 h-3" /> Saving your trip…
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Save Trip banner — appears once Marco has written a full itinerary */}
      {itineraryReady && !saving && (
        <div className="sticky bottom-20 mb-3">
          <button
            type="button"
            onClick={() => saveAndNavigate(messages)}
            className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500
              text-white font-semibold text-sm transition-colors
              flex items-center justify-center gap-2 shadow-lg shadow-indigo-200"
          >
            <Save size={16} /> Save Trip &amp; Open Itinerary
          </button>
          <p className="text-xs text-slate-500 dark:text-slate-400 text-center mt-1.5">
            Happy with the plan? Save it — or keep chatting to tweak things first.
          </p>
        </div>
      )}

      {/* Input — stays at bottom, hidden while saving */}
      {!saving && (
        <form onSubmit={handleChat} className="flex gap-2 sticky bottom-4">
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={streaming}
            placeholder={streaming ? 'Marco is typing…' : 'Reply to Marco…'}
            className="flex-1 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-slate-100
              px-4 py-3 text-sm placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-indigo-400
              focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-900 transition-all shadow-sm disabled:opacity-50"
          />
          <Button
            type="submit"
            variant="primary"
            disabled={streaming || !input.trim()}
            className="px-4"
          >
            <Send size={16} />
          </Button>
        </form>
      )}
    </div>
  )
}
