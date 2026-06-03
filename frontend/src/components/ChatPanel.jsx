import { useRef, useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, ChevronDown, MessageCircle } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'
import { Spinner } from '@/components/ui/Spinner'
import { cn } from '@/lib/utils'

/** Strip [OPTION: ...] markers from displayed text. */
function stripOptions(text) {
  return text.replace(/\[OPTION:[^\]]*\]/g, '').replace(/\n{3,}/g, '\n\n').trim()
}

/** Extract [OPTION: label] markers from Marco's response as an array of strings. */
function extractOptions(text) {
  return [...text.matchAll(/\[OPTION:\s*([^\]]+)\]/g)].map(m => m[1].trim())
}

function Bubble({ role, content, isStreaming }) {
  const isMarco = role === 'assistant'
  const displayContent = isMarco ? stripOptions(content) : content
  return (
    <div className={cn('flex gap-3', isMarco ? '' : 'justify-end')}>
      {isMarco && (
        <div className="w-7 h-7 rounded-full bg-indigo-700 flex items-center justify-center text-xs font-bold text-white shrink-0 mt-0.5">
          M
        </div>
      )}
      <div
        className={cn(
          'rounded-xl px-4 py-3 text-sm max-w-[85%]',
          isMarco
            ? 'bg-[#1e2235] text-slate-200'
            : 'bg-indigo-700/30 border border-indigo-600/30 text-slate-200',
          isStreaming && isMarco ? 'streaming-cursor' : '',
        )}
      >
        {isMarco ? (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
          </div>
        ) : (
          <p className="whitespace-pre-wrap">{displayContent}</p>
        )}
      </div>
    </div>
  )
}

/**
 * ChatPanel — collapsible chat below the itinerary.
 *
 * Props:
 *   messages   — full trip conversation history (planning + previous ask-marco turns).
 *                Used as API context but NOT displayed directly — only follow-ups are shown.
 *   tripData   — for context injection
 *   companion  — bool, enables companion mode
 *   onSave     — called with (updatedMessages) after each assistant response
 */
