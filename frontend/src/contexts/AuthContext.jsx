import { createContext, useContext, useState, useEffect } from 'react'
import { login as apiLogin, logout as apiLogout, getCurrentUser } from '../api/index.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const u = getCurrentUser()
    if (u && u.user_id) {
      setUser({ username: u.username, role: u.role })
    }
    setLoading(false)
  }, [])

  const login = async (username, password) => {
    await apiLogin(username, password)
    const u = getCurrentUser()
    setUser({ username: u.username, role: u.role })
  }

  const logout = () => {
    apiLogout()
    setUser(null)
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
