import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { Spinner } from '@/components/ui/Spinner'

export default function AuthCallback() {
  const { loginWithToken } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState(null)

  useEffect(() => {
    // Token is in the URL fragment (#<jwt>) — never sent to servers or logged.
    // Falls back to ?token= query param for backward compatibility with old server versions.
    const token =
      window.location.hash.slice(1) ||
      new URLSearchParams(window.location.search).get('token') ||
      null

    if (!token) {
      setError('No token received from Google.')
      return
    }

    loginWithToken(token)
      .then(() => {
        // Resume a pending join if the user was redirected here from a join link
        const pendingJoin = localStorage.getItem('sta_pending_join')
        if (pendingJoin) {
          localStorage.removeItem('sta_pending_join')
          navigate(pendingJoin, { replace: true })
        } else {
          navigate('/', { replace: true })
        }
      })
      .catch(() => {
        setError('Sign-in failed — please try again.')
        setTimeout(() => navigate('/login', { replace: true }), 2000)
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen text-red-400 text-sm">
        {error}
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-screen gap-2 text-slate-400 text-sm">
      <Spinner className="w-4 h-4" /> Signing you in…
    </div>
  )
}
