import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { Plane } from 'lucide-react'
import { extractInfo, saveTrip } from '@/lib/api'
import { useSSEChat } from '@/hooks/useSSEChat'
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

export default function PlanTrip() {
  const navigate = useNavigate()
  const { streaming, toolStatus, send } = useSSEChat()

  const [form, setForm] = useState({
    destination: '',
    origin: '',
    startDate: '',
    endDate: '',
    budget: '',
    currency: 'EUR',
    travelStyles: [],
    dietary: 'None',
    hasLicence: false,
    notes: '',
  })

  const [response, setResponse] = useState('')
  const [started, setStarted]   = useState(false)
  const responseRef = useRef('')
  const abortRef    = useRef(null)

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
      form.hasLicence ? "I have a driver's licence." : '',
      form.notes ? `Extra notes: ${form.notes}` : '',
    ].filter(Boolean).join(' ')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.destination || !form.startDate || !form.endDate) return

    const userMsg = buildPrompt()
    const messages = [{ role: 'user', content: userMsg }]
    responseRef.current = ''
    setResponse('')
    setStarted(true)

    const finalMessages = [...messages]

    await send({
      messages,
      onChunk: (chunk) => {
        responseRef.current += chunk
        setResponse(responseRef.current)
      },
      onDone: async () => {
        const assistantContent = responseRef.current
        finalMessages.push({ role: 'assistant', content: assistantContent })

        // Extract trip metadata + save
        const currency = form.currency
        const extracted = await extractInfo(finalMessages, currency)

        const tripData = {
          destination: extracted.destination || form.destination,
          dates: `${form.startDate} to ${form.endDate}`,
          start_date: extracted.start_date || form.startDate,
          end_date: extracted.end_date || form.endDate,
          city: extracted.city || form.destination,
          country_code: extracted.country_code || '',
          budget: parseFloat(form.budget) || 0,
          currency,
          budget_breakdown: extracted.budget_breakdown || {},
          messages: finalMessages,
          day_overrides: {},
        }

        try {
          const tripId = await saveTrip(tripData)
          navigate(`/trips/${tripId}`)
        } catch {
          // still navigate with state if save fails
          navigate('/')
        }
      },
    })
  }

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

      {/* Form */}
      {!started && (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Destination *</Label>
              <Input
                placeholder="e.g. Tokyo, Japan"
                value={form.destination}
                onChange={e => setField('destination', e.target.value)}
                required
              />
            </div>
            <div>
              <Label>Flying from *</Label>
              <Input
                placeholder="e.g. London"
                value={form.origin}
                onChange={e => setField('origin', e.target.value)}
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
                onChange={e => setField('startDate', e.target.value)}
                required
              />
            </div>
            <div>
              <Label>End date *</Label>
              <Input
                type="date"
                value={form.endDate}
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
            <div className="flex items-end pb-0.5">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded accent-indigo-500"
                  checked={form.hasLicence}
                  onChange={e => setField('hasLicence', e.target.checked)}
                />
                <span className="text-sm text-slate-300">I have a driver's licence</span>
              </label>
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
      )}

      {/* Streaming response */}
      {started && (
        <div>
          {toolStatus && (
            <div className="flex items-center gap-2 text-sm text-indigo-300 mb-4 bg-indigo-900/20 border border-indigo-800/40 rounded-lg px-4 py-2">
              <Spinner className="w-4 h-4" />
              {toolStatus}
            </div>
          )}

          {streaming && !response && !toolStatus && (
            <div className="flex items-center gap-2 text-sm text-slate-400 mb-4">
              <Spinner className="w-4 h-4" /> Marco is thinking…
            </div>
          )}

          <div className={`prose max-w-none text-sm leading-relaxed ${streaming ? 'streaming-cursor' : ''}`}>
            <ReactMarkdown>{response}</ReactMarkdown>
          </div>

          {streaming && (
            <p className="text-xs text-slate-500 mt-4">
              Saving your trip when Marco is done…
            </p>
          )}
        </div>
      )}
    </div>
  )
}
