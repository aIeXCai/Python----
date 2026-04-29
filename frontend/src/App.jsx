import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext.jsx'
import { ChatProvider } from './contexts/ChatContext.jsx'
import FloatingChat from './components/FloatingChat.jsx'
import Login from './pages/auth/Login.jsx'
import TeacherLogin from './pages/auth/TeacherLogin.jsx'
import CourseSelect from './pages/student/CourseSelect.jsx'
import StudentDashboard from './pages/student/StudentDashboard.jsx'
import QuizPage from './pages/student/info/QuizPage.jsx'
import QuizResult from './pages/student/info/QuizResult.jsx'
import TeacherDashboard from './pages/teacher/TeacherDashboard.jsx'
import StudentManagement from './pages/teacher/StudentManagement.jsx'
import InfoAdmin from './pages/teacher/InfoAdmin.jsx'
import AiAdmin from './pages/teacher/aiAdmin.jsx'
import ProblemDetail from './pages/student/ai/ProblemDetail.jsx'
import './index.css'

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" replace />
  return children
}

/** 学生端布局包裹：权限 + 聊天 */
function StudentLayout() {
  return (
    <ProtectedRoute>
      <ChatProvider>
        <Outlet />
        <FloatingChat />
      </ChatProvider>
    </ProtectedRoute>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* 登录入口 */}
          <Route path="/login" element={<Login />} />
          <Route path="/teacher-login" element={<TeacherLogin />} />

          {/* 学生端 — 含 AI 助手（Dashboard / AI课题目 / 选课） */}
          <Route element={<StudentLayout />}>
            <Route path="/course-select" element={<CourseSelect />} />
            <Route path="/problem/:problemId" element={<ProblemDetail />} />
            <Route path="/student/dashboard" element={<StudentDashboard />} />
          </Route>

          {/* 信息科技课 — 小测 / 成绩页，不提供 AI 助手 */}
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
            path="/teacher/ai"
            element={
              <ProtectedRoute>
                <AiAdmin />
              </ProtectedRoute>
            }
          />
          <Route
            path="/teacher/info"
            element={
              <ProtectedRoute>
                <InfoAdmin />
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
