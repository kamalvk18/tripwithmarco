import { useRef, useState, useEffect, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, ChevronDown, MessageCircle, LocateFixed } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'
import { useNearMe } from '@/hooks/useNearMe'
import { Spinner } from '@/components/ui/Spinner'
import { cn } from '@/lib/utils'

const NEAR_ME_TTL_MS = 30 * 60 * 1000  // 30 minutes

function stripOptions(text) {
  return text.replace(/\[OPTION:[^\]]*\]/g, '').replace(/\n{3,}/g, '\n\n').trim()
}

function extractOptions(text) {
  return [...text.matchAll(/\[OPTION:\s*([^\]]+)\]/g)].map(m => m[1].trim())
}

function Bubble({ role, content, isStreaming }) {
  const isMarco = role === 'assistant'
  const displayContent = isMarco ? stripOptions(content) : content
  return (
    <div className={cn('flex gap-3', isMarco ? '' : 'justify-end')}>
      {isMarco && (
        <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white shrink-0 mt-0.5 shadow-sm">
          M
        </div>
      )}
      <div
        className={cn(
          'rounded-xl px-4 py-3 text-sm max-w-[85%]',
          isMarco
            ? 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 shadow-sm'
            : 'bg-indigo-600 text-white shadow-sm',
          isStreaming && isMarco ? 'streaming-cursor' : '',
        )}
      >
        {isMarco ? (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[[remarkGfm, { singleTilde: false }]]}>{displayContent}</ReactMarkdown>
          </div>
        ) : (
          <p className="whitespace-pre-wrap">{displayContent}</p>
        )}
      </div>
    </div>
  )
}

