import { useState } from 'react'
import { Mail, BellRing, BellOff, Send, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { apiFetch } from '@/lib/api'

async function apiSaveConfig(tripId, config) {
  const res = await apiFetch(`/api/trips/${tripId}/email-config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
  return res.ok
}

async function apiSendNow(tripId, email) {
  const res = await apiFetch(`/api/trips/${tripId}/send-briefing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ to_email: email }),
  })
  return res.ok
}

export function EmailBriefingConfig({ tripId, emailConfig = {}, onUpdate, forceOpen = false, onOpenChange }) {
  const [open, setOpen]       = useState(forceOpen)

  function toggleOpen(val) {
    setOpen(val)
    onOpenChange?.(val)
  }
  const [email, setEmail]     = useState(emailConfig.email ?? '')
  const [time, setTime]       = useState(emailConfig.send_time ?? '07:00')
  const [enabled, setEnabled] = useState(emailConfig.enabled ?? false)
  const [saving, setSaving]   = useState(false)
  const [sending, setSending] = useState(false)
  const [toast, setToast]     = useState(null)

  function showToast(msg, ok = true) {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3500)
  }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    const cfg = { email, send_time: time, enabled }
    const ok  = await apiSaveConfig(tripId, cfg)
    setSaving(false)
    if (ok) {
      onUpdate?.(cfg)
      showToast(enabled ? `Briefings enabled — you'll get an email at ${time} UTC each trip day.` : 'Briefings disabled.')
    } else {
      showToast('Failed to save. Check the API server.', false)
    }
  }

  async function handleSendNow() {
    if (!email) return
    setSending(true)
    const ok = await apiSendNow(tripId, email)
    setSending(false)
    showToast(ok ? `Test briefing sent to ${email}!` : 'Send failed — email service may not be configured on the server.', ok)
  }

  const isConfigured = !!emailConfig.email
  const inputCls = "w-full rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-slate-100 px-3 py-2 text-sm placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:focus:ring-indigo-900 transition-all shadow-sm"

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
      {/* Header */}
      <button
        type="button"
        onClick={() => toggleOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 cursor-pointer text-left hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Mail size={16} className="text-indigo-600" />
          <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">Daily Briefing Email</span>
          <span className="text-xs text-slate-400 dark:text-slate-500">
            {isConfigured && emailConfig.enabled
              ? `✅ Sending to ${emailConfig.email} at ${emailConfig.send_time} UTC`
              : isConfigured
              ? '⏸ Configured but paused'
              : 'Not set up'}
          </span>
        </div>
        <ChevronDown size={15} className={`text-slate-400 dark:text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-slate-100 dark:border-slate-800 px-5 py-5 space-y-4">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Marco sends a morning email each trip day: today's weather, your plan, and remaining budget.
          </p>

          <form onSubmit={handleSave} className="space-y-3">
            <div>
              <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">Email address</label>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                className={inputCls}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">Send time (UTC)</label>
                <input
                  type="time"
                  value={time}
                  onChange={e => setTime(e.target.value)}
                  className={inputCls}
                />
                <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">Actual delivery depends on the server's cron schedule.</p>
              </div>
              <div className="flex items-end pb-0.5">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={e => setEnabled(e.target.checked)}
                    className="w-4 h-4 rounded accent-indigo-500"
                  />
                  <span className="text-sm text-slate-700 dark:text-slate-200">Enable briefings</span>
                </label>
              </div>
            </div>

            <div className="flex gap-2 pt-1">
              <Button type="submit" variant="primary" size="sm" disabled={saving || !email}>
                {saving ? <Spinner className="w-3.5 h-3.5" /> : (enabled ? <BellRing size={13} /> : <BellOff size={13} />)}
                {saving ? 'Saving…' : 'Save'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={sending || !email}
                onClick={handleSendNow}
                title="Send a test briefing now"
              >
                {sending ? <Spinner className="w-3.5 h-3.5" /> : <Send size={13} />}
                {sending ? 'Sending…' : 'Send test now'}
              </Button>
            </div>
          </form>

          {toast && (
            <div className={`rounded-lg px-4 py-2.5 text-sm ${toast.ok
              ? 'bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700 text-emerald-700 dark:text-emerald-300'
              : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 text-red-600 dark:text-red-400'}`}>
              {toast.msg}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
