import { useRef, useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { Send } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'
import { Spinner } from '@/components/ui/Spinner'
import { cn } from '@/lib/utils'

function Bubble({ role, content, isStreaming }) {
  const isMarco = role === 'assistant'
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
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        ) : (
          <p className="whitespace-pre-wrap">{content}</p>
        )}
      </div>
    </div>
  )
}

/**
 * ChatPanel — inline chat below the itinerary.
 *
 * Props:
 *   messages   — full trip conversation history
 *   tripData   — for context injection
 *   companion  — bool, enables companion mode
 *   onSave     — called with (updatedMessages) after each assistant response
 */
export function ChatPanel({ messages, tripData, companion = false, onSave }) {
  const { streaming, toolStatus, send } = useSSEChat()
  const [chatMessages, setChatMessages] = useState([])   // extra chat turns on top of itinerary
  const [input, setInput]               = useState('')
  const [streamingText, setStreamingText] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, streamingText, toolStatus])

  async function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || streaming) return

    const userMsg = { role: 'user', content: text }
    const newChat  = [...chatMessages, userMsg]
    setChatMessages(newChat)
    setInput('')
    setStreamingText('')

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
        onSave?.([...messages, ...updated])
      },
    })
  }

  return (
    <div className="rounded-xl border border-[#2e3248] bg-[#1a1d27] overflow-hidden">
      <div className="px-5 py-3 border-b border-[#2e3248]">
        <h3 className="text-sm font-semibold text-slate-200">
          {companion ? '🧭 Marco — Companion' : '💬 Ask Marco'}
        </h3>
      </div>

      {/* Message list */}
      <div className="flex flex-col gap-4 p-5 max-h-[480px] overflow-y-auto">
        {chatMessages.length === 0 && !streaming && (
          <p className="text-xs text-slate-500 text-center py-4">
            {companion
              ? "Ask Marco about today's weather, what to prioritise, or how to adjust the plan."
              : "Ask Marco anything about your trip — he'll refine the plan, give local tips, or find alternatives."}
          </p>
        )}

        {chatMessages.map((msg, i) => (
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
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={companion ? "What's the weather like? Should I change today's plan?" : 'Ask a follow-up…'}
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
    </div>
  )
}
