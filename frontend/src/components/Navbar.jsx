import { Link, useNavigate } from 'react-router-dom'
import { LogOut, GraduationCap } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function Navbar({ username, grade, class_num }) {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="navbar">
      <div className="nav-container">
        <Link to="/course-select" className="nav-brand">
          <GraduationCap size={32} />
          <span>AI 學習平台</span>
        </Link>
        <div className="nav-info">
          <div className="user-info">
            <span className="username">{username}</span>
            {grade && class_num && (
              <span className="grade-info">{grade} {class_num}班</span>
            )}
          </div>
          <button onClick={handleLogout} className="logout-btn">
            <LogOut size={16} />
            登出
          </button>
        </div>
      </div>
    </nav>
  )
}
