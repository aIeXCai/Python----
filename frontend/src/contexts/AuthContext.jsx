import { createContext, useContext, useState, useEffect } from 'react'
import { login as apiLogin, logout as apiLogout, getCurrentUser } from '../api/index.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const u = getCurrentUser()
    if (u && u.user_id) {
      setUser({
        username: u.username, role: u.role,
        managed_grade: u.managed_grade, is_superuser: u.is_superuser,
      })
    }
    setLoading(false)
  }, [])

  const login = async (username, password, grade, class_num, student_number) => {
    await apiLogin(username, password, grade, class_num, student_number)
    const u = getCurrentUser()
    setUser({
      username: u.username, role: u.role,
      managed_grade: u.managed_grade, is_superuser: u.is_superuser,
    })
  }

  const logout = async () => {
    try {
      await apiLogout()
    } finally {
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
