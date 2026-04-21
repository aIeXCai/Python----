import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GraduationCap, User, Lock, UserPlus } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext.jsx'
import { login, register } from '../api/index.js'

export default function Login() {
  const [isRegister, setIsRegister] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { login: authLogin } = useAuth()
  const navigate = useNavigate()

  // Form state
  const [form, setForm] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    grade: '',
    class_num: '',
    student_number: '',
  })

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!form.username || !form.password) {
      setError('請填寫用戶名和密碼')
      return
    }
    setLoading(true)
    setError('')
    try {
      await authLogin(form.username, form.password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || '登入失敗')
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    if (!form.username || !form.password) {
      setError('請填寫所有必填欄位')
      return
    }
    if (form.password !== form.confirmPassword) {
      setError('密碼與確認密碼不一致')
      return
    }
    setLoading(true)
    setError('')
    try {
      await register({
        username: form.username,
        password: form.password,
        grade: form.grade,
        class_num: form.class_num,
        role: 'student',
      })
      // Auto login after register
      await authLogin(form.username, form.password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message || '註冊失敗')
    } finally {
      setLoading(false)
    }
  }

  const grades = ['七年級', '八年級', '九年級', '高一', '高二', '高三']
  const classOptions = Array.from({ length: 20 }, (_, i) => i + 1)

  return (
    <div className="login-page">
      <div className="login-bg-grid" />

      <div className="main-container">
        <div className="header">
          <h1>
            <GraduationCap size={40} />
            AI 學習平台
          </h1>
          <p className="subtitle">開啟你的程式設計之旅</p>
        </div>

        <div className="form-card">
          <div className="form-header">
            <h2>
              {isRegister ? <UserPlus size={24} /> : <GraduationCap size={24} />}
              {isRegister ? '學生註冊' : '學生登入'}
            </h2>
            <p>{isRegister ? '加入我們的學習平台，開始你的 AI 學習之旅！' : '歡迎回到學習平台！請輸入你的學習資訊'}</p>
          </div>

          {error && <div className="error-msg">{error}</div>}

          <form onSubmit={isRegister ? handleRegister : handleLogin}>
            {/* 登入：用户名 + 密码 */}
            {!isRegister && (
              <>
                <div className="form-group">
                  <label>用戶名</label>
                  <div className="input-wrapper">
                    <User size={16} />
                    <input
                      type="text"
                      placeholder="請輸入用戶名"
                      value={form.username}
                      onChange={set('username')}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>密碼</label>
                  <div className="input-wrapper">
                    <Lock size={16} />
                    <input
                      type="password"
                      placeholder="請輸入密碼"
                      value={form.password}
                      onChange={set('password')}
                    />
                  </div>
                </div>
              </>
            )}

            {/* 註冊：全部字段 */}
            {isRegister && (
              <>
                <div className="form-group">
                  <label>年級</label>
                  <div className="input-wrapper">
                    <select value={form.grade} onChange={set('grade')}>
                      <option value="">請選擇年級</option>
                      {grades.map((g) => <option key={g} value={g}>{g}</option>)}
                    </select>
                  </div>
                </div>
                <div className="form-group">
                  <label>班級</label>
                  <div className="input-wrapper">
                    <select value={form.class_num} onChange={set('class_num')}>
                      <option value="">請選擇班級</option>
                      {classOptions.map((c) => <option key={c} value={c}>{c}班</option>)}
                    </select>
                  </div>
                </div>
                <div className="form-group">
                  <label>姓名</label>
                  <div className="input-wrapper">
                    <User size={16} />
                    <input
                      type="text"
                      placeholder="請輸入真實姓名"
                      value={form.username}
                      onChange={set('username')}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>學號</label>
                  <div className="input-wrapper">
                    <select value={form.student_number} onChange={set('student_number')}>
                      <option value="">請選擇學號（1-50）</option>
                      {Array.from({ length: 50 }, (_, i) => i + 1).map((n) => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="form-group">
                  <label>密碼</label>
                  <div className="input-wrapper">
                    <Lock size={16} />
                    <input
                      type="password"
                      placeholder="請設定登入密碼"
                      value={form.password}
                      onChange={set('password')}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>確認密碼</label>
                  <div className="input-wrapper">
                    <Lock size={16} />
                    <input
                      type="password"
                      placeholder="請再次輸入密碼"
                      value={form.confirmPassword}
                      onChange={set('confirmPassword')}
                    />
                  </div>
                </div>
              </>
            )}

            <button type="submit" className={`btn btn-primary ${loading ? 'loading' : ''}`} disabled={loading}>
              {loading ? '處理中...' : isRegister ? '開始學習' : '登入學習'}
            </button>
          </form>

          <div className="toggle-section">
            <p>
              {isRegister ? '已有帳號？' : '還沒有帳號？'}
              <span className="toggle-link" onClick={() => { setIsRegister(!isRegister); setError('') }}>
                {isRegister ? '返回登入' : '立即註冊'}
              </span>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
