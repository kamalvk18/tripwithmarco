import { useRef, useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { Send, ChevronDown, MessageCircle } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'
import { Spinner } from '@/components/ui/Spinner'
import { cn } from '@/lib/utils'

/** Strip [OPTION: ...] markers — they're planning-phase UI, not content. */
function stripOptions(text) {
  return text.replace(/\[OPTION:[^\]]*\]/g, '').replace(/\n{3,}/g, '\n\n').trim()
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
            <ReactMarkdown>{displayContent}</ReactMarkdown>
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
 *   messages   — full trip conversation history (planning + previous ask-marco turns)
 *   tripData   — for context injection
 *   companion  — bool, enables companion mode
 *   onSave     — called with (updatedMessages) after each assistant response
 */
export function ChatPanel({ messages, tripData, companion = false, onSave }) {
  const { streaming, toolStatus, send } = useSSEChat()
  const [expanded, setExpanded]           = useState(false)
  const [chatMessages, setChatMessages]   = useState([])   // new turns added in TripView
  const [input, setInput]                 = useState('')
  const [streamingText, setStreamingText] = useState('')
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  // Auto-expand when new turns arrive (e.g. user starts chatting)
  useEffect(() => {
    if (chatMessages.length > 0) setExpanded(true)
  }, [chatMessages.length])

  // Scroll to bottom when expanded or when new messages arrive
  useEffect(() => {
    if (expanded) {
      // Small delay so the panel has finished rendering before scrolling
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }, [expanded, chatMessages, streamingText, toolStatus])

  // Focus input when panel opens
  useEffect(() => {
    if (expanded && !streaming) {
      setTimeout(() => inputRef.current?.focus(), 60)
    }
  }, [expanded, streaming])

  async function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || streaming) return

    const userMsg = { role: 'user', content: text }
    const newChat  = [...chatMessages, userMsg]
    setChatMessages(newChat)
    setInput('')
    setStreamingText('')

    // Full context = historical trip messages + new ask-marco turns
    const fullHistory = [...messages, ...newChat]
    let accumulated = ''

    await send({
      messages: fullHistory,
      tripData,
      companionMode: companion,
      onChunk: (chunk) => {
        accumulated += chunk
        setStreamingText(accumulated)
      },
      onDone: () => {
        const assistantMsg = { role: 'assistant', content: accumulated }
        const updated = [...newChat, assistantMsg]
        setChatMessages(updated)
        setStreamingText('')
        // Persist the full updated history back to the trip
        onSave?.([...messages, ...updated])
      },
    })
  }

  // All messages to display: historical planning conversation + new ask-marco turns
  const allDisplay = [...messages, ...chatMessages]
  const isEmpty    = allDisplay.length === 0 && !streaming

  const headerLabel = companion ? '🧭 Marco — Companion' : '💬 Ask Marco'
  const placeholder = companion
    ? "What's the weather like? Should I change today's plan?"
    : 'Ask a follow-up…'
  const emptyHint = companion
    ? "Ask Marco about today's weather, what to prioritise, or how to adjust the plan."
    : "Ask Marco anything — refine the plan, get local tips, or explore alternatives."

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
          {allDisplay.length > 0 && (
            <span className="text-xs text-slate-500">
              · {allDisplay.length} message{allDisplay.length !== 1 ? 's' : ''}
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
          <div className="flex flex-col gap-4 p-5 max-h-[520px] overflow-y-auto">
            {isEmpty && (
              <p className="text-xs text-slate-500 text-center py-4">{emptyHint}</p>
            )}

            {allDisplay.map((msg, i) => (
              <Bubble key={i} role={msg.role} content={msg.content} />
            ))}

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