export function ChatPanel({ messages, tripData, companion = false, weatherText = null, onSave }) {
  const { streaming, toolStatus, send } = useSSEChat()
  const { locate, locating } = useNearMe()
  const [expanded, setExpanded]           = useState(false)
  const [input, setInput]                 = useState('')
  const [streamingText, setStreamingText] = useState('')
  const [quickReplies, setQuickReplies]   = useState([])
  const [chatError, setChatError]         = useState(null)
  const [nearMeLastAt, setNearMeLastAt]   = useState(null)
  const bottomRef       = useRef(null)
  const inputRef        = useRef(null)
  const scrollRef       = useRef(null)
  const shouldScrollRef = useRef(true)

  // Persisted follow-up history = everything after the initial planning
  // exchange (form prompt + first itinerary). Those two stay out of the
  // panel; every later turn is Ask Marco conversation and must survive
  // reloads — messages are saved to the trip record via onSave.
  const historyStart = useMemo(() => {
    const i = messages.findIndex(m => m.role === 'assistant')
    return i === -1 ? messages.length : i + 1
  }, [messages])

  const [chatMessages, setChatMessages] = useState(() => messages.slice(historyStart))

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const onScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
      shouldScrollRef.current = nearBottom
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [expanded])

  useEffect(() => {
    if (shouldScrollRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [chatMessages, streamingText])

  useEffect(() => {
    if (!streaming && expanded) inputRef.current?.focus()
  }, [streaming, expanded])

  useEffect(() => {
    // Sync with the persisted record: saved history first, then any in-flight
    // session messages that haven't landed in the trip record yet.
    const saved = messages.slice(historyStart)
    const savedContents = new Set(saved.map(m => m.content))
    setChatMessages(prev => {
      const pending = prev.filter(m => !savedContents.has(m.content))
      return [...saved, ...pending]
    })
  }, [messages, historyStart])

  async function sendMessage(text) {
    if (!text || streaming) return
    setQuickReplies([])
    setChatError(null)
    setExpanded(true)
    shouldScrollRef.current = true

    const userMsg = { role: 'user', content: text }
    // chatMessages already holds every persisted follow-up (slice from
    // historyStart), so prepend only the initial planning exchange —
    // spreading the full messages array would duplicate the follow-ups.
    const allMessages = [...messages.slice(0, historyStart), ...chatMessages, userMsg]
    setChatMessages(prev => [...prev, userMsg])

    let responseText = ''
    setStreamingText('')

    await send({
      messages: allMessages,
      tripData,
      companionMode: companion,
      weatherText,
      onChunk: chunk => {
        responseText += chunk
        setStreamingText(responseText)
      },
      onEvalCorrection: () => {
        // Marco is regenerating after a failed self-check — discard the bad
        // draft so only the corrected version is shown and persisted.
        responseText = ''
        setStreamingText('')
      },
      onDone: () => {
        const assistantMsg = { role: 'assistant', content: responseText }
        setChatMessages(prev => [...prev, assistantMsg])
        setStreamingText('')
        setQuickReplies(extractOptions(responseText))
        onSave?.([...allMessages, assistantMsg])
      },
      onError: msg => setChatError(msg),
    })
  }

  async function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text) return
    setInput('')
    await sendMessage(text)
  }

  async function handleNearMe() {
    if (nearMeLastAt && Date.now() - nearMeLastAt < NEAR_ME_TTL_MS) return
    const loc = await locate()
    if (!loc) return
    setNearMeLastAt(Date.now())
    await sendMessage(
      `I'm currently at ${loc.display}. Based on today's itinerary, what's closest to me right now and what should I do next? Give me 2-3 specific, actionable options.`
    )
  }

  const nearMeFresh = Boolean(nearMeLastAt && Date.now() - nearMeLastAt < NEAR_ME_TTL_MS)

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
      {/* Toggle header */}
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between gap-3 px-5 py-4 text-left cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white">
            M
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              {companion ? '🧭 Companion Mode' : 'Ask Marco'}
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              {companion
                ? 'Live help for your day'
                : 'Questions, tweaks, recommendations'}
            </p>
          </div>
        </div>
        <ChevronDown
          size={16}
          className={`text-slate-400 dark:text-slate-500 transition-transform ${expanded ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Chat body */}
      {expanded && (
        <div className="border-t border-slate-100 dark:border-slate-800">
          {/* Messages */}
          <div
            ref={scrollRef}
            className="max-h-96 overflow-y-auto px-4 py-4 space-y-4"
          >
            {chatMessages.length === 0 && !streamingText && !streaming && (
              <div className="text-center py-6">
                <MessageCircle size={24} className="text-slate-300 dark:text-slate-600 mx-auto mb-2" />
                <p className="text-sm text-slate-400 dark:text-slate-500">
                  {companion
                    ? "Ask me anything about today's plans!"
                    : 'Ask Marco to tweak your itinerary or answer travel questions.'}
                </p>
              </div>
            )}

            {chatMessages.map((msg, i) => (
              <Bubble key={i} role={msg.role} content={msg.content} />
            ))}

            {/* Quick replies */}
            {quickReplies.length > 0 && !streaming && (
              <div className="flex flex-wrap gap-2">
                {quickReplies.map((opt, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => {
                      setQuickReplies([])
                      sendMessage(opt)
                    }}
                    className="px-3 py-1.5 rounded-full text-xs border border-indigo-200 dark:border-indigo-700
                      bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition-colors cursor-pointer"
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}

            {/* Streaming bubble */}
            {streamingText && (
              <Bubble role="assistant" content={streamingText} isStreaming />
            )}

            {/* Tool status */}
            {toolStatus && (
              <div className="flex items-center gap-2 text-xs text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30
                border border-indigo-200 dark:border-indigo-700 rounded-lg px-3 py-2 w-fit">
                <Spinner className="w-3 h-3" /> {toolStatus}
              </div>
            )}

            {/* Thinking */}
            {streaming && !streamingText && !toolStatus && (
              <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
                <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold text-white shrink-0">M</div>
                <span className="animate-pulse">Marco is thinking…</span>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Rate limit / error banner */}
          {chatError && (
            <div className="mx-4 mb-2 mt-1 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 px-3 py-2.5 text-sm text-red-700 dark:text-red-400 flex items-center justify-between gap-2">
              <span>{chatError}</span>
              <button type="button" onClick={() => setChatError(null)} className="text-red-400 hover:text-red-600 shrink-0 text-base leading-none">✕</button>
            </div>
          )}

          {/* Near Me chip — companion mode only */}
          {companion && (
            <div className="px-4 pt-3 border-t border-slate-100 dark:border-slate-800">
              <button
                type="button"
                onClick={handleNearMe}
                disabled={locating || streaming || nearMeFresh}
                title={nearMeFresh ? 'Near Me refreshes every 30 minutes' : 'Find activities near your current location'}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border transition-colors',
                  nearMeFresh || locating || streaming
                    ? 'border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500 bg-slate-50 dark:bg-slate-800 cursor-not-allowed opacity-60'
                    : 'border-emerald-200 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-900/20 hover:bg-emerald-100 dark:hover:bg-emerald-900/40 cursor-pointer'
                )}
              >
                {locating ? <Spinner className="w-3 h-3" /> : <LocateFixed size={12} />}
                Near Me
              </button>
            </div>
          )}

          {/* Input */}
          <div className="px-4 py-3">
            <form onSubmit={handleSend} className="flex gap-2">
              <input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                disabled={streaming}
                placeholder={streaming ? 'Marco is typing…' : 'Ask Marco anything…'}
                className="flex-1 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-slate-100
                  px-3 py-2 text-sm placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-indigo-400
                  transition-colors disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={streaming || !input.trim()}
                className="px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white
                  transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              >
                <Send size={16} />
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
