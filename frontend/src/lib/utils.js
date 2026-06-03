/**
 * Shared utility functions.
 */

/** Merge class names (basic clsx replacement). */
export function cn(...classes) {
  return classes.filter(Boolean).join(' ')
}

/** Given a trip, return {status, label, dayNum}. */
export function tripStatus(trip) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  if (!trip.start_date || !trip.end_date) return { status: 'unknown', label: '' }

  const start = new Date(trip.start_date)
  const end   = new Date(trip.end_date)

  if (today < start) {
    const days = Math.round((start - today) / 86400000)
    return { status: 'upcoming', label: `in ${days}d`, dayNum: null }
  }
  if (today > end) {
    return { status: 'past', label: 'completed', dayNum: null }
  }
  const dayNum = Math.round((today - start) / 86400000) + 1
  const totalDays = Math.round((end - start) / 86400000) + 1
  return { status: 'active', label: `Day ${dayNum} of ${totalDays}`, dayNum }
}

/**
 * Split itinerary text into day objects: [{num, title, content}]
 *
 * Exact port of extract_all_days() from backend/agents/planning_agent.py.
 *
 * Key differences from a naive approach:
 *  1. ^ and $ anchors (multiline) — the entire line must be the heading,
 *     so "Day 1 is REST DAY. Non-negotiable..." in body text is NOT matched.
 *  2. De-duplication — only the first occurrence of each day number is kept.
 *  3. Title cleanup — strips markdown (#, *, _) and the "Day N:" prefix.
 */
export function extractAllDays(text) {
  if (!text) return []

  // Same regex as Python's heading_pattern (converted to JS):
  //   ^([ \t]* optional-# optional-** Day N optional-** optional-: rest)$
  // The $ anchor (with m flag) is the key guard: "Day 1 is REST DAY..."
  // does NOT end at $ unless the whole line IS that heading.
  const headingRe = /^([ \t]*(?:#{1,3}[ \t]*[^\w\n]*[ \t]*)?\*{0,2}(?:Day|DAY)[ \t]+(\d+)(?:\*{0,2})?[ \t]*(?:[-—–:][^\n]*)?)$/gim

  // Collect all heading matches
  const allMatches = []
  let m
  while ((m = headingRe.exec(text)) !== null) {
    allMatches.push({ num: parseInt(m[2]), rawTitle: m[1], index: m.index })
  }

  // Keep only the first occurrence of each day number (de-duplicate)
  const seen = new Set()
  const matches = []
  for (const match of allMatches) {
    if (!seen.has(match.num)) {
      seen.add(match.num)
      matches.push(match)
    }
  }

  if (matches.length === 0) return []

  const days = []
  for (let i = 0; i < matches.length; i++) {
    const { num, rawTitle, index } = matches[i]
    const end     = matches[i + 1]?.index ?? text.length
    const content = text.slice(index, end).trim()

    // Clean title: strip # and * markup, then remove the "Day N: " prefix
    // so the title is only the descriptive part (e.g. "Arrival & Acclimatization")
    let title = rawTitle
      .replace(/[#*_]+/g, '')        // strip markdown markers
      .replace(/\s+/g, ' ')          // normalize whitespace
      .trim()
    title = title
      .replace(/^Day\s+\d+\s*[-—–:]?\s*/i, '')  // remove "Day N:" prefix
      .trim()

    days.push({ num, title, content })
  }
  return days
}

/**
 * Find and clean the itinerary text from a conversation messages array.
 *
 * Picks the last assistant message that produces parseable day structure so
 * follow-up messages that only mention "Day 1" inline never hijack the result.
 */
export function computeItinerary(messages) {
  const assistantMsgs = (messages ?? []).filter(
    m => m.role === 'assistant' && typeof m.content === 'string'
  )
  const clean = text =>
    text.replace(/\[OPTION:[^\]]*\]/g, '').replace(/\n{3,}/g, '\n\n').trim()

  const raw = (
    [...assistantMsgs].reverse().find(m => extractAllDays(clean(m.content)).length > 0)
    ?? assistantMsgs[0]
  )?.content ?? ''

  return clean(raw)
}

const TOOL_LABELS = {
  search_flights: '✈️ Checking flights...',
  search_hotels:  '🏨 Searching hotels...',
  search_places:  '📍 Finding local spots...',
  get_weather:    '🌤️ Checking weather...',
}
export function toolLabel(name) {
  return TOOL_LABELS[name] ?? `🔧 Using ${name}...`
}

/** Format a budget number with currency symbol. */
export function formatMoney(amount, currency = 'EUR') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency', currency, maximumFractionDigits: 0,
  }).format(amount)
}
