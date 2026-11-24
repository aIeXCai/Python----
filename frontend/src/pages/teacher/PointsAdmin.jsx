import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Coins, Minus, Plus, RefreshCw, RotateCcw, Search, X,
} from 'lucide-react'
import { API_BASE_URL } from '../../api/config.js'
import { GRADES } from '../../constants/grades.js'
import {
  adjustStudentPoints,
  getAdminPointsStudents,
  resetPoints,
} from '../../api/points.js'

const QUICK_DELTAS = ['10', '20', '50', '-10', '-20']

function formatPoints(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '0'
  return Number.isInteger(number) ? String(number) : number.toFixed(1)
}

const labelStyle = { fontSize: 12, color: '#888', fontWeight: 600 }
const selectStyle = {
  padding: '9px 14px', borderRadius: 8, border: '1px solid #e0e0e0',
  background: '#fafafa', color: '#333', fontSize: 13,
}

export default function PointsAdmin() {
  const navigate = useNavigate()
  const teacher = useMemo(() => {
    try { return JSON.parse(localStorage.getItem('user') || '{}') } catch { return {} }
  }, [])

  const [filters, setFilters] = useState({
    grade: teacher.managed_grade || '',
    class_num: '',
    q: '',
  })
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [classes, setClasses] = useState([])
  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const [adjust, setAdjust] = useState({ open: false, student: null, delta: '10', note: '' })
  const [saving, setSaving] = useState(false)
  const [resetPanel, setResetPanel] = useState({ open: false, busy: false, note: '' })
  const mountedRef = useRef(true)

  // StrictMode 下 effect 会「挂载 → 清理 → 再挂载」，清理阶段把 ref 置 false 后
  // 必须靠重新挂载时再置回 true，否则 loading 永远停在 true（表现为页面一直加载中）。
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(filters.q.trim()), 300)
    return () => clearTimeout(timer)
  }, [filters.q])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getAdminPointsStudents({
        grade: filters.grade,
        class_num: filters.class_num,
        q: debouncedQuery,
      })
      if (mountedRef.current) setStudents(data.students || [])
    } catch (err) {
      if (mountedRef.current) setError(err.message || '加载失败')
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [filters.grade, filters.class_num, debouncedQuery])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!filters.grade) { setClasses([]); return }
    const token = localStorage.getItem('token')
    fetch(
      `${API_BASE_URL}/admin/info/classes/?grade=${encodeURIComponent(filters.grade)}`,
      { headers: { Authorization: `Token ${token}` } },
    )
      .then(res => (res.ok ? res.json() : { classes: [] }))
      .then(data => { if (mountedRef.current) setClasses(data.classes || []) })
      .catch(() => { if (mountedRef.current) setClasses([]) })
  }, [filters.grade])

  const summary = useMemo(() => {
    const values = students.map(row => Number(row.points) || 0)
    const total = values.reduce((sum, value) => sum + value, 0)
    return {
      count: students.length,
      average: students.length ? formatPoints(total / students.length) : '0',
      top: values.length ? formatPoints(Math.max(...values)) : '0',
    }
  }, [students])

  async function submitAdjust(event) {
    event.preventDefault()
    if (!adjust.student) return
    const delta = Number(adjust.delta)
    if (!Number.isFinite(delta) || delta === 0) {
      setError('请输入不为 0 的调整值')
      return
    }
    setSaving(true)
    setError('')
    try {
      const result = await adjustStudentPoints(adjust.student.student_id, delta, adjust.note)
      setNotice(
        `${adjust.student.name} ${delta > 0 ? '+' : ''}${formatPoints(result.delta)} 分，现有 ${formatPoints(result.balance)} 分`,
      )
      setAdjust({ open: false, student: null, delta: '10', note: '' })
      await load()
    } catch (err) {
      setError(err.message || '调整失败')
    } finally {
      setSaving(false)
    }
  }

  async function confirmReset() {
    setResetPanel(panel => ({ ...panel, busy: true }))
    setError('')
    try {
      const result = await resetPoints({
        grade: filters.grade,
        class_num: filters.class_num,
        note: resetPanel.note,
      })
      setNotice(
        `已清零 ${result.cleared_count} 人，共回收 ${formatPoints(result.cleared_total)} 分`,
      )
      setResetPanel({ open: false, busy: false, note: '' })
      await load()
    } catch (err) {
      setError(err.message || '清零失败')
    } finally {
      setResetPanel(panel => ({ ...panel, busy: false }))
    }
  }

  const scopeText = filters.class_num
    ? `${filters.grade} ${filters.class_num}班`
    : `${filters.grade || '我的管理范围'} 全部班级`

  return (
    <div style={{ minHeight: '100vh', background: '#f5f7fa', fontFamily: '"Microsoft JhengHei", Arial, sans-serif' }}>
      <header style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white', padding: '18px 0', boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 14 }}>
          <button
            onClick={() => navigate('/teacher/dashboard')}
            style={{
              background: 'rgba(255,255,255,0.15)', color: 'white', border: '2px solid rgba(255,255,255,0.3)',
              padding: '7px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 13, fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <ArrowLeft size={14} /> 返回
          </button>
          <Coins size={24} />
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>学生积分管理</h1>
        </div>
      </header>

      <div style={{ maxWidth: 1200, margin: '26px auto', padding: '0 24px' }}>
        <div style={{
          background: 'white', borderRadius: 12, padding: '16px 20px', marginBottom: 20,
          boxShadow: '0 2px 10px rgba(0,0,0,0.06)', display: 'flex', gap: 16, flexWrap: 'wrap',
          alignItems: 'flex-end',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={labelStyle}>年级</label>
            <select
              value={filters.grade}
              onChange={e => setFilters(f => ({ ...f, grade: e.target.value, class_num: '' }))}
              style={{ ...selectStyle, minWidth: 110 }}
            >
              <option value="">全部（我的范围）</option>
              {GRADES.map(grade => <option key={grade} value={grade}>{grade}</option>)}
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={labelStyle}>班级</label>
            <select
              value={filters.class_num}
              onChange={e => setFilters(f => ({ ...f, class_num: e.target.value }))}
              disabled={!filters.grade}
              style={{ ...selectStyle, minWidth: 90, opacity: filters.grade ? 1 : 0.6 }}
            >
              <option value="">全部班级</option>
              {classes.map(value => <option key={value} value={String(value)}>{value}班</option>)}
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label style={labelStyle}>姓名 / 学号</label>
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#aaa' }} />
              <input
                type="text"
                value={filters.q}
                onChange={e => setFilters(f => ({ ...f, q: e.target.value }))}
                placeholder="输入姓名或学号"
                style={{ ...selectStyle, paddingLeft: 32, minWidth: 180 }}
              />
            </div>
          </div>

          <button
            onClick={load}
            style={{
              padding: '9px 18px', borderRadius: 8, border: 'none', cursor: 'pointer',
              background: '#667eea', color: '#fff', fontSize: 13, fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <RefreshCw size={14} /> 刷新
          </button>

          <button
            onClick={() => setResetPanel({ open: true, busy: false, note: '' })}
            style={{
              marginLeft: 'auto', padding: '9px 18px', borderRadius: 8,
              border: '1px solid #ffd0d0', cursor: 'pointer', background: '#fff5f5',
              color: '#d64545', fontSize: 13, fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <RotateCcw size={14} /> 批量清零
          </button>
        </div>

        {notice && (
          <div style={{
            background: '#eefaf3', border: '1px solid #bfe7d2', color: '#1f7a4d',
            borderRadius: 10, padding: '10px 16px', marginBottom: 16, fontSize: 13,
          }}>
            {notice}
          </div>
        )}
        {error && (
          <div style={{
            background: '#fff5f5', border: '1px solid #ffd0d0', color: '#d64545',
            borderRadius: 10, padding: '10px 16px', marginBottom: 16, fontSize: 13,
          }}>
            {error}
          </div>
        )}

        <div style={{
          background: 'white', borderRadius: 12, padding: '16px 24px', marginBottom: 20,
          boxShadow: '0 2px 10px rgba(0,0,0,0.06)', display: 'flex', gap: 32, flexWrap: 'wrap',
        }}>
          {[
            { label: '学生数', value: summary.count, color: '#667eea' },
            { label: '平均积分', value: summary.average, color: '#11998e' },
            { label: '最高积分', value: summary.top, color: '#f59e0b' },
          ].map(item => (
            <div key={item.label} style={{ textAlign: 'center', minWidth: 100 }}>
              <div style={{ fontSize: 26, fontWeight: 800, color: item.color }}>{item.value}</div>
              <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{item.label}</div>
            </div>
          ))}
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>加载中…</div>
        ) : students.length === 0 ? (
          <div style={{
            background: 'white', borderRadius: 16, padding: '60px 24px', textAlign: 'center',
            boxShadow: '0 2px 10px rgba(0,0,0,0.06)', color: '#888',
          }}>
            <Coins size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
            <p>没有符合条件的学生</p>
          </div>
        ) : (
          <div style={{ background: 'white', borderRadius: 16, overflow: 'hidden', boxShadow: '0 2px 10px rgba(0,0,0,0.06)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8f9fc', borderBottom: '2px solid #f0f0f0' }}>
                  {['学号', '年级', '班级', '姓名', '称号', '积分', '操作'].map(head => (
                    <th key={head} style={{
                      padding: '14px 18px', textAlign: 'left', fontSize: 12,
                      color: '#888', fontWeight: 700, letterSpacing: '0.05em',
                    }}>{head}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {students.map(student => (
                  <tr
                    key={student.student_id}
                    style={{ borderBottom: '1px solid #f5f5f5' }}
                    onMouseEnter={e => { e.currentTarget.style.background = '#f8f9fc' }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
                  >
                    <td style={{ padding: '13px 18px', fontSize: 13, color: '#666' }}>{student.student_number || '—'}</td>
                    <td style={{ padding: '13px 18px', fontSize: 13, color: '#666' }}>{student.grade}</td>
                    <td style={{ padding: '13px 18px', fontSize: 13, color: '#666' }}>
                      <span style={{
                        display: 'inline-block', padding: '3px 10px', borderRadius: 12,
                        background: '#eef1fb', color: '#5566c9', fontSize: 12, fontWeight: 600,
                      }}>
                        {student.class_num}班
                      </span>
                    </td>
                    <td style={{ padding: '13px 18px', fontSize: 13, color: '#333', fontWeight: 600 }}>{student.name}</td>
                    <td style={{ padding: '13px 18px', fontSize: 12, color: '#888' }}>{student.title_name || '—'}</td>
                    <td style={{ padding: '13px 18px', fontSize: 15, fontWeight: 800, color: '#667eea' }}>
                      {formatPoints(student.points)}
                    </td>
                    <td style={{ padding: '13px 18px' }}>
                      <button
                        onClick={() => setAdjust({ open: true, student, delta: '10', note: '' })}
                        style={{
                          padding: '6px 12px', borderRadius: 8, border: '1px solid #dfe3f1',
                          background: '#fff', color: '#5566c9', fontSize: 12, fontWeight: 600, cursor: 'pointer',
                        }}
                      >
                        调整积分
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {adjust.open && adjust.student && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, zIndex: 50,
        }}>
          <form
            onSubmit={submitAdjust}
            style={{
              background: 'white', borderRadius: 16, padding: 28, width: '100%', maxWidth: 420,
              boxShadow: '0 20px 50px rgba(0,0,0,0.25)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
              <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333' }}>
                调整 {adjust.student.name} 的积分
              </h2>
              <button
                type="button"
                onClick={() => setAdjust({ open: false, student: null, delta: '10', note: '' })}
                style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#999' }}
                aria-label="关闭"
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: 13, color: '#888', marginBottom: 16 }}>
              当前积分 <strong style={{ color: '#667eea' }}>{formatPoints(adjust.student.points)}</strong> 分
            </p>

            <label style={{ ...labelStyle, display: 'block', marginBottom: 6 }}>调整值（正数加分，负数扣分）</label>
            <input
              type="number"
              step="0.1"
              value={adjust.delta}
              onChange={e => setAdjust(a => ({ ...a, delta: e.target.value }))}
              style={{ ...selectStyle, width: '100%', marginBottom: 10 }}
            />
            <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
              {QUICK_DELTAS.map(value => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setAdjust(a => ({ ...a, delta: value }))}
                  style={{
                    padding: '5px 12px', borderRadius: 999, cursor: 'pointer', fontSize: 12, fontWeight: 600,
                    border: '1px solid #e0e0e0', background: '#fafafa', color: value.startsWith('-') ? '#d64545' : '#1f7a4d',
                    display: 'flex', alignItems: 'center', gap: 3,
                  }}
                >
                  {value.startsWith('-') ? <Minus size={11} /> : <Plus size={11} />}
                  {value.replace('-', '')}
                </button>
              ))}
            </div>

            <label style={{ ...labelStyle, display: 'block', marginBottom: 6 }}>备注（可选）</label>
            <input
              type="text"
              value={adjust.note}
              onChange={e => setAdjust(a => ({ ...a, note: e.target.value }))}
              placeholder="例如：课堂表现、补做练习"
              style={{ ...selectStyle, width: '100%', marginBottom: 22 }}
            />

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setAdjust({ open: false, student: null, delta: '10', note: '' })}
                style={{
                  padding: '9px 18px', borderRadius: 8, border: '1px solid #e0e0e0',
                  background: '#fff', color: '#666', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}
              >
                取消
              </button>
              <button
                type="submit"
                disabled={saving}
                style={{
                  padding: '9px 20px', borderRadius: 8, border: 'none',
                  background: '#667eea', color: '#fff', fontSize: 13, fontWeight: 600,
                  cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1,
                }}
              >
                {saving ? '保存中…' : '确认调整'}
              </button>
            </div>
          </form>
        </div>
      )}

      {resetPanel.open && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, zIndex: 50,
        }}>
          <div style={{
            background: 'white', borderRadius: 16, padding: 28, width: '100%', maxWidth: 440,
            boxShadow: '0 20px 50px rgba(0,0,0,0.25)',
          }}>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', marginBottom: 12 }}>批量清零积分</h2>
            <p style={{ fontSize: 13, color: '#666', lineHeight: 1.7, marginBottom: 16 }}>
              即将清零 <strong style={{ color: '#d64545' }}>{scopeText}</strong> 的全部学生积分。
              清零会为每人记一条等额负向流水，历史记录仍然可查，但学生端余额会归零。
            </p>
            <label style={{ ...labelStyle, display: 'block', marginBottom: 6 }}>备注（可选）</label>
            <input
              type="text"
              value={resetPanel.note}
              onChange={e => setResetPanel(p => ({ ...p, note: e.target.value }))}
              placeholder="例如：新学期重置"
              style={{ ...selectStyle, width: '100%', marginBottom: 22 }}
            />
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setResetPanel({ open: false, busy: false, note: '' })}
                style={{
                  padding: '9px 18px', borderRadius: 8, border: '1px solid #e0e0e0',
                  background: '#fff', color: '#666', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}
              >
                取消
              </button>
              <button
                type="button"
                onClick={confirmReset}
                disabled={resetPanel.busy}
                style={{
                  padding: '9px 20px', borderRadius: 8, border: 'none',
                  background: '#d64545', color: '#fff', fontSize: 13, fontWeight: 600,
                  cursor: resetPanel.busy ? 'not-allowed' : 'pointer', opacity: resetPanel.busy ? 0.7 : 1,
                }}
              >
                {resetPanel.busy ? '清零中…' : '确认清零'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
