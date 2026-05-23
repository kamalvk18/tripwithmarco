import { useState, useRef, useCallback } from 'react'
import { chatStream } from '@/lib/api'
import { toolLabel } from '@/lib/utils'

/**
 * Hook for streaming chat with Marco.
 *
 * Returns { streaming, toolStatus, send, abort }
 *   streaming  — true while receiving chunks
 *   toolStatus — current tool label shown to user (null when idle)
 *   send(opts) — start a stream; opts = { messages, tripData, companionMode, onChunk, onDone, onError }
 *   abort()    — cancel in-flight stream
 */
export function useSSEChat() {
  const [streaming, setStreaming]   = useState(false)
  const [toolStatus, setToolStatus] = useState(null)
  const abortRef = useRef(null)

  const abort = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
    setToolStatus(null)
  }, [])

  const send = useCallback(async ({
    messages,
    tripData = null,
    companionMode = false,
    onChunk,
    onDone,
    onError,
  }) => {
    abort()   // cancel any previous stream
    const controller = new AbortController()
    abortRef.current = controller
    setStreaming(true)
    setToolStatus(null)

    try {
      await chatStream({
        messages,
        tripData,
        companionMode,
        signal: controller.signal,
        onText: (chunk) => {
          setToolStatus(null)
          onChunk?.(chunk)
        },
        onToolCall: (name) => {
          setToolStatus(toolLabel(name))
        },
      })
      onDone?.()
    } catch (err) {
      if (err.name !== 'AbortError') {
        onError?.(err.message ?? 'Stream error')
      }
    } finally {
      setStreaming(false)
      setToolStatus(null)
    }
  }, [abort])

  return { streaming, toolStatus, send, abort }
}
