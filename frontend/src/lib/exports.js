/**
 * Export helpers — mirrors the Python export functions in frontend/app.py.
 */

function icsEscape(text) {
  return (text ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\n/g, '\\n')
}

function toIcsDate(dateStr) {
  return dateStr.replace(/-/g, '')
}

/** Build a Markdown string of the full itinerary. */
export function buildMarkdown(tripData, days) {
  const lines = [
    `# ${tripData.destination}`,
    `**Dates:** ${tripData.dates}`,
    tripData.budget ? `**Budget:** ${tripData.currency ?? 'EUR'} ${tripData.budget}` : '',
    '',
    '---',
    '',
  ]

  for (const day of days) {
    const content = tripData.day_overrides?.[String(day.num)] ?? day.content
    lines.push(content)
    lines.push('')
  }

  return lines.filter(l => l !== undefined).join('\n')
}

/** Build an .ics calendar file string. */
export function buildICS(tripData, days) {
  const start = new Date(tripData.start_date)
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Marco//Marco//EN',
    'CALSCALE:GREGORIAN',
  ]

  for (const day of days) {
    const date = new Date(start)
    date.setDate(start.getDate() + day.num - 1)
    const dateStr  = toIcsDate(date.toISOString().slice(0, 10))
    const nextDate = toIcsDate(new Date(date.getTime() + 86400000).toISOString().slice(0, 10))
    const content  = tripData.day_overrides?.[String(day.num)] ?? day.content
    const summary  = `Day ${day.num}: ${day.title || tripData.destination}`

    lines.push(
      'BEGIN:VEVENT',
      `DTSTART;VALUE=DATE:${dateStr}`,
      `DTEND;VALUE=DATE:${nextDate}`,
      `SUMMARY:${icsEscape(summary)}`,
      `DESCRIPTION:${icsEscape(content)}`,
      `UID:marco-day${day.num}-${tripData.trip_id ?? 'trip'}@marco`,
      'END:VEVENT',
    )
  }

  lines.push('END:VCALENDAR')
  return lines.join('\r\n')
}

/** Build a self-contained offline HTML string. */
export function buildOfflineHTML(tripData, days) {
  const dayBlocks = days.map(day => {
    const content = (tripData.day_overrides?.[String(day.num)] ?? day.content)
      .replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>')
    const rebuilt = tripData.day_overrides?.[String(day.num)] ? ' 🔄' : ''
    return `
      <details>
        <summary><strong>Day ${day.num}${rebuilt}</strong> — ${day.title ?? ''}</summary>
        <div class="day-content">${content}</div>
      </details>`
  }).join('\n')

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${tripData.destination} — Itinerary</title>
  <style>
    :root { --bg:#0f1117; --fg:#e2e8f0; --border:#2e3248; --accent:#6366f1; --surface:#1a1d27; }
    @media(prefers-color-scheme:light){ :root{--bg:#f8f9fa;--fg:#1e293b;--border:#e2e8f0;--surface:#fff;} }
    body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--fg); max-width: 720px; margin: 0 auto; padding: 2rem 1rem; line-height: 1.7; }
    h1 { font-size: 1.75rem; margin-bottom: 0.25rem; }
    .meta { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    details { border: 1px solid var(--border); border-radius: 10px; margin-bottom: 0.75rem; background: var(--surface); }
    summary { padding: 1rem 1.25rem; cursor: pointer; font-size: 1rem; }
    summary::-webkit-details-marker { display: none; }
    details[open] summary { border-bottom: 1px solid var(--border); }
    .day-content { padding: 1rem 1.25rem; font-size: 0.92rem; }
  </style>
</head>
<body>
  <h1>${tripData.destination}</h1>
  <p class="meta">${tripData.dates} &bull; Saved offline by Marco</p>
  ${dayBlocks}
</body>
</html>`
}

/** Trigger a browser download for a string blob. */
export function downloadFile(content, filename, mimeType = 'text/plain') {
  const blob = new Blob([content], { type: mimeType })
  const url  = URL.createObjectURL(blob)
  const a    = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}
