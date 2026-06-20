import { useRef, useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, ChevronDown, MessageCircle } from 'lucide-react'
import { useSSEChat } from '@/hooks/useSSEChat'
import { Spinner } from '@/components/ui/Spinner'
import { cn } from '@/lib/utils'

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
  const [expanded, setExpanded]           = useState(false)
  const [chatMessages, setChatMessages]   = useState([])
  const [input, setInput]                 = useState('')
  const [streamingText, setStreamingText] = useState('')
  const [quickReplies, setQuickReplies]   = useState([])
  const [chatError, setChatError]         = useState(null)
  const bottomRef       = useRef(null)
  const inputRef        = useRef(null)
  const scrollRef       = useRef(null)
  const shouldScrollRef = useRef(true)
  const [initialMsgCount] = useState(messages.length)

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
    const newOnes = messages.slice(initialMsgCount)
    const inFlight = chatMessages.map(m => m.content)
    const deduped = newOnes.filter(m => !inFlight.includes(m.content))
    if (deduped.length > 0) setChatMessages(deduped)
  }, [messages])

  async function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    setQuickReplies([])
    setChatError(null)
    shouldScrollRef.current = true

    const userMsg = { role: 'user', content: text }
    const allMessages = [...messages, ...chatMessages, userMsg]
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

  const displayMessages = chatMessages

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
            {displayMessages.length === 0 && !streamingText && !streaming && (
              <div className="text-center py-6">
                <MessageCircle size={24} className="text-slate-300 dark:text-slate-600 mx-auto mb-2" />
                <p className="text-sm text-slate-400 dark:text-slate-500">
                  {companion
                    ? "Ask me anything about today's plans!"
                    : 'Ask Marco to tweak your itinerary or answer travel questions.'}
                </p>
              </div>
            )}

            {displayMessages.map((msg, i) => (
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
                      setInput(opt)
                      inputRef.current?.focus()
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

          {/* Input */}
          <div className="border-t border-slate-100 dark:border-slate-800 px-4 py-3">
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
