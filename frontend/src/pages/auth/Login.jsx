import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GraduationCap, User, Lock, UserPlus, Layers, Users, Hash, Eye, EyeOff, AlertCircle } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { register } from '../../api/index.js'
import { GRADES } from '../../constants/grades.js'

export default function Login() {
  const [isRegister, setIsRegister] = useState(false)
  const [loading, setLoading] = useState(false)
  const [globalError, setGlobalError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const { login: authLogin } = useAuth()
  const navigate = useNavigate()

  const [loginForm, setLoginForm] = useState({
    grade: '', class_num: '', display_name: '', student_number: '', password: '',
  })

  const [regForm, setRegForm] = useState({
    grade: '', class_num: '', display_name: '', student_number: '',
    password: '', confirmPassword: '',
  })

  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const setL = (key) => (e) => setLoginForm((f) => ({ ...f, [key]: e.target.value }))
  const setR = (key) => (e) => setRegForm((f) => ({ ...f, [key]: e.target.value }))

  const grades = GRADES
  const classOptions = Array.from({ length: 20 }, (_, i) => i + 1)
  const studentNumberOptions = Array.from({ length: 50 }, (_, i) => i + 1)

  const clearErrors = () => {
    setGlobalError('')
    setFieldErrors({})
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    clearErrors()
    const fe = {}
    if (!loginForm.grade) fe.grade = '请选择年级'
    if (!loginForm.class_num) fe.class_num = '请选择班级'
    if (!loginForm.display_name) fe.display_name = '请输入姓名'
    if (!loginForm.student_number) fe.student_number = '请选择学号'
    if (!loginForm.password) fe.password = '请输入密码'
    if (Object.keys(fe).length) { setFieldErrors(fe); return }
    if (loading) return
    setLoading(true)
    try {
      await authLogin('', loginForm.password, loginForm.grade, loginForm.class_num, loginForm.student_number)
      navigate('/course-select')
    } catch (err) {
      const msg = err.message || ''
      if (msg.includes('找不到') || msg.includes('不存在')) {
        setFieldErrors({ student_number: '找不到该年级班级学号的学生，请检查或先注册' })
      } else if (msg.includes('密码')) {
        setFieldErrors({ password: '密码错误，请重新输入' })
      } else {
        setGlobalError(msg || '登录失败，请稍后重试')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    clearErrors()
    const fe = {}
    if (!regForm.grade) fe.grade = '请选择年级'
    if (!regForm.class_num) fe.class_num = '请选择班级'
    if (!regForm.display_name) fe.display_name = '请输入姓名'
    if (!regForm.student_number) fe.student_number = '请选择学号'
    if (!regForm.password) fe.password = '请输入密码'
    if (!regForm.confirmPassword) fe.confirmPassword = '请再次输入密码'
    if (Object.keys(fe).length) { setFieldErrors(fe); return }
    if (regForm.password !== regForm.confirmPassword) {
      setFieldErrors({ confirmPassword: '两次输入的密码不一致' })
      return
    }
    if (loading) return
    setLoading(true)
    try {
      const regData = await register({
        display_name: regForm.display_name,
        password: regForm.password,
        grade: regForm.grade,
        class_num: regForm.class_num,
        student_number: regForm.student_number,
        role: 'student',
      })
      localStorage.setItem('token', regData.token)
      localStorage.setItem('user', JSON.stringify(regData.user))
      navigate('/course-select')
    } catch (err) {
      const msg = err.message || ''
      if (msg.includes('學號') || msg.includes('学号')) {
        setFieldErrors({ student_number: msg })
      } else {
        setGlobalError(msg || '注册失败，请稍后重试')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-bg-grid" />

      <div className="main-container">
        <div className="header">
          <h1><GraduationCap size={38} /> Python 学习平台</h1>
          <p className="subtitle">开启你的程序设计之旅</p>
        </div>

        {/* ── 登录表单 ── */}
        {!isRegister && (
          <div className="form-card">
            <div className="form-header">
              <h2><GraduationCap size={22} /> 学生登录</h2>
              <p>欢迎回到学习平台！请输入你的学习资讯</p>
            </div>

            <form onSubmit={handleLogin} noValidate>
              {/* 年级 */}
              <div className={`form-group ${fieldErrors.grade ? 'has-error' : ''}`}>
                <label>年级</label>
                <div className="input-wrapper">
                  <Layers size={16} />
                  <select value={loginForm.grade} onChange={setL('grade')}>
                    <option value="">请选择年级</option>
                    {grades.map((g) => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>
                {fieldErrors.grade && <div className="field-error"><AlertCircle size={12} />{fieldErrors.grade}</div>}
              </div>

              {/* 班级 */}
              <div className={`form-group ${fieldErrors.class_num ? 'has-error' : ''}`}>
                <label>班级</label>
                <div className="input-wrapper">
                  <Users size={16} />
                  <select value={loginForm.class_num} onChange={setL('class_num')}>
                    <option value="">请选择班级</option>
                    {classOptions.map((c) => <option key={c} value={String(c)}>{c}班</option>)}
                  </select>
                </div>
                {fieldErrors.class_num && <div className="field-error"><AlertCircle size={12} />{fieldErrors.class_num}</div>}
              </div>

              {/* 姓名 */}
              <div className={`form-group ${fieldErrors.display_name ? 'has-error' : ''}`}>
                <label>姓名</label>
                <div className="input-wrapper">
                  <User size={16} />
                  <input
                    type="text"
                    placeholder="请输入你的真实姓名"
                    value={loginForm.display_name}
                    onChange={setL('display_name')}
                    autoComplete="off"
                  />
                </div>
                {fieldErrors.display_name && <div className="field-error"><AlertCircle size={12} />{fieldErrors.display_name}</div>}
              </div>

              {/* 学号 */}
              <div className={`form-group ${fieldErrors.student_number ? 'has-error' : ''}`}>
                <label>学号</label>
                <div className="input-wrapper">
                  <Hash size={16} />
                  <select value={loginForm.student_number} onChange={setL('student_number')}>
                    <option value="">请选择学号（1-50）</option>
                    {studentNumberOptions.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
                {fieldErrors.student_number && <div className="field-error"><AlertCircle size={12} />{fieldErrors.student_number}</div>}
              </div>

              {/* 密码 */}
              <div className={`form-group ${fieldErrors.password ? 'has-error' : ''}`}>
                <label>密码</label>
                <div className="input-wrapper" style={{ position: 'relative' }}>
                  <Lock size={16} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="请输入密码"
                    value={loginForm.password}
                    onChange={setL('password')}
                    style={{ paddingRight: 40 }}
                    autoComplete="current-password"
                  />
                  <span
                    onClick={() => setShowPassword(p => !p)}
                    style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', color: 'rgba(255,255,255,0.4)' }}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </span>
                </div>
                {fieldErrors.password && <div className="field-error"><AlertCircle size={12} />{fieldErrors.password}</div>}
              </div>

              {globalError && (
                <div className="global-error">
                  <AlertCircle size={15} />
                  {globalError}
                </div>
              )}

              <button type="submit" className={`btn btn-primary ${loading ? 'loading' : ''}`} disabled={loading}>
                {loading ? '登录中...' : '登录学习'}
              </button>
            </form>

            <div className="toggle-section">
              <p>还没有帐号？<span className="toggle-link" onClick={() => { setIsRegister(true); clearErrors() }}>立即注册</span></p>
            </div>
            <div className="toggle-section" style={{ marginTop: 12, borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 12 }}>
              <p>教师？<span className="toggle-link" onClick={() => navigate('/teacher-login')}>教师登录</span></p>
            </div>
          </div>
        )}

        {/* ── 注册表单 ── */}
        {isRegister && (
          <div className="form-card">
            <div className="form-header">
              <h2><UserPlus size={22} /> 学生注册</h2>
              <p>加入我们的学习平台，开始你的程序设计之旅！</p>
            </div>

            <form onSubmit={handleRegister} noValidate>
              {/* 年级 */}
              <div className={`form-group ${fieldErrors.grade ? 'has-error' : ''}`}>
                <label>年级</label>
                <div className="input-wrapper">
                  <Layers size={16} />
                  <select value={regForm.grade} onChange={setR('grade')}>
                    <option value="">请选择年级</option>
                    {grades.map((g) => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>
                {fieldErrors.grade && <div className="field-error"><AlertCircle size={12} />{fieldErrors.grade}</div>}
              </div>

              {/* 班级 */}
              <div className={`form-group ${fieldErrors.class_num ? 'has-error' : ''}`}>
                <label>班级</label>
                <div className="input-wrapper">
                  <Users size={16} />
                  <select value={regForm.class_num} onChange={setR('class_num')}>
                    <option value="">请选择班级</option>
                    {classOptions.map((c) => <option key={c} value={String(c)}>{c}班</option>)}
                  </select>
                </div>
                {fieldErrors.class_num && <div className="field-error"><AlertCircle size={12} />{fieldErrors.class_num}</div>}
              </div>

              {/* 姓名 */}
              <div className={`form-group ${fieldErrors.display_name ? 'has-error' : ''}`}>
                <label>姓名</label>
                <div className="input-wrapper">
                  <User size={16} />
                  <input
                    type="text"
                    placeholder="请输入你的真实姓名"
                    value={regForm.display_name}
                    onChange={setR('display_name')}
                    autoComplete="off"
                  />
                </div>
                {fieldErrors.display_name && <div className="field-error"><AlertCircle size={12} />{fieldErrors.display_name}</div>}
              </div>

              {/* 学号 */}
              <div className={`form-group ${fieldErrors.student_number ? 'has-error' : ''}`}>
                <label>学号</label>
                <div className="input-wrapper">
                  <Hash size={16} />
                  <select value={regForm.student_number} onChange={setR('student_number')}>
                    <option value="">请选择学号（1-50）</option>
                    {studentNumberOptions.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </div>
                {fieldErrors.student_number && <div className="field-error"><AlertCircle size={12} />{fieldErrors.student_number}</div>}
              </div>

              {/* 密码 */}
              <div className={`form-group ${fieldErrors.password ? 'has-error' : ''}`}>
                <label>密码</label>
                <div className="input-wrapper" style={{ position: 'relative' }}>
                  <Lock size={16} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="请设置登录密码"
                    value={regForm.password}
                    onChange={setR('password')}
                    style={{ paddingRight: 40 }}
                    autoComplete="new-password"
                  />
                  <span
                    onClick={() => setShowPassword(p => !p)}
                    style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', color: 'rgba(255,255,255,0.4)' }}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </span>
                </div>
                {fieldErrors.password && <div className="field-error"><AlertCircle size={12} />{fieldErrors.password}</div>}
              </div>

              {/* 确认密码 */}
              <div className={`form-group ${fieldErrors.confirmPassword ? 'has-error' : ''}`}>
                <label>确认密码</label>
                <div className="input-wrapper" style={{ position: 'relative' }}>
                  <Lock size={16} />
                  <input
                    type={showConfirm ? 'text' : 'password'}
                    placeholder="请再次输入密码"
                    value={regForm.confirmPassword}
                    onChange={setR('confirmPassword')}
                    style={{ paddingRight: 40 }}
                    autoComplete="new-password"
                  />
                  <span
                    onClick={() => setShowConfirm(p => !p)}
                    style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', cursor: 'pointer', color: 'rgba(255,255,255,0.4)' }}
                  >
                    {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                  </span>
                </div>
                {fieldErrors.confirmPassword && <div className="field-error"><AlertCircle size={12} />{fieldErrors.confirmPassword}</div>}
              </div>

              {globalError && (
                <div className="global-error">
                  <AlertCircle size={15} />
                  {globalError}
                </div>
              )}

              <button type="submit" className={`btn btn-secondary ${loading ? 'loading' : ''}`} disabled={loading}>
                {loading ? '注册中...' : '开始学习'}
              </button>
            </form>

            <div className="toggle-section">
              <p>已有账号？<span className="toggle-link" onClick={() => { setIsRegister(false); clearErrors() }}>返回登录</span></p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
