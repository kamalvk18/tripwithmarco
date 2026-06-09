import { useState } from 'react'
import { Globe } from 'lucide-react'

export default function Login() {
  const [loading, setLoading] = useState(false)

  async function handleLogin(e) {
    e.preventDefault()
    if (loading) return
    setLoading(true)
    try {
      const base = import.meta.env.VITE_API_URL ?? ''
      const res  = await fetch(`${base}/api/auth/google/login-url`)
      if (!res.ok) throw new Error('failed')
      const { url } = await res.json()
      window.location.href = url
    } catch {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen w-full bg-gradient-to-br from-indigo-50 via-white to-sky-50 px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2.5 mb-8">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center shadow-md">
            <Globe className="text-white" size={20} />
          </div>
          <span className="text-xl font-bold text-slate-800 tracking-tight">
            Marco
          </span>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-lg">
          <h1 className="text-lg font-bold text-slate-800 mb-1">Welcome back</h1>
          <p className="text-sm text-slate-500 mb-8">
            Sign in to plan trips with Marco, your AI travel companion.
          </p>

          <a
            href={`${import.meta.env.VITE_API_URL ?? ''}/api/auth/google/login`}
            onClick={handleLogin}
            className="flex items-center justify-center gap-3 w-full rounded-xl
              bg-white text-slate-700 font-medium text-sm px-4 py-3
              border border-slate-200 shadow-sm hover:bg-slate-50 hover:shadow-md transition-all
              aria-disabled:opacity-60 aria-disabled:cursor-not-allowed"
            aria-disabled={loading}
          >
            {loading ? (
              <svg className="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
                <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/>
                <path d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
                <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
              </svg>
            )}
            {loading ? 'Redirecting to Google…' : 'Continue with Google'}
          </a>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">
          Your trips are private and only visible to you.
        </p>
      </div>
    </div>
  )
}
