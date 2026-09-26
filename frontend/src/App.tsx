import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from './auth/guards'
import { RequireRole } from './components/educator'
import { Layout } from './components/Layout'
import { Academics } from './pages/Academics'
import { Admin } from './pages/admin/Admin'
import { Cohort } from './pages/educator/Cohort'
import { LearnerDetail } from './pages/educator/LearnerDetail'
import { Learners } from './pages/educator/Learners'
import { ReviewQueue } from './pages/educator/ReviewQueue'
import { Activities } from './pages/Activities'
import { ActivityForm } from './pages/ActivityForm'
import { Consent } from './pages/Consent'
import { Dashboard } from './pages/Dashboard'
import { Growth } from './pages/Growth'
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
          <Route path="growth" element={<Growth />} />
          <Route path="activities" element={<Activities />} />
          <Route path="activities/new" element={<ActivityForm />} />
          <Route path="activities/:id" element={<ActivityForm />} />
          <Route path="academics" element={<Academics />} />
          <Route path="skills" element={<SkillsInterests />} />
          <Route path="profile" element={<Profile />} />
          <Route path="educator/queue" element={<RequireRole roles={['educator', 'admin']}><ReviewQueue /></RequireRole>} />
          <Route path="educator/learners" element={<RequireRole roles={['educator', 'admin']}><Learners /></RequireRole>} />
          <Route path="educator/learners/:id" element={<RequireRole roles={['educator', 'admin']}><LearnerDetail /></RequireRole>} />
          <Route path="educator/cohort" element={<RequireRole roles={['educator', 'admin']}><Cohort /></RequireRole>} />
          <Route path="admin" element={<RequireRole roles={['admin']}><Admin /></RequireRole>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
