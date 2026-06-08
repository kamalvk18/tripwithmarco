import { useState } from 'react'
import { Share2, Copy, Check, RefreshCw, X, Users, LogOut, ChevronDown, Link } from 'lucide-react'
import { generateInviteLink, regenerateInviteLink, revokeInviteLink, kickMember, leaveTrip } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'

function MemberAvatar({ member, size = 'md' }) {
  const dim = size === 'sm' ? 'w-7 h-7 text-xs' : 'w-9 h-9 text-sm'
  return member.picture ? (
    <img
      src={member.picture}
      alt={member.name}
      title={member.name}
      className={`${dim} rounded-full object-cover border-2 border-white shadow-sm`}
    />
  ) : (
    <div
      title={member.name}
      className={`${dim} rounded-full bg-indigo-200 flex items-center justify-center font-bold text-indigo-700 border-2 border-white shadow-sm`}
    >
      {member.name?.[0]?.toUpperCase() ?? '?'}
    </div>
  )
}

export function MemberAvatarStack({ members = [], max = 4 }) {
  const shown = members.slice(0, max)
  const extra = members.length - max
  return (
    <div className="flex items-center -space-x-2">
      {shown.map(m => (
        <MemberAvatar key={m.user_id} member={m} size="sm" />
      ))}
      {extra > 0 && (
        <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center text-xs font-semibold text-slate-600 border-2 border-white shadow-sm">
          +{extra}
        </div>
      )}
    </div>
  )
}

export function SharePanel({ tripId, isOwner, members = [], onMembersChange, onLeave }) {
  const [open, setOpen]           = useState(false)
  const [inviteUrl, setInviteUrl] = useState(null)
  const [copied, setCopied]       = useState(false)
  const [working, setWorking]     = useState(false)
  const [revoking, setRevoking]   = useState(false)
  const [error, setError]         = useState(null)

  async function handleGetLink() {
    setWorking(true)
    setError(null)
    try {
      const data = await generateInviteLink(tripId)
      setInviteUrl(data.invite_url)
    } catch (e) {
      setError(e.message)
    } finally {
      setWorking(false)
    }
  }

  async function handleRegenerate() {
    setWorking(true)
    setError(null)
    try {
      const data = await regenerateInviteLink(tripId)
      setInviteUrl(data.invite_url)
    } catch (e) {
      setError(e.message)
    } finally {
      setWorking(false)
    }
  }

  async function handleRevoke() {
    if (!confirm('Revoke the invite link? Anyone with the old link will no longer be able to join.')) return
    setRevoking(true)
    await revokeInviteLink(tripId)
    setInviteUrl(null)
    setRevoking(false)
  }

  async function handleCopy() {
    if (!inviteUrl) return
    try {
      await navigator.clipboard.writeText(inviteUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for browsers that block clipboard access
      const el = document.createElement('textarea')
      el.value = inviteUrl
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  async function handleKick(userId, name) {
    if (!confirm(`Remove ${name} from this trip?`)) return
    await kickMember(tripId, userId)
    onMembersChange?.(members.filter(m => m.user_id !== userId))
  }

  async function handleLeave() {
    if (!confirm('Leave this trip? You will lose access to the itinerary.')) return
    try {
      await leaveTrip(tripId)
      onLeave?.()
    } catch (e) {
      setError(e.message)
    }
  }

  const shownMembers = members.filter(m => m.role !== 'owner' || isOwner ? true : m.role === 'owner')

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header toggle */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 cursor-pointer text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Users size={16} className="text-indigo-600" />
          <span className="text-sm font-semibold text-slate-700">Trip Members</span>
          {members.length > 0 && (
            <MemberAvatarStack members={members} max={4} />
          )}
          <span className="text-xs text-slate-400">
            {members.length} {members.length === 1 ? 'person' : 'people'}
          </span>
        </div>
        <ChevronDown size={15} className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-slate-100">
          {/* Members list */}
          <div className="px-5 py-4 space-y-3">
            {members.map(member => (
              <div key={member.user_id} className="flex items-center gap-3 group">
                <MemberAvatar member={member} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-700 truncate">{member.name}</span>
                    {member.role === 'owner' && (
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-indigo-100 text-indigo-700 font-medium">
                        owner
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-slate-400 truncate">{member.email}</span>
                </div>
                {/* Kick button — owner only, not for themselves */}
                {isOwner && member.role !== 'owner' && (
                  <button
                    type="button"
                    onClick={() => handleKick(member.user_id, member.name)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 cursor-pointer"
                    title={`Remove ${member.name}`}
                  >
                    <X size={13} />
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Invite link section — owner only */}
          {isOwner && (
            <div className="px-5 pb-5 border-t border-slate-100 pt-4">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                Invite Link
              </p>

              {!inviteUrl ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleGetLink}
                  disabled={working}
                >
                  {working ? <Spinner className="w-3.5 h-3.5" /> : <Link size={13} />}
                  {working ? 'Generating…' : 'Generate Invite Link'}
                </Button>
              ) : (
                <div className="space-y-3">
                  {/* Link display */}
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-slate-50 border border-slate-200">
                    <span className="flex-1 text-xs text-slate-600 truncate font-mono">{inviteUrl}</span>
                    <button
                      type="button"
                      onClick={handleCopy}
                      className="shrink-0 p-1.5 rounded-md hover:bg-slate-200 transition-colors text-slate-500 hover:text-slate-700 cursor-pointer"
                      title="Copy link"
                    >
                      {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
                    </button>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleCopy}
                    >
                      {copied ? <><Check size={12} /> Copied!</> : <><Share2 size={12} /> Share Link</>}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleRegenerate}
                      disabled={working}
                      title="Regenerate link (old link stops working)"
                    >
                      {working ? <Spinner className="w-3 h-3" /> : <RefreshCw size={12} />}
                      New Link
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleRevoke}
                      disabled={revoking}
                      className="text-red-500 hover:bg-red-50"
                    >
                      Revoke
                    </Button>
                  </div>

                  <p className="text-xs text-slate-400">
                    Anyone with this link can join. Regenerate to invalidate the old link.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Leave button — members only */}
          {!isOwner && (
            <div className="px-5 pb-5 border-t border-slate-100 pt-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleLeave}
                className="text-red-500 hover:bg-red-50"
              >
                <LogOut size={13} /> Leave Trip
              </Button>
              <p className="text-xs text-slate-400 mt-2">
                You'll lose access to this trip's itinerary and won't be able to rejoin unless re-invited.
              </p>
            </div>
          )}

          {error && (
            <div className="mx-5 mb-4 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
