import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { Layout } from '@/components/Layout'
import Home from '@/pages/Home'
import PlanTrip from '@/pages/PlanTrip'
import TripView from '@/pages/TripView'
import Login from '@/pages/Login'
import AuthCallback from '@/pages/AuthCallback'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes — no layout */}
          <Route path="/login"         element={<Login />} />
          <Route path="/auth/callback" element={<AuthCallback />} />

          {/* Protected routes — inside sidebar layout */}
          <Route path="/*" element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route index           element={<Home />} />
                  <Route path="plan"     element={<PlanTrip />} />
                  <Route path="trips/:id" element={<TripView />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          } />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
