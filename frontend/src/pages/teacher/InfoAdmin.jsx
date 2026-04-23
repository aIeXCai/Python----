import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, BookOpen, BarChart3, ListChecks, Plus, Edit2, Trash2, Eye, EyeOff,
  X, Upload, CheckCircle, AlertCircle, RefreshCw, ToggleLeft, ToggleRight
} from 'lucide-react'

const API = 'http://localhost:8080/api'
const GRADES = ['初一', '初二', '初三', '高一', '高二', '高三']
const DIFFICULTY_COLORS = { easy: '#38ef7d', medium: '#f59e0b', hard: '#ef4444' }

export default function InfoAdmin() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('units')
  const token = localStorage.getItem('token')
  const headers = { 'Authorization': `Token ${token}`, 'Content-Type': 'application/json' }

  // ─── Tab1: 题库 ────────────────────────────────────────────────────────────
  const [units, setUnits] = useState([])
  const [questions, setQuestions] = useState([])
  const [qLoading, setQLoading] = useState(true)
  const [filterUnit, setFilterUnit] = useState('')
  const [unitForm, setUnitForm] = useState({ name: '', display_name: '' })
  const [unitMsg, setUnitMsg] = useState({ type: '', text: '' })
  const [editUnit, setEditUnit] = useState(null) // { id, name, display_name }

  const [qModal, setQModal] = useState({ open: false, mode: 'create', data: null })
  const [qForm, setQForm] = useState({
    unit: '', difficulty: 'easy', category: '',
    text: '', option_a: '', option_b: '', option_c: '', option_d: '', answer: 'A', explanation: ''
  })
  const [qMsg, setQMsg] = useState({ type: '', text: '' })
  const [qSaving, setQSaving] = useState(false)

  const [importData, setImportData] = useState('')
  const [importMsg, setImportMsg] = useState({ type: '', text: '' })

  // ─── Tab2: 小测 ────────────────────────────────────────────────────────────
  const [sessions, setSessions] = useState([])
  const [sLoading, setSLoading] = useState(true)
  const [sModal, setSModal] = useState({ open: false, mode: 'create', data: null })
  const [sForm, setSForm] = useState({
    title: '', units: [], num_questions: 10,
    difficulty_ratio: { easy: 7, medium: 2, hard: 1 },
    time_limit: null, is_visible: false, visible_grades: []
  })
  const [sMsg, setSMsg] = useState({ type: '', text: '' })
  const [sSaving, setSSaving] = useState(false)

  // ─── Tab3: 统计 ────────────────────────────────────────────────────────────
  const [statsOverview, setStatsOverview] = useState(null)
  const [statsSessions, setStatsSessions] = useState([])
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsFilter, setStatsFilter] = useState({ grade: '', class_num: '' })
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [matrixData, setMatrixData] = useState({ sessions: [], students: [] })
  const [selectedSessionDetail, setSelectedSessionDetail] = useState(null) // 选中某次小测详情

  // ─── 加载题库数据 ────────────────────────────────────────────────────────
  const loadUnits = async () => {
    try {
      const res = await fetch(`${API}/admin/info/units/`, { headers })
      if (res.ok) setUnits(await res.json())
    } catch (e) { console.error(e) }
  }

  const loadQuestions = async () => {
    setQLoading(true)
    try {
      const url = filterUnit
        ? `${API}/admin/info/questions/?unit=${encodeURIComponent(filterUnit)}`
        : `${API}/admin/info/questions/`
      const res = await fetch(url, { headers })
      if (res.ok) setQuestions(await res.json())
    } catch (e) { console.error(e) }
    setQLoading(false)
  }

  useEffect(() => { loadUnits(); loadQuestions() }, [filterUnit])

  // 创建单元
  const handleCreateUnit = async (e) => {
    e.preventDefault()
    try {
      const res = await fetch(`${API}/admin/info/units/create/`, {
        method: 'POST', headers, body: JSON.stringify(unitForm)
      })
      const data = await res.json()
      if (res.ok) {
        setUnitMsg({ type: 'success', text: '单元创建成功' })
        loadUnits()
        setUnitForm({ name: '', display_name: '' })
      } else {
        setUnitMsg({ type: 'error', text: JSON.stringify(data) })
      }
    } catch (e) { setUnitMsg({ type: 'error', text: e.message }) }
    setTimeout(() => setUnitMsg({ type: '', text: '' }), 4000)
  }

  // 删除单元
  const deleteUnit = async (unitId, unitName) => {
    if (!window.confirm(`确定删除单元「${unitName}」吗？该单元下所有题目也会被删除。`)) return
    try {
      const res = await fetch(`${API}/admin/info/units/${unitId}/delete/`, { method: 'DELETE', headers })
      if (res.ok || res.status === 204) {
        loadUnits()
        if (filterUnit === unitName) setFilterUnit('')
        loadQuestions()
      }
    } catch (e) { alert('删除失败：' + e.message) }
  }

  // 更新单元
  const handleUpdateUnit = async (e) => {
    e.preventDefault()
    try {
      const res = await fetch(`${API}/admin/info/units/${editUnit.id}/`, {
        method: 'PUT', headers, body: JSON.stringify({ name: editUnit.name, display_name: editUnit.display_name })
      })
      if (res.ok) {
        setEditUnit(null)
        loadUnits()
      } else {
        const data = await res.json()
        alert(JSON.stringify(data))
      }
    } catch (e) { alert('更新失败：' + e.message) }
  }

  // 打开新建题目弹窗
  const openNewQuestion = () => {
    setQForm({ unit: filterUnit || (units[0]?.name || ''), difficulty: 'easy', category: '',
      text: '', option_a: '', option_b: '', option_c: '', option_d: '', answer: 'A', explanation: '' })
    setQMsg({ type: '', text: '' })
    setQModal({ open: true, mode: 'create', data: null })
  }

  // 打开编辑题目弹窗
  const openEditQuestion = (q) => {
    setQForm({
      unit: q.unit, difficulty: q.difficulty, category: q.category || '',
      text: q.text, option_a: q.option_a || '', option_b: q.option_b || '',
      option_c: q.option_c || '', option_d: q.option_d || '',
      answer: q.answer, explanation: q.explanation || ''
    })
    setQMsg({ type: '', text: '' })
    setQModal({ open: true, mode: 'edit', data: q })
  }

  // 保存题目（新建/编辑）
  const handleSaveQuestion = async (e) => {
    e.preventDefault()
    setQSaving(true)
    try {
      const url = qModal.mode === 'edit'
        ? `${API}/admin/info/questions/${qModal.data.id}/`
        : `${API}/admin/info/questions/create/`
      const method = qModal.mode === 'edit' ? 'PUT' : 'POST'
      const res = await fetch(url, { method, headers, body: JSON.stringify(qForm) })
      const data = await res.json()
      if (res.ok || res.status === 200) {
        setQMsg({ type: 'success', text: qModal.mode === 'edit' ? '修改成功' : '创建成功' })
        setTimeout(() => setQModal({ open: false, mode: 'create', data: null }), 1200)
        loadQuestions()
        loadUnits()
      } else {
        setQMsg({ type: 'error', text: JSON.stringify(data) })
      }
    } catch (e) { setQMsg({ type: 'error', text: e.message }) }
    setQSaving(false)
  }

  // 删除题目
  const deleteQuestion = async (q) => {
    if (!window.confirm(`确定删除题目「${q.text.slice(0, 20)}」吗？`)) return
    try {
      const res = await fetch(`${API}/admin/info/questions/${q.id}/delete/`, { method: 'DELETE', headers })
      if (res.ok || res.status === 204) {
        loadQuestions()
        loadUnits()
      }
    } catch (e) { alert('删除失败：' + e.message) }
  }

  // 导入 JSON
  const handleImport = async (e) => {
    e.preventDefault()
    if (!importData.trim()) return
    let parsed
    try { parsed = JSON.parse(importData) } catch { setImportMsg({ type: 'error', text: 'JSON 格式错误' }); return }
    try {
      const res = await fetch(`${API}/admin/info/questions/import/`, {
        method: 'POST', headers, body: JSON.stringify(parsed)
      })
      const data = await res.json()
      if (res.ok) {
        setImportMsg({ type: 'success', text: `导入成功：新增 ${data.imported} 题` })
        setImportData('')
        loadQuestions()
        loadUnits()
      } else {
        setImportMsg({ type: 'error', text: JSON.stringify(data) })
      }
    } catch (e) { setImportMsg({ type: 'error', text: e.message }) }
    setTimeout(() => setImportMsg({ type: '', text: '' }), 5000)
  }

  // ─── 加载小测数据 ────────────────────────────────────────────────────────
  const loadSessions = async () => {
    setSLoading(true)
    try {
      const res = await fetch(`${API}/admin/info/sessions/`, { headers })
      if (res.ok) setSessions(await res.json())
    } catch (e) { console.error(e) }
    setSLoading(false)
  }

  useEffect(() => { if (tab === 'sessions') loadSessions() }, [tab])
  useEffect(() => { if (tab === 'stats') loadStats() }, [tab])

  // 打开新建小测弹窗
  const openNewSession = () => {
    setSForm({ title: '', units: [], num_questions: 10,
      difficulty_ratio: { easy: 7, medium: 2, hard: 1 },
      time_limit: null, is_visible: false, visible_grades: [] })
    setSMsg({ type: '', text: '' })
    setSModal({ open: true, mode: 'create', data: null })
  }

  // 打开编辑小测弹窗
  const openEditSession = (s) => {
    setSForm({
      title: s.title, units: s.units, num_questions: s.num_questions,
      difficulty_ratio: s.difficulty_ratio || { easy: 7, medium: 2, hard: 1 },
      time_limit: s.time_limit, is_visible: s.is_visible,
      visible_grades: s.visible_grades || []
    })
    setSMsg({ type: '', text: '' })
    setSModal({ open: true, mode: 'edit', data: s })
  }

  // 保存小测
  const handleSaveSession = async (e) => {
    e.preventDefault()
    if (!sForm.title.trim()) { setSMsg({ type: 'error', text: '请填写标题' }); return }
    if (sForm.units.length === 0) { setSMsg({ type: 'error', text: '请选择至少一个单元' }); return }
    setSSaving(true)
    try {
      const url = sModal.mode === 'edit'
        ? `${API}/admin/info/sessions/${sModal.data.id}/`
        : `${API}/admin/info/sessions/create/`
      const method = sModal.mode === 'edit' ? 'PUT' : 'POST'
      const res = await fetch(url, { method, headers, body: JSON.stringify(sForm) })
      const data = await res.json()
      if (res.ok || res.status === 200) {
        setSMsg({ type: 'success', text: sModal.mode === 'edit' ? '修改成功' : '创建成功' })
        setTimeout(() => setSModal({ open: false, mode: 'create', data: null }), 1200)
        loadSessions()
      } else {
        setSMsg({ type: 'error', text: JSON.stringify(data) })
      }
    } catch (e) { setSMsg({ type: 'error', text: e.message }) }
    setSSaving(false)
  }

  // 删除小测
  const deleteSession = async (s) => {
    if (!window.confirm(`确定删除小测「${s.title}」吗？`)) return
    try {
      const res = await fetch(`${API}/admin/info/sessions/${s.id}/delete/`, { method: 'DELETE', headers })
      if (res.ok || res.status === 204) loadSessions()
    } catch (e) { alert('删除失败：' + e.message) }
  }

  // 切换可见性
  const toggleSession = async (s) => {
    try {
      const res = await fetch(`${API}/admin/info/sessions/${s.id}/toggle/`, {
        method: 'PATCH', headers,
        body: JSON.stringify({ is_visible: !s.is_visible, visible_grades: s.visible_grades || [] })
      })
      if (res.ok) loadSessions()
    } catch (e) { console.error(e) }
  }

  // ─── 加载统计数据 ────────────────────────────────────────────────────────
  const loadStats = async () => {
    setStatsLoading(true)
    try {
      const params = {}
      if (statsFilter.grade) params.grade = statsFilter.grade
      if (statsFilter.class_num) params.class_num = statsFilter.class_num
      const qs = new URLSearchParams(params).toString()

      const [ov, ss, matrix] = await Promise.all([
        fetch(`${API}/admin/info/stats/overview/`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API}/admin/info/stats/sessions/`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API}/admin/info/stats/submissions/${qs ? '?' + qs : ''}`, { headers }).then(r => r.ok ? r.json() : { sessions: [], students: [] })),
      ])
      setStatsOverview(ov)
      setStatsSessions(ss || [])
      setMatrixData(matrix || { sessions: [], students: [] })
    } catch (e) { console.error(e) }
    setStatsLoading(false)
  }

  // 自动刷新
  useEffect(() => {
    if (!autoRefresh || tab !== 'stats') return
    const interval = setInterval(loadStats, 30000)
    return () => clearInterval(interval)
  }, [autoRefresh, tab, statsFilter])

  const difficultyLabel = (d) => ({ easy: '简单', medium: '中等', hard: '困难' }[d] || d)

  // ─── 渲染 ────────────────────────────────────────────────────────────────
  const Badge = ({ children, color }) => (
    <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: `${color}22`, color }}>{children}</span>
  )

  const MsgBanner = ({ msg }) => !msg.text ? null : (
    <div style={{
      padding: '10px 16px', borderRadius: 8, marginBottom: 16, fontSize: 13, fontWeight: 600,
      background: msg.type === 'success' ? '#d4edda' : '#f8d7da',
      color: msg.type === 'success' ? '#155724' : '#721c24',
      border: `1px solid ${msg.type === 'success' ? '#c3e6cb' : '#f5c6cb'}`
    }}>{msg.text}</div>
  )

  return (
    <div style={{ minHeight: '100vh', background: '#f5f7fa', fontFamily: '"Microsoft JhengHei", Arial, sans-serif' }}>
      {/* Header */}
      <header style={{
        background: 'linear-gradient(135deg, #11998e 0%, #0e7a6d 100%)',
        color: 'white', padding: '16px 0', boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <button onClick={() => navigate('/teacher/dashboard')} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: 8,
            color: 'white', cursor: 'pointer', padding: '8px 14px', fontSize: 13, fontWeight: 600,
          }}><ArrowLeft size={14} /> 返回主页</button>
          <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.25)' }} />
          <ListChecks size={20} />
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>信息科技课管理</h1>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 24px' }}>
        {/* Tab 切换 */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 28, background: '#e8e8e8', borderRadius: 12, padding: 4, width: 'fit-content' }}>
          {[
            { key: 'units',    label: '单元管理', icon: <ListChecks size={15} /> },
            { key: 'questions', label: '题库管理', icon: <BookOpen size={15} /> },
            { key: 'sessions',  label: '小测管理', icon: <ListChecks size={15} /> },
            { key: 'stats',     label: '成绩统计', icon: <BarChart3 size={15} /> },
          ].map(t => (
            <button key={t.key} onClick={() => setTab(t.key)} style={{
              padding: '9px 20px', borderRadius: 9, border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: 13,
              display: 'flex', alignItems: 'center', gap: 6,
              background: tab === t.key ? 'white' : 'transparent',
              color: tab === t.key ? '#11998e' : '#666',
              boxShadow: tab === t.key ? '0 1px 4px rgba(0,0,0,0.1)' : 'none',
              transition: 'all 0.15s',
            }}>{t.icon} {t.label}</button>
          ))}
        </div>

        {/* ─── Tab0: 单元管理 ──────────────────────────────────────────────── */}
        {tab === 'units' && (
          <div style={{ background: 'white', borderRadius: 14, padding: '24px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
              <ListChecks size={20} style={{ color: '#11998e' }} />
              <span style={{ fontSize: 16, fontWeight: 700, color: '#333' }}>单元列表</span>
              <span style={{ marginLeft: 'auto', fontSize: 12, color: '#888' }}>共 {units.length} 个单元</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 24 }}>
              {units.map(u => (
                <div key={u.id} style={{
                  padding: '10px 14px', borderRadius: 10, border: '2px solid #e0e0e0',
                  display: 'flex', alignItems: 'center', gap: 10, background: 'white', minWidth: 180,
                }}>
                  {editUnit && editUnit.id === u.id ? (
                    <form onSubmit={handleUpdateUnit} style={{ display: 'flex', gap: 4, alignItems: 'center', flex: 1 }}>
                      <input value={editUnit.display_name} onChange={e => setEditUnit(p => ({ ...p, display_name: e.target.value }))}
                        style={{ flex: 1, padding: '4px 8px', borderRadius: 6, border: '1.5px solid #11998e', fontSize: 13 }} autoFocus />
                      <button type="submit" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#11998e', padding: 2 }}><CheckCircle size={16} /></button>
                      <button type="button" onClick={() => setEditUnit(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ccc', padding: 2 }}><X size={16} /></button>
                    </form>
                  ) : (
                    <>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, color: '#333', fontSize: 14 }}>{u.display_name || u.name}</div>
                        <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>{u.question_count} 题</div>
                      </div>
                      <button onClick={() => setEditUnit({ id: u.id, name: u.name, display_name: u.display_name || '' })} title="编辑" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#17a2b8', padding: 2 }}><Edit2 size={14} /></button>
                      <button onClick={() => deleteUnit(u.id, u.name)} title="删除" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc3545', padding: 2 }}><Trash2 size={14} /></button>
                    </>
                  )}
                </div>
              ))}
              {units.length === 0 && <span style={{ color: '#aaa', fontSize: 13 }}>暂无单元，请先创建一个</span>}
            </div>
            <div style={{ borderTop: '2px solid #f0f0f0', paddingTop: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#555', marginBottom: 10 }}>+ 新建单元</div>
              <form onSubmit={handleCreateUnit} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <input placeholder="name（如 unit_1）" value={unitForm.name} onChange={e => setUnitForm(p => ({ ...p, name: e.target.value }))}
                  style={{ padding: '8px 12px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, width: 160 }} />
                <input placeholder="显示名称（如 第一单元）" value={unitForm.display_name} onChange={e => setUnitForm(p => ({ ...p, display_name: e.target.value }))}
                  style={{ padding: '8px 12px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, flex: 1 }} />
                <button type="submit" style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: '#11998e', color: 'white', cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>创建</button>
              </form>
              <MsgBanner msg={unitMsg} />
            </div>
          </div>
        )}

        {/* ─── Tab1: 题库管理 ─────────────────────────────────────────────── */}
        {tab === 'questions' && (
          <div style={{ display: 'flex, flexDirection: column', gap: 24 }}>

            {/* 题目列表卡片 */}
            <div style={{ background: 'white', borderRadius: 14, overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div style={{ padding: '18px 24px', borderBottom: '2px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <BookOpen size={18} style={{ color: '#11998e' }} />
                <span style={{ fontSize: 15, fontWeight: 700, color: '#333' }}>题目列表</span>
                <span style={{ marginLeft: 'auto', fontSize: 12, color: '#888' }}>共 {questions.length} 题</span>
                <select value={filterUnit} onChange={e => setFilterUnit(e.target.value)}
                  style={{ padding: '6px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }}>
                  <option value="">全部单元</option>
                  {units.map(u => <option key={u.id} value={u.name}>{u.display_name || u.name}</option>)}
                </select>
                <button onClick={openNewQuestion} style={{
                  padding: '7px 16px', borderRadius: 8, border: 'none', background: '#11998e', color: 'white',
                  cursor: 'pointer', fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6,
                }}><Plus size={14} /> 新建题目</button>
              </div>

              {qLoading ? <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>加载中...</div>
                : questions.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 40, color: '#888' }}><BookOpen size={40} style={{ opacity: 0.3, marginBottom: 12 }} /><p>暂无题目</p></div>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ background: '#f8f9fa' }}>
                          {['#', '单元', '难度', '题目摘要', '答案', '操作'].map(h => (
                            <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 700, color: '#666', whiteSpace: 'nowrap' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {questions.map((q, i) => (
                          <tr key={q.id} style={{ borderBottom: '1px solid #f0f0f0' }}
                            onMouseEnter={e => e.currentTarget.style.background = '#f8f9fa'}
                            onMouseLeave={e => e.currentTarget.style.background = 'white'}>
                            <td style={{ padding: '10px 14px', color: '#888' }}>{i + 1}</td>
                            <td style={{ padding: '10px 14px' }}><Badge color="#667eea">{q.unit_name || q.unit}</Badge></td>
                            <td style={{ padding: '10px 14px' }}>
                              <Badge color={DIFFICULTY_COLORS[q.difficulty] || '#888'}>{difficultyLabel(q.difficulty)}</Badge>
                            </td>
                            <td style={{ padding: '10px 14px', color: '#333', maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{q.text}</td>
                            <td style={{ padding: '10px 14px', fontWeight: 800, color: '#11998e' }}>{q.answer}</td>
                            <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>
                              <button onClick={() => openEditQuestion(q)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#17a2b8', padding: '4px', display: 'inline-flex' }}><Edit2 size={14} /></button>
                              <button onClick={() => deleteQuestion(q)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc3545', padding: '4px', display: 'inline-flex', marginLeft: 6 }}><Trash2 size={14} /></button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
            </div>

            {/* JSON 导入卡片 */}
            <div style={{ background: 'white', borderRadius: 14, padding: '24px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                <Upload size={18} style={{ color: '#11998e' }} />
                <span style={{ fontSize: 15, fontWeight: 700, color: '#333' }}>JSON 批量导入</span>
              </div>
              <div style={{ background: '#f0f4ff', borderRadius: 8, padding: '12px 16px', marginBottom: 16, fontSize: 12, color: '#555', lineHeight: 1.8 }}>
                <strong>格式：</strong>
                <code style={{ background: '#e0e0e0', padding: '1px 4px', borderRadius: 3 }}>{'{"unit":"unit_1","unit_display_name":"第一单元","questions":[{"text":"...","answer":"A","difficulty":"easy","options":[{"key":"A","text":"..."}]}]}'}</code>
              </div>
              <textarea rows={6} value={importData} onChange={e => setImportData(e.target.value)}
                placeholder="粘贴 JSON..." style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, fontFamily: 'monospace', boxSizing: 'border-box', resize: 'vertical' }} />
              <div style={{ marginTop: 12 }}>
                <button onClick={handleImport} style={{ padding: '9px 20px', borderRadius: 8, border: 'none', background: '#667eea', color: 'white', cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>导入</button>
              </div>
              <MsgBanner msg={importMsg} />
            </div>
          </div>
        )}

        {/* ─── Tab2: 小测管理 ─────────────────────────────────────────────── */}
        {tab === 'sessions' && (
          <div>
            <div style={{ background: 'white', borderRadius: 14, overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', marginBottom: 24 }}>
              <div style={{ padding: '18px 24px', borderBottom: '2px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 12 }}>
                <ListChecks size={18} style={{ color: '#11998e' }} />
                <span style={{ fontSize: 15, fontWeight: 700, color: '#333' }}>小测列表</span>
                <span style={{ marginLeft: 'auto', fontSize: 12, color: '#888' }}>共 {sessions.length} 个</span>
                <button onClick={openNewSession} style={{
                  padding: '8px 16px', borderRadius: 8, border: 'none', background: '#11998e', color: 'white',
                  cursor: 'pointer', fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6,
                }}><Plus size={14} /> 新建小测</button>
              </div>
              {sLoading ? <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>加载中...</div>
                : sessions.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 40, color: '#888' }}><ListChecks size={40} style={{ opacity: 0.3, marginBottom: 12 }} /><p>暂无小测</p></div>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ background: '#f8f9fa' }}>
                          {['标题', '单元', '题数', '可见', '已交/总数', '创建时间', '操作'].map(h => (
                            <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 700, color: '#666', whiteSpace: 'nowrap' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sessions.map(s => (
                          <tr key={s.id} style={{ borderBottom: '1px solid #f0f0f0' }}
                            onMouseEnter={e => e.currentTarget.style.background = '#f8f9fa'}
                            onMouseLeave={e => e.currentTarget.style.background = 'white'}>
                            <td style={{ padding: '10px 14px', fontWeight: 600, color: '#333' }}>{s.title}</td>
                            <td style={{ padding: '10px 14px', fontSize: 12, color: '#666' }}>{(s.unit_names || []).join(', ')}</td>
                            <td style={{ padding: '10px 14px' }}>{s.num_questions}</td>
                            <td style={{ padding: '10px 14px' }}>
                              <button onClick={() => toggleSession(s)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 13, color: s.is_visible ? '#38ef7d' : '#ccc' }}>
                                {s.is_visible ? <Eye size={15} /> : <EyeOff size={15} />}
                                {s.is_visible ? '已发布' : '未发布'}
                              </button>
                            </td>
                            <td style={{ padding: '10px 14px' }}>
                              <span style={{ color: '#11998e', fontWeight: 700 }}>{s.submission_count}</span>
                              <span style={{ color: '#888' }}> 人</span>
                            </td>
                            <td style={{ padding: '10px 14px', color: '#888', fontSize: 12 }}>{new Date(s.created_at).toLocaleDateString('zh-CN')}</td>
                            <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>
                              <button onClick={() => openEditSession(s)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#17a2b8', padding: '4px', display: 'inline-flex' }}><Edit2 size={14} /></button>
                              <button onClick={() => deleteSession(s)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc3545', padding: '4px', display: 'inline-flex', marginLeft: 6 }}><Trash2 size={14} /></button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
            </div>
          </div>
        )}

{/* ─── Tab3: 成绩统计 ─────────────────────────────────────────────── */}
        {tab === 'stats' && (
          <div>
            {/* 筛选栏 */}
            <div style={{ background: 'white', borderRadius: 14, padding: '16px 20px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', marginBottom: 20, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              {/* 年级 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#555' }}>年级</span>
                <select value={statsFilter.grade} onChange={e => setStatsFilter(f => ({ ...f, grade: e.target.value }))} style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13, minWidth: 90 }}>
                  <option value="">全部年级</option>
                  {['初一', '初二', '初三', '高一', '高二', '高三'].map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>

              {/* 班级 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#555' }}>班级</span>
                <select value={statsFilter.class_num} onChange={e => setStatsFilter(f => ({ ...f, class_num: e.target.value }))} style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13, minWidth: 80 }}>
                  <option value="">全部班级</option>
                  {[1,2,3,4,5,6,7,8].map(c => <option key={c} value={c}>{c}班</option>)}
                </select>
              </div>

              <button onClick={loadStats} style={{ padding: '6px 16px', borderRadius: 8, border: 'none', background: '#667eea', color: 'white', fontSize: 13, cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                <RefreshCw size={13} /> 刷新
              </button>

              <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 13, color: '#555' }}>
                <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} style={{ width: 15, height: 15 }} />
                自动刷新
              </label>
            </div>

            {statsLoading ? <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>加载中...</div> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                {/* 全局概览 */}
                {statsOverview && (
                  <>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 16 }}>
                      {[
                        { label: '小测总数', value: statsOverview.total_sessions, color: '#667eea' },
                        { label: '提交总数', value: statsOverview.total_submissions, color: '#11998e' },
                        { label: '平均分', value: statsOverview.avg_score, color: '#f59e0b' },
                        { label: '中位分 P50', value: statsOverview.p50_score, color: '#38ef7d' },
                        { label: '高分线 P90', value: statsOverview.p90_score, color: '#ef4444' },
                      ].map(stat => (
                        <div key={stat.label} style={{ background: 'white', borderRadius: 12, padding: '20px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', textAlign: 'center' }}>
                          <div style={{ fontSize: 28, fontWeight: 800, color: stat.color }}>{stat.value ?? '—'}</div>
                          <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>{stat.label}</div>
                        </div>
                      ))}
                    </div>

                    {/* 分数段分布 */}
                    {statsOverview.score_distribution && (
                      <div style={{ background: 'white', borderRadius: 14, padding: '24px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#333', marginBottom: 16 }}>分数段分布</div>
                        <div style={{ display: 'flex', height: 24, borderRadius: 12, overflow: 'hidden' }}>
                          {Object.entries(statsOverview.score_distribution).map(([range, count]) => {
                            const total = Object.values(statsOverview.score_distribution).reduce((a, b) => a + b, 0) || 1
                            const pct = Math.round(count / total * 100)
                            const colors = { '0-60': '#ef4444', '60-80': '#f59e0b', '80-100': '#38ef7d' }
                            return pct > 0 ? (
                              <div key={range} style={{ flex: pct, background: colors[range], display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: pct < 8 ? 0 : 40 }}>
                                {pct >= 8 && <span style={{ color: 'white', fontWeight: 800, fontSize: 12 }}>{pct}%</span>}
                              </div>
                            ) : null
                          })}
                        </div>
                        <div style={{ display: 'flex', gap: 16, marginTop: 10, justifyContent: 'center' }}>
                          {[['#ef4444', '0-60 分'], ['#f59e0b', '60-80 分'], ['#38ef7d', '80-100 分']].map(([c, l]) => (
                            <span key={l} style={{ fontSize: 12, color: '#666', display: 'flex', alignItems: 'center', gap: 4 }}>
                              <span style={{ width: 10, height: 10, borderRadius: 2, background: c, display: 'inline-block' }} />{l}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}

                {/* 各小测成绩表 */}
                {statsSessions.length > 0 && (
                  <div style={{ background: 'white', borderRadius: 14, padding: '24px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#333', marginBottom: 16 }}>各小测成绩总览</div>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead>
                          <tr style={{ background: '#f8f9fa' }}>
                            {['小测', '年级', '提交人数', '平均分', '最高分', '最低分'].map(h => <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontWeight: 700, color: '#666' }}>{h}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {statsSessions.map(s => (
                            <tr key={s.session_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                              <td style={{ padding: '8px 14px', fontWeight: 600 }}>{s.title}</td>
                              <td style={{ padding: '8px 14px', color: '#667eea', fontWeight: 600 }}>{s.grade || '—'}</td>
                              <td style={{ padding: '8px 14px' }}>{s.total_submissions ?? 0} 人</td>
                              <td style={{ padding: '8px 14px', color: '#11998e', fontWeight: 700 }}>{s.avg_score ?? '—'}</td>
                              <td style={{ padding: '8px 14px', color: '#38ef7d' }}>{s.max_score ?? '—'}</td>
                              <td style={{ padding: '8px 14px', color: '#ef4444' }}>{s.min_score ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* 满分矩阵 */}
                {matrixData.sessions.length > 0 && (
                  <div style={{ background: 'white', borderRadius: 14, padding: '24px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: '#333' }}>满分矩阵</div>
                      <div style={{ fontSize: 12, color: '#888' }}>
                        {matrixData.students.length} 名学生 × {matrixData.sessions.length} 次小测
                      </div>
                    </div>
                    <div style={{ overflowX: 'auto', maxHeight: 500, overflowY: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 600 }}>
                        <thead style={{ position: 'sticky', top: 0, zIndex: 2 }}>
                          <tr style={{ background: '#f1f3f5' }}>
                            <th style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 700, color: '#555', position: 'sticky', left: 0, background: '#f1f3f5', zIndex: 3, minWidth: 80, borderRight: '2px solid #e0e0e0' }}>姓名</th>
                            <th style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 700, color: '#555', minWidth: 60 }}>班级</th>
                            <th style={{ padding: '8px 12px', textAlign: 'center', fontWeight: 700, color: '#555', minWidth: 50 }}>均分</th>
                            {matrixData.sessions.map(s => (
                              <th key={s.id} style={{ padding: '8px 10px', textAlign: 'center', fontWeight: 700, color: '#555', minWidth: 80, whiteSpace: 'nowrap' }}>{s.title || `小测${s.id}`}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {matrixData.students.map(stu => {
                            const scores = stu.scores
                            const avgScore = scores.filter(s => s !== null).length > 0
                              ? (scores.filter(s => s !== null).reduce((a, b) => a + b, 0) / scores.filter(s => s !== null).length).toFixed(1)
                              : null
                            return (
                              <tr key={stu.user_id} style={{ borderBottom: '1px solid #f0f0f0' }}>
                                <td style={{ padding: '6px 12px', fontWeight: 600, color: '#333', position: 'sticky', left: 0, background: 'white', zIndex: 1, borderRight: '2px solid #e0e0e0' }}>{stu.display_name}</td>
                                <td style={{ padding: '6px 12px', color: '#888' }}>{stu.grade} {stu.class_num}班</td>
                                <td style={{ padding: '6px 12px', textAlign: 'center', fontWeight: 700, color: avgScore ? (avgScore >= 80 ? '#11998e' : avgScore >= 60 ? '#f59e0b' : '#ef4444') : '#ccc' }}>{avgScore !== null ? avgScore : '—'}</td>
                                {scores.map((score, si) => {
                                  if (score === null) return <td key={si} style={{ padding: '6px 8px', textAlign: 'center', color: '#ccc', background: '#fafafa' }}>—</td>
                                  const pct = score // 满分100
                                  const bg = pct >= 80 ? '#d4edda' : pct >= 60 ? '#fff3cd' : '#f8d7da'
                                  const color = pct >= 80 ? '#155724' : pct >= 60 ? '#856404' : '#721c24'
                                  return <td key={si} style={{ padding: '6px 8px', textAlign: 'center', background: bg, color, fontWeight: 700, borderRadius: 4 }}>{score}</td>
                                })}
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* 无筛选结果时 */}
                {!statsOverview && !statsLoading && (
                  <div style={{ textAlign: 'center', padding: 60, color: '#aaa', background: 'white', borderRadius: 14 }}>
                    暂无统计数据
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* ─── 题目弹窗 ─────────────────────────────────────────────────────── */}
      {qModal.open && (
        <ModalWrap onClose={() => setQModal({ open: false, mode: 'create', data: null })}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>
              {qModal.mode === 'edit' ? '编辑题目' : '新建题目'}
            </h2>
            <button onClick={() => setQModal({ open: false, mode: 'create', data: null })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}><X size={20} /></button>
          </div>
          <MsgBanner msg={qMsg} />
          <form onSubmit={handleSaveQuestion} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>所属单元 *</label>
                <select value={qForm.unit} onChange={e => setQForm(p => ({ ...p, unit: e.target.value }))}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }} required>
                  <option value="">选择单元</option>
                  {units.map(u => <option key={u.id} value={u.name}>{u.display_name || u.name}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>难度</label>
                <select value={qForm.difficulty} onChange={e => setQForm(p => ({ ...p, difficulty: e.target.value }))}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }}>
                  <option value="easy">简单</option><option value="medium">中等</option><option value="hard">困难</option>
                </select>
              </div>
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>题目内容 *</label>
              <textarea value={qForm.text} onChange={e => setQForm(p => ({ ...p, text: e.target.value }))} rows={3}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, resize: 'vertical', boxSizing: 'border-box' }} required />
            </div>
            {['A', 'B', 'C', 'D'].map(opt => (
              <div key={opt}>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>选项 {opt}</label>
                <input value={qForm[`option_${opt.toLowerCase()}`]} onChange={e => setQForm(p => ({ ...p, [`option_${opt.toLowerCase()}`]: e.target.value }))}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }} />
              </div>
            ))}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>正确答案 *</label>
                <select value={qForm.answer} onChange={e => setQForm(p => ({ ...p, answer: e.target.value }))}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }}>
                  {['A', 'B', 'C', 'D'].map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>分类（可选）</label>
                <input value={qForm.category} onChange={e => setQForm(p => ({ ...p, category: e.target.value }))}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }} />
              </div>
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>解析（可选）</label>
              <textarea value={qForm.explanation} onChange={e => setQForm(p => ({ ...p, explanation: e.target.value }))} rows={2}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, resize: 'vertical', boxSizing: 'border-box' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 4 }}>
              <button type="button" onClick={() => setQModal({ open: false, mode: 'create', data: null })} style={{ padding: '9px 18px', borderRadius: 8, border: '1.5px solid #ddd', background: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>取消</button>
              <button type="submit" disabled={qSaving} style={{ padding: '9px 20px', borderRadius: 8, border: 'none', background: qSaving ? '#aaa' : '#11998e', color: 'white', cursor: qSaving ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 13 }}>
                {qSaving ? '保存中...' : '保存'}
              </button>
            </div>
          </form>
        </ModalWrap>
      )}

      {/* ─── 小测弹窗 ─────────────────────────────────────────────────────── */}
      {sModal.open && (
        <ModalWrap onClose={() => setSModal({ open: false, mode: 'create', data: null })}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>
              {sModal.mode === 'edit' ? '编辑小测' : '新建小测'}
            </h2>
            <button onClick={() => setSModal({ open: false, mode: 'create', data: null })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}><X size={20} /></button>
          </div>
          <MsgBanner msg={sMsg} />
          <form onSubmit={handleSaveSession} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>小测标题 *</label>
              <input value={sForm.title} onChange={e => setSForm(p => ({ ...p, title: e.target.value }))}
                placeholder="如：第一章 认识算法"
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, boxSizing: 'border-box' }} required />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 6 }}>选择单元 *（可多选）</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {units.map(u => (
                  <label key={u.id} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', padding: '5px 10px', borderRadius: 6, border: '1.5px solid #ddd', fontSize: 13 }}>
                    <input type="checkbox" checked={sForm.units.includes(u.id)}
                      onChange={e => {
                        const checked = e.target.checked
                        setSForm(p => ({
                          ...p, units: checked ? [...p.units, u.id] : p.units.filter(id => id !== u.id)
                        }))
                      }} />
                    {u.display_name || u.name}
                  </label>
                ))}
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>抽题数量 *</label>
                <input type="number" min={1} value={sForm.num_questions} onChange={e => setSForm(p => ({ ...p, num_questions: parseInt(e.target.value) }))}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }} required />
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>时间限制（分钟，选填）</label>
                <input type="number" min={1} value={sForm.time_limit || ''} onChange={e => setSForm(p => ({ ...p, time_limit: e.target.value ? parseInt(e.target.value) : null }))}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }} />
              </div>
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>发布状态</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <button type="button" onClick={() => setSForm(p => ({ ...p, is_visible: !p.is_visible }))}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: 13, background: sForm.is_visible ? '#38ef7d' : '#ccc', color: 'white' }}>
                  {sForm.is_visible ? <Eye size={14} /> : <EyeOff size={14} />}
                  {sForm.is_visible ? '已发布（学生可见）' : '未发布'}
                </button>
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 4 }}>
              <button type="button" onClick={() => setSModal({ open: false, mode: 'create', data: null })} style={{ padding: '9px 18px', borderRadius: 8, border: '1.5px solid #ddd', background: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>取消</button>
              <button type="submit" disabled={sSaving} style={{ padding: '9px 20px', borderRadius: 8, border: 'none', background: sSaving ? '#aaa' : '#11998e', color: 'white', cursor: sSaving ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 13 }}>
                {sSaving ? '保存中...' : '保存'}
              </button>
            </div>
          </form>
        </ModalWrap>
      )}
    </div>
  )
}

// 通用弹窗包装
function ModalWrap({ children, onClose }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }} onClick={onClose}>
      <div style={{ background: 'white', borderRadius: 16, padding: '28px', maxWidth: 560, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)', maxHeight: '88vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
        {children}
      </div>
    </div>
  )
}
