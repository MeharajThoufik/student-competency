import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './auth/guards'
import { Layout } from './components/Layout'
import { Academics } from './pages/Academics'
import { Activities } from './pages/Activities'
import { ActivityForm } from './pages/ActivityForm'
import { Consent } from './pages/Consent'
import { Dashboard } from './pages/Dashboard'
import { Landing } from './pages/Landing'
import { Login } from './pages/Login'
import { Profile } from './pages/Profile'
import { SkillsInterests } from './pages/SkillsInterests'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/consent" element={<Consent />} />
        <Route
          path="/app"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="activities" element={<Activities />} />
          <Route path="activities/new" element={<ActivityForm />} />
          <Route path="activities/:id" element={<ActivityForm />} />
          <Route path="academics" element={<Academics />} />
          <Route path="skills" element={<SkillsInterests />} />
          <Route path="profile" element={<Profile />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
