import { useEffect, useRef, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { Plane, Send, Save } from 'lucide-react'
import { extractInfo, listTrips, saveTrip, updateTrip } from '@/lib/api'
import { useSSEChat } from '@/hooks/useSSEChat'
import { AutocompleteInput } from '@/components/AutocompleteInput'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'

const TRAVEL_STYLES = ['Backpacker', 'Budget', 'Mid-range', 'Luxury', 'Adventure', 'Cultural', 'Relaxation', 'Foodie']
const DIETARY = ['None', 'Vegetarian', 'Vegan', 'Halal', 'Kosher', 'Gluten-free', 'Dairy-free']
const CURRENCIES = ['EUR', 'USD', 'GBP', 'AUD', 'CAD', 'JPY', 'SGD', 'INR']

function Label({ children }) {
  return <label className="block text-sm font-medium text-slate-300 mb-1">{children}</label>
}
function Input({ className = '', ...props }) {
  return (
    <input
      className={`w-full rounded-lg bg-[#22263a] border border-[#2e3248] text-slate-200
        px-3 py-2 text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500
        transition-colors ${className}`}
      {...props}
    />
  )
}
function Select({ children, ...props }) {
  return (
    <select
      className="w-full rounded-lg bg-[#22263a] border border-[#2e3248] text-slate-200
        px-3 py-2 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
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

  const [form, setForm] = useState({
    destination:            prefill.destination            ?? '',
    destinationCountryCode: prefill.destinationCountryCode ?? '',
    origin:                 prefill.origin                 ?? '',
    startDate:              prefill.startDate              ?? '',
    endDate:                prefill.endDate                ?? '',
    budget:                 prefill.budget                 ?? '',
    currency:               prefill.currency               ?? 'EUR',
    travelStyles: [],
    dietary: 'None',
    hasTwoWheelerLicence:  prefill.hasTwoWheelerLicence  ?? false,
    hasFourWheelerLicence: prefill.hasFourWheelerLicence ?? false,
    notes: '',
  })

  // Past trip preferences — loaded once, injected into planning prompts
  const [pastPreferences, setPastPreferences] = useState([])
  useEffect(() => {
    listTrips()
      .then(trips => {
        const prefs = trips
          .filter(t => t.preferences?.length > 0)
          .flatMap(t => t.preferences)
        // Deduplicate and cap to avoid bloating the prompt
        const unique = [...new Set(prefs)].slice(0, 10)
        setPastPreferences(unique)
      })
      .catch(() => {})
  }, [])

  // Conversation state
  const [started, setStarted]           = useState(false)
  const [messages, setMessages]         = useState([])
  const [streamingText, setStreamText]  = useState('')
  const [quickReplies, setQuickReplies] = useState([])
  const [input, setInput]               = useState('')
  const [saving, setSaving]             = useState(false)
  const [draftSaved, setDraftSaved]     = useState(false)
  // True once Marco has written a full day-by-day itinerary — shows the Save button
  const [itineraryReady, setItineraryReady] = useState(false)
  const responseRef      = useRef('')
  const draftIdRef       = useRef(null)   // persists across renders without causing re-renders
  const draftMetaRef     = useRef(null)   // base trip metadata for updates
  const bookingDataRef   = useRef({})     // accumulated booking data (hotel suggestions, etc.)
  const bottomRef    = useRef(null)
  const inputRef     = useRef(null)

  // Auto-scroll to bottom as Marco types
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
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
      budget_breakdown: {},
      day_overrides: {},
    }
  }

  function buildPrompt() {
    const nights = form.startDate && form.endDate
      ? Math.round((new Date(form.endDate) - new Date(form.startDate)) / 86400000)
      : '?'
    const styles = form.travelStyles.join(', ') || 'flexible'
    return [
      `I want to plan a trip to ${form.destination} from ${form.origin}.`,
      `Dates: ${form.startDate} to ${form.endDate} (${nights} nights).`,
      `Budget: ${form.budget} ${form.currency}.`,
      `Travel style: ${styles}.`,
      form.dietary !== 'None' ? `Dietary: ${form.dietary}.` : '',
      form.hasTwoWheelerLicence && form.hasFourWheelerLicence
        ? "I have both a two-wheeler and a four-wheeler driving licence."
        : form.hasTwoWheelerLicence  ? "I have a two-wheeler (bike/scooter) driving licence."
        : form.hasFourWheelerLicence ? "I have a four-wheeler (car) driving licence."
        : '',
      form.notes ? `Extra notes: ${form.notes}` : '',
      pastPreferences.length > 0
        ? `Based on my past trips, here are my known travel preferences: ${pastPreferences.join('; ')}.`
        : '',
    ].filter(Boolean).join(' ')
  }

  /** Core: send a message to Marco, stream response, handle auto-save on itinerary. */
  async function sendMessage(userContent, prevMessages = messages) {
    const userMsg  = { role: 'user', content: userContent }
    const withUser = [...prevMessages, userMsg]
    setMessages(withUser)
    setQuickReplies([])        // clear option buttons on every new send
    responseRef.current = ''
    setStreamText('')

    await send({
      messages: withUser,
      onChunk: (chunk) => {
        responseRef.current += chunk
        setStreamText(responseRef.current)
      },
      onBookingData: (data) => {
        bookingDataRef.current = { ...bookingDataRef.current, ...data }
      },
      onDone: () => {
        const assistantMsg = { role: 'assistant', content: responseRef.current }
        const finalMessages = [...withUser, assistantMsg]
        setMessages(finalMessages)
        setStreamText('')

        // Surface any [OPTION: ...] choices as quick-reply buttons
        setQuickReplies(extractOptions(responseRef.current))

        // Show the Save button once Marco has produced a full day-by-day itinerary.
        if (hasFullItinerary(responseRef.current)) {
          setItineraryReady(true)
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
    })
  }

  async function saveAndNavigate(msgs) {
    setSaving(true)
    try {
      const extracted = await extractInfo(msgs, form.currency)
      const base = draftMetaRef.current ?? buildDraftMeta()
      const tripData = {
        ...base,
        ...bookingDataRef.current,
        destination: extracted.destination || form.destination,
        dates: `${form.startDate} to ${form.endDate}`,
        start_date: extracted.start_date || form.startDate,
        end_date: extracted.end_date || form.endDate,
        city: extracted.city || form.destination,
        country_code: extracted.country_code || form.destinationCountryCode || '',
        budget: parseFloat(form.budget) || 0,
        currency: form.currency,
        budget_breakdown: extracted.budget_breakdown || {},
        messages: msgs,
        day_overrides: {},
      }
      if (draftIdRef.current) {
        // Update the existing draft with full extracted metadata, then navigate to it
        await updateTrip(draftIdRef.current, tripData)
        navigate(`/trips/${draftIdRef.current}`)
      } else {
        const tripId = await saveTrip(tripData)
        navigate(`/trips/${tripId}`)
      }
    } catch {
      // If extraction/update failed, still navigate to the draft if we have one
      if (draftIdRef.current) navigate(`/trips/${draftIdRef.current}`)
      else navigate('/')
    }
  }

  // ── Form submit (first turn) ────────────────────────────────────────────────
  async function handleFormSubmit(e) {
    e.preventDefault()
    if (!form.destination || !form.startDate || !form.endDate) return
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
      <div className="max-w-2xl mx-auto px-6 py-10">
        <div className="flex items-center gap-3 mb-8">
          <div className="p-2 rounded-xl bg-indigo-900/40 border border-indigo-700/40">
            <Plane className="text-indigo-400" size={22} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Plan a Trip</h1>
            <p className="text-slate-400 text-sm">Marco will search live flights, hotels & weather</p>
          </div>
        </div>

        <form onSubmit={handleFormSubmit} className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Destination *</Label>
              <AutocompleteInput
                placeholder="e.g. Tokyo, Japan"
                value={form.destination}
                onChange={val => setForm(f => ({ ...f, destination: val, destinationCountryCode: '' }))}
                onSelect={s => setForm(f => ({ ...f, destination: s.name, destinationCountryCode: s.countryCode }))}
                required
              />
            </div>
            <div>
              <Label>Flying from *</Label>
              <AutocompleteInput
                placeholder="e.g. London"
                value={form.origin}
                onChange={val => setField('origin', val)}
                onSelect={s => setField('origin', s.name)}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
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

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Budget</Label>
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
                      ? 'bg-indigo-600 border-indigo-500 text-white'
                      : 'bg-[#22263a] border-[#2e3248] text-slate-400 hover:border-indigo-600/50'}`}
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
                  <span className="text-sm text-slate-300">Two-wheeler (bike / scooter)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    className="w-4 h-4 rounded accent-indigo-500"
                    checked={form.hasFourWheelerLicence}
                    onChange={e => setField('hasFourWheelerLicence', e.target.checked)}
                  />
                  <span className="text-sm text-slate-300">Four-wheeler (car)</span>
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
              className="w-full rounded-lg bg-[#22263a] border border-[#2e3248] text-slate-200
                px-3 py-2 text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500
                transition-colors resize-none"
            />
          </div>

          <Button type="submit" variant="primary" size="lg" className="w-full justify-center">
            <Plane size={16} /> Generate My Trip Plan
          </Button>
        </form>
      </div>
    )
  }

  // ── Render: chat (after first send) ────────────────────────────────────────
  return (
    <div className="max-w-2xl mx-auto px-6 py-10 flex flex-col min-h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 rounded-xl bg-indigo-900/40 border border-indigo-700/40">
          <Plane className="text-indigo-400" size={18} />
        </div>
        <div className="flex-1">
          <h1 className="text-lg font-bold text-slate-100">
            Planning: {form.destination}
          </h1>
          <p className="text-slate-500 text-xs">{form.startDate} → {form.endDate} · {form.budget} {form.currency}</p>
        </div>
        {draftSaved && (
          <span className="text-xs text-slate-500 flex items-center gap-1">
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
                text-white text-xs font-bold shrink-0 mt-0.5">
                M
              </div>
            )}

            {/* Bubble */}
            <div className={`rounded-2xl px-4 py-3 text-sm max-w-[88%] ${
              msg.role === 'user'
                ? 'bg-indigo-600 text-white rounded-tr-sm'
                : 'bg-[#1a1d27] border border-[#2e3248] text-slate-200 rounded-tl-sm'
            }`}>
              {msg.role === 'assistant'
                ? (
                  <div className="prose prose-sm prose-invert max-w-none
                    prose-p:my-1 prose-ul:my-1 prose-li:my-0.5 prose-headings:text-slate-100">
                    <ReactMarkdown>{stripOptions(msg.content)}</ReactMarkdown>
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
                className="px-4 py-2 rounded-full text-sm border border-indigo-600/60
                  bg-indigo-900/20 text-indigo-300 hover:bg-indigo-900/40
                  hover:border-indigo-500 transition-colors cursor-pointer"
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
              text-white text-xs font-bold shrink-0 mt-0.5">
              M
            </div>
            <div className="bg-[#1a1d27] border border-[#2e3248] rounded-2xl rounded-tl-sm
              px-4 py-3 text-sm max-w-[88%] text-slate-200">
              <div className="prose prose-sm prose-invert max-w-none
                prose-p:my-1 prose-ul:my-1 prose-li:my-0.5 prose-headings:text-slate-100 streaming-cursor">
                <ReactMarkdown>{stripOptions(streamingText)}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {/* Tool status */}
        {toolStatus && (
          <div className="flex items-center gap-2 text-xs text-indigo-300 bg-indigo-900/20
            border border-indigo-800/40 rounded-lg px-3 py-2 w-fit">
            <Spinner className="w-3 h-3" /> {toolStatus}
          </div>
        )}

        {/* Thinking (no text yet) */}
        {streaming && !streamingText && !toolStatus && (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center
              text-white text-xs font-bold shrink-0">M</div>
            <span className="animate-pulse">Marco is thinking…</span>
          </div>
        )}

        {/* Saving */}
        {saving && (
          <div className="flex items-center gap-2 text-xs text-indigo-300 bg-indigo-900/20
            border border-indigo-800/40 rounded-lg px-3 py-2 w-fit">
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
              flex items-center justify-center gap-2 shadow-lg shadow-indigo-900/40"
          >
            <Save size={16} /> Save Trip &amp; Open Itinerary
          </button>
          <p className="text-xs text-slate-500 text-center mt-1.5">
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
            className="flex-1 rounded-xl bg-[#22263a] border border-[#2e3248] text-slate-200
              px-4 py-3 text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500
              transition-colors disabled:opacity-50"
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
