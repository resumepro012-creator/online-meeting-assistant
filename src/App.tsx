import { Routes, Route } from 'react-router-dom'
import { ProtectedRoute } from '@/components/layout/ProtectedRoute'

import Landing from '@/pages/Landing'
import SignIn from '@/pages/SignIn'
import SignUp from '@/pages/SignUp'
import ForgotPassword from '@/pages/ForgotPassword'
import VerifyEmail from '@/pages/VerifyEmail'
import ResetPassword from '@/pages/ResetPassword'
import Dashboard from '@/pages/Dashboard'
import JoinClass from '@/pages/JoinClass'
import Processing from '@/pages/Processing'
import LectureResults from '@/pages/LectureResults'
import MyClasses from '@/pages/MyClasses'
import LectureNotes from '@/pages/LectureNotes'
import Announcements from '@/pages/Announcements'
import Settings from '@/pages/Settings'
import NotFound from '@/pages/NotFound'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/sign-in" element={<SignIn />} />
      <Route path="/sign-up" element={<SignUp />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/join-class"
        element={
          <ProtectedRoute>
            <JoinClass />
          </ProtectedRoute>
        }
      />
      <Route
        path="/processing/:classId"
        element={
          <ProtectedRoute>
            <Processing />
          </ProtectedRoute>
        }
      />
      <Route
        path="/lecture-results/:classId"
        element={
          <ProtectedRoute>
            <LectureResults />
          </ProtectedRoute>
        }
      />
      <Route
        path="/my-classes"
        element={
          <ProtectedRoute>
            <MyClasses />
          </ProtectedRoute>
        }
      />
      <Route
        path="/lecture-notes"
        element={
          <ProtectedRoute>
            <LectureNotes />
          </ProtectedRoute>
        }
      />
      <Route
        path="/announcements"
        element={
          <ProtectedRoute>
            <Announcements />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
