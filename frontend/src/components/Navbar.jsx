import { Link, useNavigate } from 'react-router-dom'
import { LogOut, Sparkles } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext.jsx'

export default function Navbar({ username, grade, class_num }) {
  const { logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    try {
      await logout()
    } finally {
      navigate('/login')
    }
  }

  return (
    <nav className="navbar">
      <div className="nav-container">
        <Link to="/course-select" className="nav-brand">
          <Sparkles size={30} />
          <span>白省修仙传</span>
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
