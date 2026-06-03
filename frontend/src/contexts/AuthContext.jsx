import { createContext, useContext, useEffect, useState } from 'react'

const AuthContext = createContext(null)

const TOKEN_KEY = 'sta_auth_token'
const API_BASE  = (import.meta.env.VITE_API_URL ?? '') + '/api'

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  // Restore session from localStorage on mount
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) { setLoading(false); return }

    fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => (r.ok ? r.json() : null))
      .then(u => { setUser(u); setLoading(false) })
      .catch(() => { localStorage.removeItem(TOKEN_KEY); setLoading(false) })
  }, [])

  async function loginWithToken(token) {
    localStorage.setItem(TOKEN_KEY, token)
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) {
      localStorage.removeItem(TOKEN_KEY)
      throw new Error('Token rejected by server')
    }
    const u = await res.json()
    setUser(u)
    return u
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, loginWithToken, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