export function ChatPanel({ messages, tripData, companion = false, weatherText = null, onSave }) {
  const { streaming, toolStatus, send } = useSSEChat()
  const [expanded, setExpanded]           = useState(false)
  // In-flight turns for the current exchange (cleared after onSave, since they
  // move into the messages prop — prevents duplicate display on re-render).
  const [chatMessages, setChatMessages]   = useState([])
  const [input, setInput]                 = useState('')
  const [streamingText, setStreamingText] = useState('')
  const [quickReplies, setQuickReplies]   = useState([])
  const bottomRef       = useRef(null)
  const inputRef        = useRef(null)
  const scrollRef       = useRef(null)   // the scrollable message list div
  const shouldScrollRef = useRef(true)
  // Snapshot of messages.length at mount — used to slice out planning history.
  // useState (not useRef) so the value is safe to read during render.
  const [initialMsgCount] = useState(messages.length)

  // Track whether user has scrolled up inside the panel
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const onScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
      shouldScrollRef.current = nearBottom
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  // Scroll to bottom when expanded or new content arrives — only if near bottom
  useEffect(() => {
    if (expanded && shouldScrollRef.current) {
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }, [expanded, messages.length, streamingText, toolStatus])

  // Focus input when panel opens
  useEffect(() => {
    if (expanded && !streaming) {
      setTimeout(() => inputRef.current?.focus(), 60)
    }
  }, [expanded, streaming])

  async function handleSend(e, overrideText) {
    e.preventDefault()
    const text = (overrideText ?? input).trim()
    if (!text || streaming) return

    shouldScrollRef.current = true   // snap to bottom for the new turn
    const userMsg = { role: 'user', content: text }
    const newChat  = [...chatMessages, userMsg]
    setChatMessages(newChat)
    setExpanded(true)
    setInput('')
    setStreamingText('')
    setQuickReplies([])

    // Full context = ALL historical messages + current in-flight turns
    const fullHistory = [...messages, ...newChat]
    let accumulated = ''

    const tripDataWithWeather = weatherText
      ? { ...tripData, weather_text: weatherText }
      : tripData

    await send({
      messages: fullHistory,
      tripData: tripDataWithWeather,
      companionMode: companion,
      onChunk: (chunk) => {
        accumulated += chunk
        setStreamingText(accumulated)
      },
      onDone: () => {
        const assistantMsg = { role: 'assistant', content: accumulated }
        const updated = [...newChat, assistantMsg]
        setStreamingText('')
        setQuickReplies(extractOptions(accumulated))
        // Persist to parent first, then clear local state.
        // After onSave the parent re-renders with updated messages prop that now
        // includes these turns — clearing chatMessages prevents duplicate display.
        onSave?.([...messages, ...updated])
        setChatMessages([])
      },
    })
  }

  // Display only follow-up exchanges added after this component mounted.
  // The planning conversation is in messages[0..initialMsgCount) — it's sent as
  // API context but is not shown here (too much noise, user already saw it in /plan).
  const followUps = [...messages.slice(initialMsgCount), ...chatMessages]
  const isEmpty   = followUps.length === 0 && !streaming

  const headerLabel = companion ? '🧭 Marco — Companion' : '💬 Ask Marco'
  const placeholder = companion
    ? "What's the weather like? Should I change today's plan?"
    : 'Ask a follow-up…'

  const dest = tripData?.city || tripData?.destination || 'the destination'
  const suggestions = companion
    ? [
        "What should I prioritise today?",
        "Any food spots I shouldn't miss nearby?",
        "I have extra time — what do you recommend?",
        "Should I adjust today's plan?",
      ]
    : [
        `What should I pack for ${dest}?`,
        "Any hidden gems I shouldn't miss?",
        "How can I trim costs on this trip?",
        "Add a day trip to the itinerary",
      ]

  return (
    <div className="rounded-xl border border-[#2e3248] bg-[#1a1d27] overflow-hidden">
      {/* Header — click to toggle */}
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between px-5 py-3
          border-b border-[#2e3248] hover:bg-white/[.03] transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <MessageCircle size={14} className="text-indigo-400" />
          <span className="text-sm font-semibold text-slate-200">{headerLabel}</span>
          {followUps.length > 0 && (
            <span className="text-xs text-slate-500">
              · {followUps.length} message{followUps.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <ChevronDown
          size={15}
          className={cn(
            'text-slate-400 transition-transform duration-200',
            expanded ? 'rotate-180' : '',
          )}
        />
      </button>

      {/* Collapsible body */}
      {expanded && (
        <>
          {/* Message list */}
          <div ref={scrollRef} className="flex flex-col gap-4 p-5 max-h-[520px] overflow-y-auto">
            {isEmpty && (
              <div className="py-2 space-y-2">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={(e) => handleSend(e, s)}
                    className="w-full text-left px-3 py-2 rounded-lg text-sm border border-[#2e3248]
                      bg-[#1a1d27] text-slate-400 hover:text-slate-200 hover:border-indigo-500/50
                      transition-colors cursor-pointer"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            {followUps.map((msg, i) => (
              <Bubble key={i} role={msg.role} content={msg.content} />
            ))}

            {/* Quick-reply option buttons — shown after Marco's last message */}
            {quickReplies.length > 0 && !streaming && (
              <div className="flex flex-wrap gap-2 pl-10">
                {quickReplies.map((opt, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={(e) => handleSend(e, opt)}
                    className="px-4 py-2 rounded-full text-sm border border-indigo-600/60
                      bg-indigo-900/20 text-indigo-300 hover:bg-indigo-900/40
                      hover:border-indigo-500 transition-colors cursor-pointer"
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}

            {toolStatus && (
              <div className="flex items-center gap-2 text-xs text-indigo-300 bg-indigo-900/20 border border-indigo-800/40 rounded-lg px-3 py-2">
                <Spinner className="w-3 h-3" /> {toolStatus}
              </div>
            )}

            {streamingText && (
              <Bubble role="assistant" content={streamingText} isStreaming />
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <form onSubmit={handleSend} className="flex gap-2 px-4 pb-4">
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={streaming ? 'Marco is typing…' : placeholder}
              disabled={streaming}
              className="flex-1 rounded-lg bg-[#22263a] border border-[#2e3248] text-slate-200 text-sm
                px-3 py-2 placeholder-slate-500 focus:outline-none focus:border-indigo-500
                disabled:opacity-50 transition-colors"
            />
            <button
              type="submit"
              disabled={!input.trim() || streaming}
              className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40
                transition-colors cursor-pointer"
            >
              {streaming ? <Spinner className="w-4 h-4" /> : <Send size={16} />}
            </button>
          </form>
        </>
      )}
    </div>
  )
}
