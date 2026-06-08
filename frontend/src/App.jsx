import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { Layout } from '@/components/Layout'
import Home from '@/pages/Home'
import PlanTrip from '@/pages/PlanTrip'
import TripView from '@/pages/TripView'
import Login from '@/pages/Login'
import AuthCallback from '@/pages/AuthCallback'
import AdminDashboard from '@/pages/AdminDashboard'
import JoinTrip from '@/pages/JoinTrip'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes — no auth, no layout */}
          <Route path="/login"         element={<Login />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/join/:token"   element={<JoinTrip />} />

          {/* Protected routes — inside sidebar layout */}
          <Route path="/*" element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route index            element={<Home />} />
                  <Route path="plan"      element={<PlanTrip />} />
                  <Route path="trips/:id" element={<TripView />} />
                  <Route path="admin"     element={<AdminDashboard />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          } />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
