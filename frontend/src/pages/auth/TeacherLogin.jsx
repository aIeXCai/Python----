import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GraduationCap, User, Lock, Briefcase, ArrowLeft } from 'lucide-react'
import { login } from '../../api/index.js'

export default function TeacherLogin() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const setF = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!form.username || !form.password) {
      setError('请填写用户名和密码')
      return
    }
    setLoading(true)
    setError('')
    try {
      const body = { username: form.username, password: form.password }
      const res = await fetch('http://localhost:8080/api/auth/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || '登入失败')

      localStorage.setItem('token', data.token)
      if (data.user) {
        localStorage.setItem('user', JSON.stringify(data.user))
      }

      navigate('/teacher/dashboard')
    } catch (err) {
      setError(err.message || '登入失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-bg-grid" />

      <a
        onClick={() => navigate('/login')}
        style={{
          position: 'fixed', top: 24, left: 24,
          display: 'flex', alignItems: 'center', gap: 6,
          color: 'rgba(255,255,255,0.4)', cursor: 'pointer',
          fontSize: 13, textDecoration: 'none', zIndex: 10,
        }}
      >
        <ArrowLeft size={14} />
        返回学生登入
      </a>

      <div className="main-container">
        <div className="header">
          <h1><GraduationCap size={38} /> Python 学习平台</h1>
          <p className="subtitle">老师后台管理</p>
        </div>

        <div className="form-card">
          <div className="form-header">
            <h2><Briefcase size={22} /> 老师登入</h2>
            <p>管理学生和课程内容</p>
          </div>

          {error && <div className="error-msg">{error}</div>}

          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>用户名</label>
              <div className="input-wrapper">
                <User size={16} />
                <input
                  type="text"
                  placeholder="请输入用户名"
                  value={form.username}
                  onChange={setF('username')}
                  autoComplete="username"
                />
              </div>
            </div>

            <div className="form-group">
              <label>密码</label>
              <div className="input-wrapper">
                <Lock size={16} />
                <input
                  type="password"
                  placeholder="请输入密码"
                  value={form.password}
                  onChange={setF('password')}
                  autoComplete="current-password"
                />
              </div>
            </div>

            <button
              type="submit"
              className={`btn btn-primary ${loading ? 'loading' : ''}`}
              disabled={loading}
            >
              {loading ? '登入中...' : '老师登入'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
