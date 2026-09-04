import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Users, Trash2, Search, RefreshCw, Edit2, X } from 'lucide-react'
import { API_BASE_URL } from '../../api/config.js'
import {
  generateStudentTemporaryPassword,
  resetStudentPassword,
  revealStudentPassword,
} from '../../api/index.js'
import { GRADES } from '../../constants/grades.js'

const API = API_BASE_URL
const grades = GRADES

export default function StudentManagement() {
  const navigate = useNavigate()
  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ grade: '', class_num: '', search: '' })
  const [filtered, setFiltered] = useState([])
  const [sortConfig, setSortConfig] = useState({ field: 'student_number', order: 'asc' })

  // 编辑弹窗
  const [editModal, setEditModal] = useState({ open: false, student: null })
  const [editForm, setEditForm] = useState({})
  const [editSaving, setEditSaving] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [passwordSaving, setPasswordSaving] = useState(false)

  // 同时只在当前组件内存中短时保存一个学生密码。
  const [revealedPassword, setRevealedPassword] = useState(null)
  const passwordTimerRef = useRef(null)

  const token = localStorage.getItem('token')
  const headers = { 'Authorization': `Token ${token}`, 'Content-Type': 'application/json' }

  useEffect(() => { loadStudents() }, [])

  useEffect(() => () => {
    if (passwordTimerRef.current) clearTimeout(passwordTimerRef.current)
    passwordTimerRef.current = null
  }, [])

  useEffect(() => {
    let result = [...students]
    if (filters.search) {
      const q = filters.search.toLowerCase()
      result = result.filter(s =>
        (s.display_name || s.username || '').toLowerCase().includes(q) ||
        String(s.student_number || '').includes(q)
      )
    }
    if (filters.grade) result = result.filter(s => s.grade === filters.grade)
    if (filters.class_num) result = result.filter(s => String(s.class_num) === filters.class_num)
    setFiltered(result)
  }, [filters, students])

  const loadStudents = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/ai/admin/students/?sort_by=${sortConfig.field}&order=${sortConfig.order}`, { headers })
      if (res.ok) setStudents(await res.json())
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  // ---------- 密码显示/隐藏 ----------
  const clearRevealedPassword = () => {
    if (passwordTimerRef.current) clearTimeout(passwordTimerRef.current)
    passwordTimerRef.current = null
    setRevealedPassword(null)
  }

  const showPasswordTemporarily = (studentId, password, seconds = 30) => {
    clearRevealedPassword()
    setRevealedPassword({ studentId, password, seconds })
    passwordTimerRef.current = setTimeout(() => {
      setRevealedPassword(null)
      passwordTimerRef.current = null
    }, seconds * 1000)
  }

  const togglePassword = async (student) => {
    if (revealedPassword?.studentId === student.id) {
      clearRevealedPassword()
      return
    }
    if (!student.password_available) {
      alert('该学生密码不可查看，请先重置密码。')
      return
    }
    if (!window.confirm('查看操作将被记录，请仅用于帮助该学生登录。')) return
    try {
      const data = await revealStudentPassword(student.id)
      showPasswordTemporarily(student.id, data.password, data.display_seconds)
    } catch (e) {
      clearRevealedPassword()
      alert(e.message || '密码查看失败')
    }
  }

  // ---------- 编辑 ----------
  const openEdit = (student) => {
    setEditForm({
      username: student.username || '',
      display_name: student.display_name || '',
      grade: student.grade || '',
      class_num: student.class_num || '',
      student_number: student.student_number || '',
    })
    setNewPassword('')
    clearRevealedPassword()
    setEditModal({ open: true, student })
  }

  const closeEdit = () => {
    clearRevealedPassword()
    setNewPassword('')
    setEditModal({ open: false, student: null })
  }

  const saveEdit = async () => {
    setEditSaving(true)
    try {
      const payload = { ...editForm }
      const res = await fetch(`${API}/auth/${editModal.student.id}/`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        const data = await res.json()
        setStudents(prev => prev.map(s => s.id === editModal.student.id ? {
          ...s,
          username: data.student.username,
          display_name: data.student.display_name,
          grade: data.student.grade,
          class_num: data.student.class_num,
          student_number: data.student.student_number,
        } : s))
        closeEdit()
      } else {
        const err = await res.json()
        alert('更新失败：' + (err.error || err.detail || JSON.stringify(err)))
      }
    } catch (e) { alert('更新失败：' + e.message) }
    setEditSaving(false)
  }

  const markPasswordAvailable = (studentId) => {
    setStudents(prev => prev.map(student => (
      student.id === studentId ? { ...student, password_available: true } : student
    )))
  }

  const handleManualPasswordReset = async () => {
    if (!newPassword) {
      alert('请输入至少 8 位的新密码。')
      return
    }
    setPasswordSaving(true)
    try {
      const data = await resetStudentPassword(editModal.student.id, newPassword)
      setNewPassword('')
      markPasswordAvailable(editModal.student.id)
      clearRevealedPassword()
      alert(data.message)
    } catch (e) {
      alert(e.message || '密码重置失败')
    } finally {
      setPasswordSaving(false)
    }
  }

  const handleGeneratedPassword = async () => {
    if (!window.confirm('确定生成并应用新的随机临时密码吗？学生原登录会立即失效。')) return
    setPasswordSaving(true)
    try {
      const data = await generateStudentTemporaryPassword(editModal.student.id)
      markPasswordAvailable(editModal.student.id)
      showPasswordTemporarily(
        editModal.student.id,
        data.temporary_password,
        data.display_seconds,
      )
    } catch (e) {
      clearRevealedPassword()
      alert(e.message || '临时密码生成失败')
    } finally {
      setPasswordSaving(false)
    }
  }

  // ---------- 删除 ----------
  const handleDelete = (student) => {
    if (!window.confirm(`确定删除学生「${student.username}」吗？此操作不可撤销。`)) return
    fetch(`${API}/auth/${student.id}/`, { method: 'DELETE', headers })
      .then(res => {
        if (res.ok || res.status === 204) setStudents(prev => prev.filter(s => s.id !== student.id))
        else alert('删除失败')
      })
      .catch(e => alert('删除失败：' + e.message))
  }

  // 密码遮罩
  const displayPwd = (id) => revealedPassword?.studentId === id
    ? revealedPassword.password
    : '••••••••'

  const gradeColor = (g) => ({ '七年級': '#667eea', '七年级': '#667eea', '八年級': '#38ef7d', '八年级': '#38ef7d', '九年級': '#f59e0b', '九年级': '#f59e0b' }[g] || '#888')

  // classOptions
  const classOptions = Array.from({ length: 20 }, (_, i) => i + 1)

  return (
    <div style={{ minHeight: '100vh', background: '#f5f7fa', fontFamily: '"Microsoft JhengHei", Arial, sans-serif' }}>
      {/* Header */}
      <header style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white', padding: '16px 0', boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <button onClick={() => navigate('/teacher/dashboard')} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: 8,
            color: 'white', cursor: 'pointer', padding: '8px 14px', fontSize: 13, fontWeight: 600,
          }}>
            <ArrowLeft size={14} /> 返回主页
          </button>
          <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.25)' }} />
          <Users size={20} />
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>学生管理</h1>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 24px' }}>

        {/* 筛选 */}
        <div style={{
          background: 'white', borderRadius: 12, padding: '20px 24px', marginBottom: 24,
          boxShadow: '0 2px 10px rgba(0,0,0,0.06)', display: 'flex', gap: 16, alignItems: 'flex-end', flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>年级</label>
            <select value={filters.grade} onChange={e => setFilters(f => ({ ...f, grade: e.target.value }))}
              style={{ padding: '9px 14px', borderRadius: 8, border: '1px solid #e0e0e0', background: '#fafafa', color: '#333', fontSize: 13, minWidth: 120 }}>
              <option value="">全部年级</option>
              {grades.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>班级</label>
            <select value={filters.class_num} onChange={e => setFilters(f => ({ ...f, class_num: e.target.value }))}
              style={{ padding: '9px 14px', borderRadius: 8, border: '1px solid #e0e0e0', background: '#fafafa', color: '#333', fontSize: 13, minWidth: 80 }}>
              <option value="">全部班级</option>
              {classOptions.map(c => <option key={c} value={String(c)}>{c}班</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>姓名</label>
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#aaa' }} />
              <input type="text" placeholder="输入姓名搜索..." value={filters.search}
                onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
                style={{ padding: '9px 14px 9px 32px', borderRadius: 8, border: '1px solid #e0e0e0', background: '#fafafa', color: '#333', fontSize: 13, minWidth: 180 }} />
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={{ fontSize: 12, color: '#888', fontWeight: 600 }}>排序</label>
            <div style={{ display: 'flex', gap: 6 }}>
              <select value={sortConfig.field} onChange={e => setSortConfig(s => ({ ...s, field: e.target.value }))}
                style={{ padding: '9px 10px', borderRadius: 8, border: '1px solid #e0e0e0', background: '#fafafa', color: '#333', fontSize: 13, minWidth: 120 }}>
                <option value="student_number">按学号</option>
                <option value="grade">按年级</option>
                <option value="class_num">按班级</option>
                <option value="username">按用户名</option>
              </select>
              <select value={sortConfig.order} onChange={e => setSortConfig(s => ({ ...s, order: e.target.value }))}
                style={{ padding: '9px 10px', borderRadius: 8, border: '1px solid #e0e0e0', background: '#fafafa', color: '#333', fontSize: 13, minWidth: 80 }}>
                <option value="asc">升序 ↑</option>
                <option value="desc">降序 ↓</option>
              </select>
            </div>
          </div>
          <button onClick={loadStudents} style={{
            padding: '9px 20px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: '#f59e0b', color: '#fff', fontSize: 13, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <RefreshCw size={14} /> 刷新
          </button>
        </div>

        {/* 统计卡片 */}
        <div style={{
          background: 'white', borderRadius: 12, padding: '16px 24px', marginBottom: 24,
          boxShadow: '0 2px 10px rgba(0,0,0,0.06)', display: 'flex', gap: 32, flexWrap: 'wrap',
        }}>
          {[
            { label: '总学生数', value: filtered.length, color: '#667eea' },
            { label: '年级数量', value: new Set(filtered.map(s => s.grade).filter(Boolean)).size, color: '#38ef7d' },
            { label: '班级数量', value: new Set(filtered.map(s => `${s.grade}-${s.class_num}`).filter(Boolean)).size, color: '#f59e0b' },
          ].map(s => (
            <div key={s.label} style={{ textAlign: 'center', minWidth: 100 }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: s.color }}>{s.value}</div>
              <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{s.label}</div>
            </div>
          ))}
        </div>

        {/* 表格 */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>加载中...</div>
        ) : filtered.length === 0 ? (
          <div style={{ background: 'white', borderRadius: 16, padding: '60px 24px', textAlign: 'center', boxShadow: '0 2px 10px rgba(0,0,0,0.06)', color: '#888' }}>
            <Users size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
            <p>暂无学生记录</p>
          </div>
        ) : (
          <div style={{ background: 'white', borderRadius: 16, overflow: 'hidden', boxShadow: '0 2px 10px rgba(0,0,0,0.06)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8f9fc', borderBottom: '2px solid #f0f0f0' }}>
                  {['ID', '学号', '年级', '班级', '姓名', '密码', '操作'].map(h => (
                    <th key={h} style={{ padding: '14px 18px', textAlign: 'left', fontSize: 12, color: '#888', fontWeight: 700, letterSpacing: '0.05em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((s, i) => (
                  <tr key={s.id || i} style={{ borderBottom: '1px solid #f5f5f5', transition: 'background 0.15s' }}
                    onMouseEnter={e => e.currentTarget.style.background = '#f8f9fc'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '14px 18px', fontSize: 12, color: '#aaa' }}>{s.id}</td>
                    <td style={{ padding: '14px 18px', fontSize: 13, color: '#666' }}>{s.student_number || '—'}</td>
                    <td style={{ padding: '14px 18px' }}>
                      <span style={{
                        display: 'inline-block', padding: '3px 10px', borderRadius: 12,
                        fontSize: 12, fontWeight: 700,
                        background: `${gradeColor(s.grade)}18`, color: gradeColor(s.grade),
                      }}>{s.grade || '—'}</span>
                    </td>
                    <td style={{ padding: '14px 18px', fontSize: 13, color: '#666' }}>{s.class_num ? `${s.class_num}班` : '—'}</td>
                    <td style={{ padding: '14px 18px', fontSize: 14, color: '#333', fontWeight: 600 }}>{s.display_name || s.username}</td>
                    <td style={{ padding: '14px 18px' }}>
                      <span style={{ fontFamily: 'monospace', background: '#f0f0f0', padding: '2px 8px', borderRadius: 3, fontSize: 12, color: '#666', marginRight: 6 }}>
                        {displayPwd(s.id)}
                      </span>
                      <button onClick={() => togglePassword(s)} style={{
                        background: 'none', border: 'none', cursor: 'pointer', color: '#667eea',
                        fontSize: 11, textDecoration: 'underline', padding: 0,
                      }}>
                        {revealedPassword?.studentId === s.id
                          ? '隐藏'
                          : (s.password_available ? '显示' : '需重置')}
                      </button>
                      {revealedPassword?.studentId === s.id && (
                        <div style={{ fontSize: 10, color: '#b45309', marginTop: 4 }}>
                          {revealedPassword.seconds} 秒后自动隐藏
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '14px 18px', display: 'flex', gap: 6 }}>
                      <button onClick={() => openEdit(s)} style={{
                        display: 'flex', alignItems: 'center', gap: 4,
                        padding: '6px 12px', borderRadius: 8, border: 'none', cursor: 'pointer',
                        background: '#28a745', color: '#fff', fontSize: 12, fontWeight: 600,
                      }}>
                        <Edit2 size={12} /> 编辑
                      </button>
                      <button onClick={() => handleDelete(s)} style={{
                        display: 'flex', alignItems: 'center', gap: 4,
                        padding: '6px 12px', borderRadius: 8, border: 'none', cursor: 'pointer',
                        background: '#dc3545', color: '#fff', fontSize: 12, fontWeight: 600,
                      }}>
                        <Trash2 size={12} /> 删除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {/* 编辑弹窗 */}
      {editModal.open && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={closeEdit}>
          <div style={{
            background: 'white', borderRadius: 16, padding: '32px', width: 440,
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#333', margin: 0 }}>编辑学生信息</h2>
              <button onClick={closeEdit} style={{
                background: 'none', border: 'none', cursor: 'pointer', color: '#888', padding: 4,
              }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {[
                { key: 'display_name', label: '姓名', type: 'text' },
                { key: 'username', label: '用户名（系统自动生成）', type: 'text', readOnly: true },
                { key: 'student_number', label: '学号', type: 'text' },
              ].map(field => (
                <div key={field.key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: 13, color: '#666', fontWeight: 600 }}>{field.label}</label>
                  <input
                    type={field.type}
                    value={editForm[field.key] || ''}
                    onChange={field.readOnly ? undefined : e => setEditForm(f => ({ ...f, [field.key]: e.target.value }))}
                    readOnly={field.readOnly || false}
                    disabled={field.readOnly || false}
                    style={{ padding: '10px 14px', borderRadius: 8, border: '1px solid #e0e0e0', fontSize: 14, color: field.readOnly ? '#888' : '#333', background: field.readOnly ? '#f5f5f5' : '#fff' }}
                  />
                </div>
              ))}

              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: 13, color: '#666', fontWeight: 600 }}>年级</label>
                  <select value={editForm.grade || ''}
                    onChange={e => setEditForm(f => ({ ...f, grade: e.target.value }))}
                    style={{ padding: '10px 14px', borderRadius: 8, border: '1px solid #e0e0e0', fontSize: 14, color: '#333' }}>
                    <option value="">请选择年级</option>
                    {grades.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <label style={{ fontSize: 13, color: '#666', fontWeight: 600 }}>班级</label>
                  <select value={editForm.class_num || ''}
                    onChange={e => setEditForm(f => ({ ...f, class_num: e.target.value }))}
                    style={{ padding: '10px 14px', borderRadius: 8, border: '1px solid #e0e0e0', fontSize: 14, color: '#333' }}>
                    <option value="">请选择班级</option>
                    {classOptions.map(c => <option key={c} value={String(c)}>{c}班</option>)}
                  </select>
                </div>
              </div>

              <div style={{ borderTop: '1px solid #eee', paddingTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
                <label style={{ fontSize: 13, color: '#666', fontWeight: 600 }}>密码重置</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={e => setNewPassword(e.target.value)}
                  placeholder="输入至少 8 位新密码"
                  autoComplete="new-password"
                  style={{ padding: '10px 14px', borderRadius: 8, border: '1px solid #e0e0e0', fontSize: 14 }}
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" onClick={handleManualPasswordReset} disabled={passwordSaving} style={{
                    padding: '8px 14px', borderRadius: 8, border: 'none', cursor: passwordSaving ? 'not-allowed' : 'pointer',
                    background: '#f59e0b', color: 'white', fontSize: 12, fontWeight: 600,
                  }}>设置新密码</button>
                  <button type="button" onClick={handleGeneratedPassword} disabled={passwordSaving} style={{
                    padding: '8px 14px', borderRadius: 8, border: '1px solid #667eea', cursor: passwordSaving ? 'not-allowed' : 'pointer',
                    background: 'white', color: '#667eea', fontSize: 12, fontWeight: 600,
                  }}>生成随机临时密码</button>
                </div>
                {revealedPassword?.studentId === editModal.student.id && (
                  <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: '10px 12px' }}>
                    <div style={{ fontSize: 11, color: '#9a3412', marginBottom: 4 }}>当前密码（{revealedPassword.seconds} 秒后自动隐藏）</div>
                    <div style={{ fontFamily: 'monospace', fontSize: 15, color: '#7c2d12' }}>{revealedPassword.password}</div>
                  </div>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 12, marginTop: 28, justifyContent: 'flex-end' }}>
              <button onClick={closeEdit} style={{
                padding: '10px 24px', borderRadius: 8, border: '1px solid #e0e0e0',
                background: 'white', color: '#666', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              }}>取消</button>
              <button onClick={saveEdit} disabled={editSaving} style={{
                padding: '10px 24px', borderRadius: 8, border: 'none',
                background: editSaving ? '#ccc' : '#667eea', color: 'white', fontSize: 14, fontWeight: 600, cursor: editSaving ? 'not-allowed' : 'pointer',
              }}>
                {editSaving ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
