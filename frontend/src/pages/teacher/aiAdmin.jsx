import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Bot, BookOpen, BarChart3, RefreshCw, Eye, Trash2,
  Upload, X, Plus, Edit2, CheckCircle
} from 'lucide-react'
import { API_BASE_URL } from '../../api/config.js'
import { GRADES } from '../../constants/grades.js'

const API = API_BASE_URL
const DIFFICULTY_COLORS = { '简单': '#38ef7d', '中等': '#f59e0b', '困难': '#ef4444', '入门': '#38ef7d', '进阶': '#f59e0b', '高级': '#ef4444' }

function MsgBanner({ msg }) {
  if (!msg.text) return null
  return (
    <div style={{
      padding: '10px 14px', borderRadius: 8, marginBottom: 12, fontSize: 13, fontWeight: 600,
      background: msg.type === 'success' ? '#d4edda' : '#f8d7da',
      color: msg.type === 'success' ? '#155724' : '#721c24',
      border: `1px solid ${msg.type === 'success' ? '#c3e6cb' : '#f5c6cb'}`,
    }}>{msg.text}</div>
  )
}

export default function AiAdmin() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('problems')
  const token = localStorage.getItem('token')
  const headers = { 'Authorization': `Token ${token}`, 'Content-Type': 'application/json' }

  // ─── Tab0: 题库管理 ─────────────────────────────────────────────────────────
  const [problems, setProblems] = useState([])
  const [pLoading, setPLoading] = useState(true)
  const [pSyncing, setPSyncing] = useState(false)
  const [pMsg, setPMsg] = useState({ type: '', text: '' })
  const [detailModal, setDetailModal] = useState({ open: false, problem: null })
  const [detailLoading, setDetailLoading] = useState(false)

  const loadProblems = async () => {
    setPLoading(true)
    try {
      const res = await fetch(`${API}/ai/admin/problems/`, { headers })
      if (res.ok) setProblems(await res.json())
    } catch (e) { console.error(e) }
    setPLoading(false)
  }

  useEffect(() => { loadProblems() }, [])

  const syncFromDisk = async () => {
    setPSyncing(true)
    try {
      const res = await fetch(`${API}/ai/admin/problems/`, { method: 'POST', headers })
      if (res.ok) {
        const data = await res.json()
        setPMsg({ type: 'success', text: `同步完成！新增 ${data.created} 题，更新 ${data.updated} 题` })
        loadProblems()
      } else {
        const data = await res.json()
        setPMsg({ type: 'error', text: JSON.stringify(data) })
      }
    } catch (e) { setPMsg({ type: 'error', text: '同步失败：' + e.message }) }
    setPSyncing(false)
    setTimeout(() => setPMsg({ type: '', text: '' }), 5000)
  }

  const viewProblem = async (problemId) => {
    setDetailLoading(true)
    setDetailModal({ open: true, problem: null })
    try {
      const res = await fetch(`${API}/ai/admin/problems/${problemId}/`, { headers })
      if (res.ok) setDetailModal({ open: true, problem: await res.json() })
    } catch (e) { console.error(e) }
    setDetailLoading(false)
  }

  const deleteProblem = (problem) => {
    if (!window.confirm(`确定删除题目「${problem.title}」吗？此操作不可撤销。`)) return
    fetch(`${API}/ai/admin/problems/${problem.problem_id}/`, { method: 'DELETE', headers })
      .then(res => {
        if (res.ok || res.status === 204) {
          setProblems(prev => prev.filter(p => p.problem_id !== problem.problem_id))
          setPMsg({ type: 'success', text: `题目「${problem.title}」已删除` })
          setTimeout(() => setPMsg({ type: '', text: '' }), 3000)
        } else { alert('删除失败') }
      })
      .catch(e => alert('删除失败：' + e.message))
  }

  // ─── Tab1: 成绩统计 ─────────────────────────────────────────────────────────
  const [scores, setScores] = useState([])
  const [sLoading, setSLoading] = useState(true)
  const [sFilters, setSFilters] = useState({ grade: '', class_num: '', problem_id: '' })
  const [sStats, setSStats] = useState({ total: 0, submitted: 0, avg: 0, problemCount: 0 })
  const [problems2, setProblems2] = useState([])
  const [scoreMapByNum, setScoreMapByNum] = useState({})

  const grades = GRADES
  const classOptions = Array.from({ length: 20 }, (_, i) => i + 1)

  const loadScores = async () => {
    setSLoading(true)
    try {
      const params = {}
      if (sFilters.grade) params.grade = sFilters.grade
      if (sFilters.class_num) params.class_num = sFilters.class_num
      if (sFilters.problem_id) params.problem_id = sFilters.problem_id
      params.course_type = 'ai'
      const qs = new URLSearchParams(params).toString()
      const res = await fetch(`${API}/ai/admin/scores/${qs ? '?' + qs : ''}`, { headers })
      if (res.ok) {
        const data = await res.json()
        setScores(data.students || [])
        setProblems2(data.problems || [])

        let total = (data.students || []).length
        let submitted = 0, sum = 0, count = 0
        const map = {}
        ;(data.students || []).forEach(s => {
          const num = parseInt(s.student_number) || 0
          if (num >= 1 && num <= 50) {
            map[num] = Math.max(map[num] || 0, s.best_score || 0)
          }
          s.scores.forEach(sc => {
            if (sc.submitted) { submitted++; sum += sc.score || 0; count++ }
          })
        })
        setScoreMapByNum(map)
        setSStats({ total, submitted, avg: count > 0 ? (sum / count).toFixed(1) : 0, problemCount: (data.problems || []).length })
      }
    } catch (e) { console.error(e) }
    setSLoading(false)
  }

  useEffect(() => { loadScores() }, [sFilters])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { const id = setInterval(loadScores, 5000); return () => clearInterval(id) }, [sFilters])

  const scoreColor = (score) => {
    if (score == null) return { bg: '#f8f9fa', color: '#6c757d', text: '—' }
    if (score >= 90) return { bg: '#d4edda', color: '#155724', text: score }
    if (score >= 75) return { bg: '#d1ecf1', color: '#0c5460', text: score }
    if (score >= 60) return { bg: '#fff3cd', color: '#856404', text: score }
    return { bg: '#f8d7da', color: '#721c24', text: score }
  }

  const gradeColor = (g) => ({ '七年级': '#667eea', '八年级': '#38ef7d', '九年级': '#f59e0b' }[g] || '#888')

  const ROWS = 5, COLS = 10

  // ─── Tab 样式 ──────────────────────────────────────────────────────────────
  const tabs = [
    { key: 'problems', label: '题库管理', icon: BookOpen },
    { key: 'scores', label: '成绩统计', icon: BarChart3 },
  ]

  return (
    <div style={{ minHeight: '100vh', background: '#f5f7fa', fontFamily: '"Microsoft JhengHei", Arial, sans-serif' }}>

      {/* Header */}
      <header style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white', padding: '14px 0', boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
      }}>
        <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 14 }}>
          <button onClick={() => navigate('/teacher/dashboard')} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: 8,
            color: 'white', cursor: 'pointer', padding: '7px 14px', fontSize: 13, fontWeight: 600,
          }}>
            <ArrowLeft size={14} /> 返回主页
          </button>
          <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.25)' }} />
          <Bot size={20} />
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>AI课管理</h1>

          {/* Tab 切换 */}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 10, padding: 4 }}>
            {tabs.map(({ key, label, icon: Icon }) => (
              <button key={key} onClick={() => setTab(key)} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '7px 18px', borderRadius: 8, border: 'none', cursor: 'pointer',
                fontSize: 13, fontWeight: 700,
                background: tab === key ? 'white' : 'transparent',
                color: tab === key ? '#667eea' : 'rgba(255,255,255,0.75)',
                transition: 'all 0.2s',
              }}>
                <Icon size={14} />{label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1400, margin: '0 auto', padding: '28px 24px' }}>

        {/* ─── Tab0: 题库管理 ──────────────────────────────────────────────── */}
        {tab === 'problems' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

            {/* 操作栏 */}
            <div style={{ background: 'white', borderRadius: 14, padding: '16px 20px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <BookOpen size={18} style={{ color: '#667eea' }} />
              <span style={{ fontSize: 15, fontWeight: 700, color: '#333' }}>AI课题库</span>
              <span style={{ marginLeft: 4, fontSize: 12, color: '#888' }}>共 {problems.length} 题</span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                <button onClick={syncFromDisk} disabled={pSyncing} style={{
                  padding: '8px 18px', borderRadius: 8, border: 'none', cursor: pSyncing ? 'not-allowed' : 'pointer',
                  background: pSyncing ? '#ccc' : '#45b7d1', color: 'white', fontWeight: 700, fontSize: 13,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  <RefreshCw size={13} className={pSyncing ? 'spin' : ''} />
                  {pSyncing ? '同步中...' : '从磁盘同步'}
                </button>
              </div>
            </div>

            <MsgBanner msg={pMsg} />

            {/* 题目卡片网格 */}
            <div style={{ background: 'white', borderRadius: 14, overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              {pLoading ? (
                <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>加载中...</div>
              ) : problems.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>
                  <BookOpen size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
                  <p>暂无题目，点击「从磁盘同步」导入</p>
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14, padding: 20 }}>
                  {problems.map((p, i) => (
                    <div key={p.problem_id || i} style={{
                      border: '2px solid #e9ecef', borderRadius: 12, padding: 14,
                      transition: 'all 0.2s', background: 'white',
                    }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = '#667eea'; e.currentTarget.style.background = '#f8f9ff' }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = '#e9ecef'; e.currentTarget.style.background = 'white' }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 13, fontWeight: 700, color: '#333', marginBottom: 3 }}>
                            {p.title || `题目${p.problem_id}`}
                          </div>
                          <div style={{ fontSize: 11, color: '#888' }}>编号：{p.problem_id} · 测试点：{p.test_count}</div>
                        </div>
                        <span style={{
                          padding: '3px 8px', borderRadius: 8, fontSize: 11, fontWeight: 800, whiteSpace: 'nowrap',
                          background: `${DIFFICULTY_COLORS[p.difficulty] || '#888'}18`,
                          color: DIFFICULTY_COLORS[p.difficulty] || '#888',
                        }}>{p.difficulty || '—'}</span>
                      </div>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button onClick={() => viewProblem(p.problem_id)} style={{
                          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                          padding: '6px 0', borderRadius: 8, border: 'none', cursor: 'pointer',
                          background: '#17a2b8', color: 'white', fontSize: 12, fontWeight: 600,
                        }}>
                          <Eye size={12} /> 查看
                        </button>
                        <button onClick={() => deleteProblem(p)} style={{
                          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                          padding: '6px 0', borderRadius: 8, border: 'none', cursor: 'pointer',
                          background: '#dc3545', color: 'white', fontSize: 12, fontWeight: 600,
                        }}>
                          <Trash2 size={12} /> 删除
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 上传说明 */}
            <div style={{ background: 'white', borderRadius: 14, padding: '20px 24px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Upload size={16} style={{ color: '#667eea' }} />
                <span style={{ fontSize: 14, fontWeight: 700, color: '#333' }}>上传新题目</span>
              </div>
              <div style={{ background: '#f0f4ff', borderRadius: 10, padding: '14px 18px', fontSize: 13, color: '#555', lineHeight: 1.8, marginBottom: 16 }}>
                <strong>流程：</strong>将题目文件夹放入后端 <code style={{ background: '#e0e0e0', padding: '1px 5px', borderRadius: 3 }}>backend/problems/</code> 目录（包含 <code>description.txt</code> 和测试点文件），然后点击「从磁盘同步」即可。
              </div>
              <button onClick={syncFromDisk} disabled={pSyncing} style={{
                padding: '10px 24px', borderRadius: 8, border: 'none', cursor: pSyncing ? 'not-allowed' : 'pointer',
                background: pSyncing ? '#ccc' : '#667eea', color: 'white', fontWeight: 700, fontSize: 13,
              }}>
                {pSyncing ? '同步中...' : '📂 从磁盘同步题目'}
              </button>
            </div>
          </div>
        )}

        {/* ─── Tab1: 成绩统计 ──────────────────────────────────────────────── */}
        {tab === 'scores' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* 筛选栏 */}
            <div style={{ background: 'white', borderRadius: 14, padding: '16px 20px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <Bot size={18} style={{ color: '#667eea' }} />
              <span style={{ fontSize: 14, fontWeight: 700, color: '#333' }}>AI课成绩</span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 11, color: '#888', fontWeight: 600 }}>年级</label>
                <select value={sFilters.grade} onChange={e => setSFilters(f => ({ ...f, grade: e.target.value }))}
                  style={{ padding: '7px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13, minWidth: 100 }}>
                  <option value="">全部年级</option>
                  {grades.map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 11, color: '#888', fontWeight: 600 }}>班级</label>
                <select value={sFilters.class_num} onChange={e => setSFilters(f => ({ ...f, class_num: e.target.value }))}
                  style={{ padding: '7px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13, minWidth: 80 }}>
                  <option value="">全部班级</option>
                  {classOptions.map(c => <option key={c} value={String(c)}>{c}班</option>)}
                </select>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 11, color: '#888', fontWeight: 600 }}>题目</label>
                <select value={sFilters.problem_id} onChange={e => setSFilters(f => ({ ...f, problem_id: e.target.value }))}
                  style={{ padding: '7px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13, minWidth: 120 }}>
                  <option value="">全部题目</option>
                  {problems2.map(p => <option key={p.problem_id} value={p.problem_id}>{p.title || `题${p.problem_id}`}</option>)}
                </select>
              </div>
              <button onClick={loadScores} style={{
                padding: '8px 18px', borderRadius: 8, border: 'none', cursor: 'pointer',
                background: '#28a745', color: '#fff', fontSize: 13, fontWeight: 600,
                display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto',
              }}>
                <RefreshCw size={13} /> 刷新
              </button>
            </div>

            {/* 统计卡片 */}
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              {[
                { label: '总学生数', value: sStats.total, color: '#1976d2' },
                { label: '题目数', value: sStats.problemCount, color: '#1976d2' },
                { label: '总提交数', value: sStats.submitted, color: '#1976d2' },
                { label: '平均分', value: sStats.avg, color: '#1976d2' },
                { label: '满分人数', value: Object.values(scoreMapByNum).filter(v => v === 100).length, color: '#2e7d32' },
              ].map(s => (
                <div key={s.label} style={{
                  background: 'white', borderRadius: 12, padding: '14px 24px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 90,
                }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: s.color }}>{s.value}</div>
                  <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>{s.label}</div>
                </div>
              ))}
            </div>

            {/* 双栏：成绩表 + 灯矩阵 */}
            <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>

              {/* 成绩表格 */}
              <div style={{ flex: 1, minWidth: 0 }}>
                {sLoading ? (
                  <div style={{ background: 'white', borderRadius: 14, padding: 60, textAlign: 'center', color: '#888', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>加载中...</div>
                ) : scores.length === 0 ? (
                  <div style={{ background: 'white', borderRadius: 14, padding: '60px 24px', textAlign: 'center', color: '#888', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                    <BarChart3 size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
                    <p>暂无成绩记录</p>
                  </div>
                ) : (
                  <div style={{ background: 'white', borderRadius: 14, overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 600 }}>
                      <thead>
                        <tr style={{ background: '#495057' }}>
                          {['年级', '班级', '姓名', '学号'].map(h => (
                            <th key={h} style={{ padding: '11px 14px', color: 'white', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>{h}</th>
                          ))}
                          {problems2.map(p => (
                            <th key={p.problem_id} style={{ padding: '11px 10px', color: 'white', textAlign: 'center', fontSize: 11, fontWeight: 600 }}>
                              {p.title || `题${p.problem_id}`}
                            </th>
                          ))}
                          {problems2.length === 0 && (
                            <th style={{ padding: '11px 14px', color: 'rgba(255,255,255,0.6)', textAlign: 'center' }}>暂无题目</th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {scores.slice().sort((a, b) => (parseInt(a.student_number) || 0) - (parseInt(b.student_number) || 0)).map((student, i) => {
                          const scoreMap = {}
                          ;(student.scores || []).forEach(sc => { scoreMap[sc.problem_id] = sc })
                          const has100 = student.best_score === 100
                          return (
                            <tr key={student.id || i} style={{ background: has100 ? '#e8f5e9' : (i % 2 === 0 ? 'white' : '#f8f9fa') }}
                              onMouseEnter={e => e.currentTarget.style.background = '#e8f0ff'}
                              onMouseLeave={e => e.currentTarget.style.background = has100 ? '#e8f5e9' : (i % 2 === 0 ? 'white' : '#f8f9fa')}>
                              <td style={{ padding: '9px 14px', textAlign: 'center', borderBottom: '1px solid #e9ecef' }}>
                                <span style={{ background: `${gradeColor(student.grade)}18`, color: gradeColor(student.grade), padding: '2px 8px', borderRadius: 8, fontWeight: 700, fontSize: 12 }}>
                                  {student.grade || '—'}
                                </span>
                              </td>
                              <td style={{ padding: '9px 14px', textAlign: 'center', borderBottom: '1px solid #e9ecef', fontSize: 12, color: '#666' }}>
                                {student.class_num ? `${student.class_num}班` : '—'}
                              </td>
                              <td style={{ padding: '9px 14px', textAlign: 'center', borderBottom: '1px solid #e9ecef', fontSize: 13, fontWeight: 600, color: '#333' }}>
                                {student.display_name || student.username || '—'}
                              </td>
                              <td style={{ padding: '9px 14px', textAlign: 'center', borderBottom: '1px solid #e9ecef', fontSize: 12, color: '#666', fontFamily: 'monospace' }}>
                                {student.student_number || '—'}
                              </td>
                              {problems2.map(p => {
                                const sc = scoreMap[p.problem_id]
                                const info = scoreColor(sc?.score ?? null)
                                return (
                                  <td key={p.problem_id} style={{
                                    padding: '9px 10px', textAlign: 'center', borderBottom: '1px solid #e9ecef',
                                    background: info.bg, color: info.color, fontWeight: 700, fontSize: 13,
                                  }}>
                                    {info.text}
                                  </td>
                                )
                              })}
                              {problems2.length === 0 && (
                                <td style={{ padding: '9px 14px', textAlign: 'center', color: '#aaa', borderBottom: '1px solid #e9ecef' }}>—</td>
                              )}
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* 图例 */}
                <div style={{ marginTop: 12, display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12, color: '#666' }}>
                  <span style={{ fontWeight: 600 }}>图例：</span>
                  {[
                    { bg: '#d4edda', color: '#155724', label: '优秀 (≥90)' },
                    { bg: '#d1ecf1', color: '#0c5460', label: '良好 (75-89)' },
                    { bg: '#fff3cd', color: '#856404', label: '及格 (60-74)' },
                    { bg: '#f8d7da', color: '#721c24', label: '不及格 (<60)' },
                    { bg: '#f8f9fa', color: '#6c757d', label: '未提交' },
                  ].map(l => (
                    <span key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span style={{ width: 13, height: 13, borderRadius: 3, background: l.bg, border: `1px solid ${l.color}40`, display: 'inline-block' }}></span>
                      <span style={{ color: l.color }}>{l.label}</span>
                    </span>
                  ))}
                </div>
              </div>

              {/* 满分灯矩阵 */}
              <div style={{
                background: 'white', borderRadius: 14, padding: '18px 20px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                display: 'flex', flexDirection: 'column', gap: 10, minWidth: 340,
              }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#333', textAlign: 'center' }}>满分监控 · 学号1-50</div>
                <div style={{ display: 'grid', gridTemplateColumns: `repeat(${COLS}, 1fr)`, gap: 5 }}>
                  {Array.from({ length: ROWS * COLS }, (_, idx) => {
                    const lampNum = idx + 1
                    const is100 = (scoreMapByNum[lampNum] || 0) === 100
                    return (
                      <div key={idx} title={`学号${lampNum} ${is100 ? '✓ 满分' : '未满分'}`}
                        style={{
                          width: 28, height: 28, borderRadius: 5,
                          background: is100 ? '#4caf50' : '#2a2a2a',
                          boxShadow: is100 ? '0 0 8px #4caf50' : 'inset 0 1px 3px rgba(0,0,0,0.5)',
                          border: `1px solid ${is100 ? '#81c784' : '#444'}`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 10, fontWeight: 700,
                          color: is100 ? '#fff' : '#555',
                          transition: 'background 0.3s, box-shadow 0.3s',
                        }}>
                        {lampNum}
                      </div>
                    )
                  })}
                </div>
                <div style={{ fontSize: 11, color: '#888', textAlign: 'center' }}>
                  {Object.values(scoreMapByNum).filter(v => v === 100).length}/{ROWS * COLS} 满分
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* 题目详情弹窗 */}
      {detailModal.open && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px',
        }} onClick={() => setDetailModal({ open: false, problem: null })}>
          <div style={{
            background: 'white', borderRadius: 16, padding: '28px', maxWidth: 600, width: '100%',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)', maxHeight: '80vh', overflowY: 'auto',
          }} onClick={e => e.stopPropagation()}>
            {detailLoading ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>加载中...</div>
            ) : detailModal.problem ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                  <div>
                    <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>{detailModal.problem.title}</h2>
                    <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                      编号 {detailModal.problem.problem_id} · {detailModal.problem.difficulty}
                    </div>
                  </div>
                  <button onClick={() => setDetailModal({ open: false, problem: null })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}>
                    <X size={20} />
                  </button>
                </div>
                <div style={{ background: '#f8f9fa', borderRadius: 10, padding: '14px 16px', fontSize: 14, color: '#333', lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
                  {detailModal.problem.description || '（无描述）'}
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
