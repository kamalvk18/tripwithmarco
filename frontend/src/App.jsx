import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import Home from '@/pages/Home'
import PlanTrip from '@/pages/PlanTrip'
import TripView from '@/pages/TripView'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/"             element={<Home />} />
          <Route path="/plan"         element={<PlanTrip />} />
          <Route path="/trips/:id"    element={<TripView />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
