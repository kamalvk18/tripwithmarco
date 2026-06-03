import { useState, useRef, useEffect } from 'react'
import { MapPin } from 'lucide-react'
import { useLocationSuggestions } from '@/hooks/useLocationSuggestions'
import { Spinner } from '@/components/ui/Spinner'
import { cn } from '@/lib/utils'

/**
 * Text input with city autocomplete powered by Photon (OpenStreetMap).
 *
 * Props:
 *   value       — controlled string value (city name)
 *   onChange    — (name: string) => void   — called on every keystroke
 *   onSelect    — (suggestion: { name, label, country, countryCode, state }) => void
 *                 called only when the user picks from the dropdown
 *   placeholder — string
 *   required    — bool
 *   className   — extra class names for the <input>
 *
 * Keyboard: ↑ / ↓ navigate, Enter selects, Escape closes.
 */
export function AutocompleteInput({
  value,
  onChange,
  onSelect,
  placeholder = '',
  required = false,
  className = '',
  ...inputProps
}) {
  // `closed` tracks whether the user explicitly dismissed the dropdown.
  // It resets to false whenever the user types, so the dropdown re-opens
  // on the next keystroke. This avoids a useEffect that syncs state to
  // suggestions (which triggers cascading renders).
  const [closed, setClosed]    = useState(false)
  const [activeIdx, setActive] = useState(-1)
  const containerRef           = useRef(null)
  const inputRef               = useRef(null)

  const { suggestions, loading } = useLocationSuggestions(value)

  // Derived: show dropdown only when there are results and user hasn't dismissed
  const isOpen = suggestions.length > 0 && !closed

  // Close when clicking outside — setState happens in the event listener
  // callback, not synchronously in the effect body, so no cascading-render issue.
  useEffect(() => {
    function onMouseDown(e) {
      if (!containerRef.current?.contains(e.target)) setClosed(true)
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [])

  function handleChange(val) {
    onChange(val)
    setClosed(false)   // user is typing — re-open dropdown
    setActive(-1)
  }

  function pick(suggestion) {
    onChange(suggestion.name)
    onSelect?.(suggestion)
    setClosed(true)
    setActive(-1)
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  function handleKeyDown(e) {
    if (!isOpen) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive(i => Math.min(i + 1, suggestions.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && activeIdx >= 0) {
      e.preventDefault()
      pick(suggestions[activeIdx])
    } else if (e.key === 'Escape') {
      setClosed(true)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        ref={inputRef}
        value={value}
        onChange={e => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={() => setClosed(false)}
        placeholder={placeholder}
        required={required}
        autoComplete="off"
        className={cn(
          `w-full rounded-lg bg-white border border-slate-200 text-slate-800
           px-3 py-2 text-sm placeholder-slate-400 focus:outline-none focus:border-indigo-400
           focus:ring-2 focus:ring-indigo-100 transition-all shadow-sm`,
          className,
        )}
        {...inputProps}
      />

      {/* Loading spinner */}
      {loading && (
        <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none">
          <Spinner className="w-3.5 h-3.5 text-slate-500" />
        </div>
      )}

      {/* Suggestion dropdown */}
      {isOpen && (
        <ul
          role="listbox"
          className="absolute z-50 top-full mt-1 w-full rounded-lg border border-slate-200
            bg-white shadow-lg overflow-hidden text-sm"
        >
          {suggestions.map((s, i) => (
            <li
              key={s.label}
              role="option"
              aria-selected={i === activeIdx}
              onMouseDown={() => pick(s)}
              onMouseEnter={() => setActive(i)}
              className={cn(
                'flex items-center gap-2.5 px-3 py-2.5 cursor-pointer select-none transition-colors',
                i === activeIdx
                  ? 'bg-indigo-50 text-indigo-800'
                  : 'text-slate-700 hover:bg-slate-50',
              )}
            >
              <MapPin size={13} className="text-indigo-500 shrink-0" />
              <span className="truncate">{s.label}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
