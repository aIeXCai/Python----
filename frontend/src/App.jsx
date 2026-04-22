import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext.jsx'
import Login from './pages/auth/Login.jsx'
import TeacherLogin from './pages/auth/TeacherLogin.jsx'
import CourseSelect from './pages/student/CourseSelect.jsx'
import StudentDashboard from './pages/student/StudentDashboard.jsx'
import QuizPage from './pages/student/QuizPage.jsx'
import QuizResult from './pages/student/QuizResult.jsx'
import TeacherDashboard from './pages/teacher/TeacherDashboard.jsx'
import StudentManagement from './pages/teacher/StudentManagement.jsx'
import ScoreManagement from './pages/teacher/ScoreManagement.jsx'
import ProblemManagement from './pages/teacher/ProblemManagement.jsx'
import ProblemDetail from './pages/ProblemDetail.jsx'
import './index.css'

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* 登录入口 */}
          <Route path="/login" element={<Login />} />
          <Route path="/teacher-login" element={<TeacherLogin />} />

          {/* 选课页 */}
          <Route
            path="/course-select"
            element={
              <ProtectedRoute>
                <CourseSelect />
              </ProtectedRoute>
            }
          />

          {/* 学生端 */}
          <Route
            path="/problem/:problemId"
            element={
              <ProtectedRoute>
                <ProblemDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/dashboard"
            element={
              <ProtectedRoute>
                <StudentDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/quiz/:sessionId"
            element={
              <ProtectedRoute>
                <QuizPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/student/quiz-result/:sessionId"
            element={
              <ProtectedRoute>
                <QuizResult />
              </ProtectedRoute>
            }
          />

          {/* 老师端 */}
          <Route
            path="/teacher/dashboard"
            element={
              <ProtectedRoute>
                <TeacherDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/teacher/students"
            element={
              <ProtectedRoute>
                <StudentManagement />
              </ProtectedRoute>
            }
          />
          <Route
            path="/teacher/scores"
            element={
              <ProtectedRoute>
                <ScoreManagement />
              </ProtectedRoute>
            }
          />
          <Route
            path="/teacher/problems"
            element={
              <ProtectedRoute>
                <ProblemManagement />
              </ProtectedRoute>
            }
          />

          {/* 默认跳转 */}
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
