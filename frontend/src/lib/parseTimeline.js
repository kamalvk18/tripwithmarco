// Parses a day's markdown content into time-of-day slots for the timeline view.
// Marco's itineraries use bold headings like **Morning**, **Afternoon**, **Evening**.

const SLOT_DEFS = [
  { keys: ['morning'],       label: 'Morning',      color: 'amber'  },
  { keys: ['afternoon'],     label: 'Afternoon',    color: 'sky'    },
  { keys: ['evening'],       label: 'Evening',      color: 'orange' },
  { keys: ['night', 'late'], label: 'Night',        color: 'violet' },
]

function resolveSlot(raw) {
  const lower = raw.toLowerCase()
  for (const def of SLOT_DEFS) {
    if (def.keys.some(k => lower.startsWith(k))) return def
  }
  return { label: raw, color: 'slate' }
}

// A line is a time-of-day heading if it is ONLY bold text that starts with a
// known time word, e.g. "**Morning**", "**Morning/Afternoon**", "**Late Evening**"
const HEADING_RE = /^\*{1,2}(Morning|Afternoon|Evening|Night|Late\s+Evening)[^*]*\*{1,2}\s*$/i

const BUDGET_RE = /^\s*\*{0,2}\s*Budget\s+today/i

export function parseTimeline(content) {
  if (!content) return null

  const lines = content.split('\n')
  const slots = []
  const introLines = []
  let current = null
  let budgetLine = null

  for (const line of lines) {
    if (HEADING_RE.test(line)) {
      if (current) slots.push(current)
      const raw = line.replace(/\*/g, '').trim()
      current = { ...resolveSlot(raw), label: raw, lines: [] }
    } else if (BUDGET_RE.test(line)) {
      if (current) { slots.push(current); current = null }
      budgetLine = line.replace(/\*{1,2}/g, '').trim()
    } else if (current) {
      current.lines.push(line)
    } else {
      introLines.push(line)
    }
  }

  if (current) slots.push(current)

  // If we found no time slots the content doesn't follow the expected format
  if (slots.length === 0) return null

  return {
    intro:  introLines.join('\n').trim(),
    slots:  slots.map(s => ({ ...s, content: s.lines.join('\n').trim() })),
    budget: budgetLine,
  }
}
