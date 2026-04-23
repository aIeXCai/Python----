import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, BookOpen, BarChart3, ListChecks, Plus, Edit2, Trash2, Eye, EyeOff,
  X, Upload, CheckCircle, AlertCircle, RefreshCw, ToggleLeft, ToggleRight, FileText
} from 'lucide-react'

const API = 'http://localhost:8080/api'
const GRADES = ['七年级', '八年级', '九年级', '高一', '高二', '高三']
const DIFFICULTY_COLORS = { easy: '#38ef7d', medium: '#f59e0b', hard: '#ef4444' }

export default function InfoAdmin() {
  const navigate = useNavigate()
  const [tab, setTab] = useState('units')
  const token = localStorage.getItem('token')
  const headers = { 'Authorization': `Token ${token}`, 'Content-Type': 'application/json' }

  // ─── Tab0: 单元管理 ────────────────────────────────────────────────────────────
  const [bigUnits, setBigUnits] = useState([])        // 大单元（嵌套 sections）
  const [allUnits, setAllUnits] = useState([])         // 拍平：所有单元（Tab1 用）
  const [unitGradeFilter, setUnitGradeFilter] = useState('七年级')
  const [expandedUnits, setExpandedUnits] = useState(new Set())
  const [newBigUnitOpen, setNewBigUnitOpen] = useState(false)
  const [sectionModal, setSectionModal] = useState({ open: false, bigUnit: null })
  const [unitForm, setUnitForm] = useState({ grade: '七年级', name: '', display_name: '' })
  const [unitMsg, setUnitMsg] = useState({ type: '', text: '' })
  const [editUnit, setEditUnit] = useState(null)

  // ─── Tab1: 题库（年级-大单元-小节 三级筛选）──────────────────────────────
  const [qGradeFilter, setQGradeFilter] = useState('七年级')   // 年级筛选
  const [qBigUnitFilter, setQBigUnitFilter] = useState('')      // 大单元筛选
  const [qBigUnits, setQBigUnits] = useState([])               // 当前年级下的大单元列表
  const [qAllUnits, setQAllUnits] = useState([])               // 当前年级下拍平的单元列表
  const [questions, setQuestions] = useState([])
  const [qLoading, setQLoading] = useState(true)
  const [filterUnit, setFilterUnit] = useState('')
  const [qModal, setQModal] = useState({ open: false, mode: 'create', data: null })
  const [qForm, setQForm] = useState({
    unit: '', difficulty: 'easy', category: '',
    text: '', option_a: '', option_b: '', option_c: '', option_d: '', answer: 'A', explanation: ''
  })
  const [qMsg, setQMsg] = useState({ type: '', text: '' })
  const [qSaving, setQSaving] = useState(false)

  const [importData, setImportData] = useState('')
  const [importMsg, setImportMsg] = useState({ type: '', text: '' })

  // ─── Tab1: 批量导入弹窗 ────────────────────────────────────────────────
  const [importModal, setImportModal] = useState({ open: false, unit: '', grade: '七年级', file: null })
  const [importFileName, setImportFileName] = useState('')
  const [importPreview, setImportPreview] = useState(null)   // 预览解析出的题目数
  const [importing, setImporting] = useState(false)

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
  const [selectedQuiz, setSelectedQuiz] = useState('') // 选中某次小测，用于灯阵

  const ROWS = 5, COLS = 10

  // ─── 加载单元数据（Tab0 + Tab1 共用）───────────────────────────────────────
  const loadUnits = async (grade) => {
    try {
      const url = grade ? `${API}/admin/info/units/?grade=${encodeURIComponent(grade)}` : `${API}/admin/info/units/`
      const res = await fetch(url, { headers })
      if (!res.ok) return
      const data = await res.json()
      setBigUnits(data)  // 嵌套格式，Tab0 用

      // 拍平：所有大单元 + 所有小节，Tab1 筛选下拉用
      const flat = []
      data.forEach(big => {
        flat.push(big)
        ;(big.sections || []).forEach(sec => flat.push(sec))
      })
      setAllUnits(flat)
    } catch (e) { console.error(e) }
  }

  // ─── Tab0 切换年级后重新加载
  useEffect(() => { loadUnits(unitGradeFilter) }, [unitGradeFilter])

  // ─── Tab1: 年级-大单元-小节三级筛选加载 ───────────────────────────────────
  const loadQUnits = async (grade) => {
    try {
      const url = `${API}/admin/info/units/?grade=${encodeURIComponent(grade)}`
      const res = await fetch(url, { headers })
      if (!res.ok) return
      const data = await res.json()
      setQBigUnits(data)
      const flat = []
      data.forEach(big => {
        flat.push(big)
        ;(big.sections || []).forEach(sec => flat.push(sec))
      })
      setQAllUnits(flat)
    } catch (e) { console.error(e) }
  }
  useEffect(() => {
    loadQUnits(qGradeFilter)
    setQBigUnitFilter('')
    setFilterUnit('')
  }, [qGradeFilter])

  // Tab1 依赖 allUnits（不重新请求，只用已有数据）
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
  useEffect(() => { loadQuestions() }, [filterUnit])

  // ─── Tab0 操作函数 ────────────────────────────────────────────────────────
  const toggleUnit = (id) => setExpandedUnits(prev => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })

  const openNewBigUnit = () => {
    setUnitForm({ grade: unitGradeFilter, name: '', display_name: '' })
    setUnitMsg({ type: '', text: '' })
    setNewBigUnitOpen(true)
  }

  const openAddSection = (bigUnit) => {
    setUnitForm({ grade: bigUnit.grade, name: '', display_name: '' })
    setUnitMsg({ type: '', text: '' })
    setSectionModal({ open: true, bigUnit })
  }

  // 创建大单元
  const handleCreateBigUnit = async (e) => {
    e.preventDefault()
    if (!unitForm.display_name.trim()) { setUnitMsg({ type: 'error', text: '名称不能为空' }); return }
    try {
      // name 用拼音序号生成（不暴露给用户）
      const name = `u${Date.now()}`
      const res = await fetch(`${API}/admin/info/units/`, {
        method: 'POST', headers,
        body: JSON.stringify({ grade: unitForm.grade, name, display_name: unitForm.display_name.trim(), order: 0 })
      })
      const data = await res.json()
      if (res.ok) {
        setNewBigUnitOpen(false)
        loadUnits(unitGradeFilter)
      } else {
        setUnitMsg({ type: 'error', text: JSON.stringify(data) })
      }
    } catch (e) { setUnitMsg({ type: 'error', text: e.message }) }
    setTimeout(() => setUnitMsg({ type: '', text: '' }), 4000)
  }

  // 新增小节
  const handleSaveSection = async (e) => {
    e.preventDefault()
    if (!unitForm.display_name.trim()) { setUnitMsg({ type: 'error', text: '名称不能为空' }); return }
    if (!sectionModal.bigUnit) return
    try {
      const name = `s${Date.now()}`
      const res = await fetch(`${API}/admin/info/units/`, {
        method: 'POST', headers,
        body: JSON.stringify({ grade: sectionModal.bigUnit.grade, parent: sectionModal.bigUnit.id, name, display_name: unitForm.display_name.trim(), order: 0 })
      })
      const data = await res.json()
      if (res.ok) {
        setSectionModal({ open: false, bigUnit: null })
        loadUnits(unitGradeFilter)
      } else {
        setUnitMsg({ type: 'error', text: JSON.stringify(data) })
      }
    } catch (e) { setUnitMsg({ type: 'error', text: e.message }) }
    setTimeout(() => setUnitMsg({ type: '', text: '' }), 4000)
  }

  // 删除单元
  const deleteUnit = async (unitId) => {
    if (!window.confirm('确定删除该单元吗？该单元下所有题目也会被删除。')) return
    try {
      const res = await fetch(`${API}/admin/info/units/${unitId}/delete/`, { method: 'DELETE', headers })
      if (res.ok || res.status === 204) {
        loadUnits(unitGradeFilter)
        if (filterUnit) { setFilterUnit(''); loadQuestions() }
      }
    } catch (e) { alert('删除失败：' + e.message) }
  }

  // 更新单元
  const handleUpdateUnit = async (e) => {
    e.preventDefault()
    try {
      const body = { display_name: editUnit.display_name }
      // 小节编辑时带 parent
      if (editUnit.parent != null) body.parent = editUnit.parent
      const res = await fetch(`${API}/admin/info/units/${editUnit.id}/`, {
        method: 'PUT', headers, body: JSON.stringify(body)
      })
      if (res.ok) {
        setEditUnit(null)
        loadUnits(unitGradeFilter)
      } else {
        const data = await res.json()
        alert(JSON.stringify(data))
      }
    } catch (e) { alert('更新失败：' + e.message) }
  }

  // 打开新建题目弹窗
  const openNewQuestion = () => {
    setQForm({ unit: filterUnit || (qAllUnits.find(u => u.parent != null)?.name || ''), difficulty: 'easy', category: '',
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

  // 导入 JSON（textarea 旧方式）
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

  // 打开导入弹窗
  const openImportModal = () => {
    setImportModal({ open: true, grade: qGradeFilter, unit: '', file: null })
    setImportFileName('')
    setImportPreview(null)
    setImportMsg({ type: '', text: '' })
  }

  // 文件选择后解析预览
  const handleFileSelect = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportFileName(file.name)
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const parsed = JSON.parse(ev.target.result)
        if (Array.isArray(parsed)) {
          setImportPreview(parsed.length)
        } else if (Array.isArray(parsed.questions)) {
          setImportPreview(parsed.questions.length)
        } else {
          setImportPreview(null)
        }
      } catch {
        setImportPreview(null)
      }
    }
    reader.readAsText(file)
    const modal = { ...importModal, file }
    setImportModal(modal)
  }

  // 拖拽文件
  const handleDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (!file || !file.name.endsWith('.json')) return
    const input = document.createElement('input')
    input.type = 'file'
    const dt = new DataTransfer()
    dt.items.add(file)
    input.files = dt.files
    handleFileSelect({ target: { files: [file] } })
  }

  // 执行导入
  const doImport = async () => {
    if (!importModal.file) return
    setImporting(true)
    setImportMsg({ type: '', text: '' })
    try {
      const text = await importModal.file.text()
      let parsed
      try { parsed = JSON.parse(text) } catch { setImportMsg({ type: 'error', text: 'JSON 格式错误' }); setImporting(false); return }

      // 统一结构：可能直接是 questions 数组，也可能包装在 { questions: [...] } 里
      const questions = Array.isArray(parsed) ? parsed : (parsed.questions || [])

      const payload = {
        unit: importModal.unit,
        unit_display_name: importModal.unit,
        questions,
      }

      const res = await fetch(`${API}/admin/info/questions/import/`, {
        method: 'POST', headers, body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (res.ok) {
        setImportMsg({ type: 'success', text: `导入成功：新增 ${data.imported} 题` })
        setTimeout(() => {
          setImportModal({ open: false, unit: '', grade: '七年级', file: null })
          loadQuestions()
          loadUnits()
        }, 1500)
      } else {
        setImportMsg({ type: 'error', text: JSON.stringify(data) })
      }
    } catch (e) { setImportMsg({ type: 'error', text: e.message }) }
    setImporting(false)
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
  const loadStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const params = {}
      if (statsFilter.grade) params.grade = statsFilter.grade
      if (statsFilter.class_num) params.class_num = statsFilter.class_num
      const qs = new URLSearchParams(params).toString()
      const submissionsUrl = qs
        ? `${API}/admin/info/stats/submissions/?${qs}`
        : `${API}/admin/info/stats/submissions/`

      const [ov, ss, matrix] = await Promise.all([
        fetch(`${API}/admin/info/stats/overview/${qs ? '?' + qs : ''}`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(`${API}/admin/info/stats/sessions/${qs ? '?' + qs : ''}`, { headers }).then(r => r.ok ? r.json() : null),
        fetch(submissionsUrl, { headers }).then(r => r.ok ? r.json() : { sessions: [], students: [] }),
      ])
      setStatsOverview(ov)
      setStatsSessions(ss || [])
      setMatrixData(matrix || { sessions: [], students: [] })
    } catch (e) { console.error(e) }
    setStatsLoading(false)
  }, [statsFilter])

  // 自动刷新
  useEffect(() => {
    if (!autoRefresh || tab !== 'stats') return
    loadStats() // 立即执行一次
    const interval = setInterval(loadStats, 5000)
    return () => clearInterval(interval)
  }, [autoRefresh, tab, statsFilter, loadStats])

  const difficultyLabel = (d) => ({ easy: '简单', medium: '中等', hard: '困难' }[d] || d)

  // 成绩颜色（满分灯阵用）
  const scoreColor = (score) => {
    if (score === null || score === undefined) return { bg: '#f8f9fa', color: '#6c757d', text: '—' }
    if (score >= 90) return { bg: '#d4edda', color: '#155724', text: score }
    if (score >= 75) return { bg: '#d1ecf1', color: '#0c5460', text: score }
    if (score >= 60) return { bg: '#fff3cd', color: '#856404', text: score }
    return { bg: '#f8d7da', color: '#721c24', text: score }
  }

  const gradeColor = (g) => ({ '七年級': '#667eea', '七年级': '#667eea', '八年級': '#38ef7d', '八年级': '#38ef7d', '九年級': '#f59e0b', '九年级': '#f59e0b', '初一': '#667eea', '初二': '#38ef7d', '初三': '#f59e0b' }[g] || '#888')
  const gradeDisplay = (g) => ({ '初一': '七年级', '初二': '八年级', '初三': '九年级' }[g] || g || '—')

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
        color: 'white', padding: '12px 0', boxShadow: '0 2px 10px rgba(0,0,0,0.15)',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px', display: 'flex', alignItems: 'center', gap: 14 }}>
          <button onClick={() => navigate('/teacher/dashboard')} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(255,255,255,0.15)', border: 'none', borderRadius: 8,
            color: 'white', cursor: 'pointer', padding: '7px 14px', fontSize: 13, fontWeight: 600,
          }}><ArrowLeft size={14} /> 返回主页</button>
          <div style={{ width: 1, height: 24, background: 'rgba(255,255,255,0.25)' }} />
          <ListChecks size={20} />
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>信息科技课管理</h1>

          {/* Tab 切换（移入 header） */}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 10, padding: 4 }}>
            {[
              { key: 'units',    label: '单元管理', icon: ListChecks },
              { key: 'questions', label: '题库管理', icon: BookOpen },
              { key: 'sessions',  label: '小测管理', icon: ListChecks },
              { key: 'stats',     label: '成绩统计', icon: BarChart3 },
            ].map(({ key, label, icon: Icon }) => (
              <button key={key} onClick={() => setTab(key)} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '7px 18px', borderRadius: 8, border: 'none', cursor: 'pointer',
                fontSize: 13, fontWeight: 700,
                background: tab === key ? 'white' : 'transparent',
                color: tab === key ? '#11998e' : 'rgba(255,255,255,0.75)',
                transition: 'all 0.2s',
              }}>
                <Icon size={14} />{label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 24px' }}>

        {/* ─── Tab0: 单元管理 Grade-Unit-Section ────────────────────────────── */}
        {tab === 'units' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* 顶部栏：年级筛选 + 新建大单元 */}
            <div style={{ background: 'white', borderRadius: 14, padding: '16px 20px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <ListChecks size={18} style={{ color: '#11998e' }} />
              <span style={{ fontSize: 15, fontWeight: 700, color: '#333' }}>单元列表</span>
              <span style={{ marginLeft: 4, fontSize: 12, color: '#888' }}>共 {bigUnits.length} 个大单元</span>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#555' }}>年级</span>
                <select value={unitGradeFilter} onChange={e => setUnitGradeFilter(e.target.value)}
                  style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13, minWidth: 100 }}>
                  {[
                    { value: '七年级', label: '七年级' },
                    { value: '八年级', label: '八年级' },
                  ].map(g => <option key={g.value} value={g.value}>{g.label}</option>)}
                </select>
              </div>
              <button onClick={() => openNewBigUnit()}
                style={{ padding: '7px 16px', borderRadius: 8, border: 'none', background: '#11998e', color: 'white', cursor: 'pointer', fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Plus size={14} /> 新建大单元
              </button>
            </div>

            {/* 大单元列表（可折叠展示小节） */}
            {bigUnits.length === 0 && (
              <div style={{ background: 'white', borderRadius: 14, padding: '48px 24px', textAlign: 'center', color: '#aaa', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
                <ListChecks size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
                <p>该年级暂无大单元，请点击"新建大单元"创建</p>
              </div>
            )}

            {bigUnits.map(big => (
              <div key={big.id} style={{ background: 'white', borderRadius: 14, boxShadow: '0 2px 8px rgba(0,0,0,0.06)', overflow: 'hidden' }}>
                {/* 大单元标题行 */}
                <div style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 10,
                  background: expandedUnits.has(big.id) ? '#f0faf9' : 'white',
                  borderLeft: `4px solid ${gradeColor(unitGradeFilter)}` }}>
                  <button onClick={() => toggleUnit(big.id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#555', padding: 0, display: 'flex', alignItems: 'center' }}>
                    <span style={{ fontSize: 14, transition: 'transform 0.2s', transform: expandedUnits.has(big.id) ? 'rotate(90deg)' : 'rotate(0deg)', display: 'inline-block' }}>▶</span>
                  </button>
                  <div style={{ flex: 1 }}>
                    {editUnit && editUnit.id === big.id ? (
                      <form onSubmit={handleUpdateUnit} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <input value={editUnit.display_name} onChange={e => setEditUnit(p => ({ ...p, display_name: e.target.value }))}
                          style={{ flex: 1, padding: '4px 10px', borderRadius: 6, border: '1.5px solid #11998e', fontSize: 13 }} autoFocus />
                        <button type="submit" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#11998e' }}><CheckCircle size={16} /></button>
                        <button type="button" onClick={() => setEditUnit(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ccc' }}><X size={16} /></button>
                      </form>
                    ) : (
                      <>
                        <span style={{ fontWeight: 700, fontSize: 15, color: '#333' }}>{big.display_name || big.name}</span>
                        <span style={{ marginLeft: 8, fontSize: 12, color: '#888' }}>{big.question_count} 题 · {big.sections?.length || 0} 小节</span>
                      </>
                    )}
                  </div>
                  {!editUnit || editUnit.id !== big.id ? (
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button onClick={() => openAddSection(big)}
                        style={{ background: 'none', border: '1px solid #11998e', borderRadius: 6, cursor: 'pointer', color: '#11998e', padding: '3px 10px', fontSize: 12, fontWeight: 600 }}>+ 小节</button>
                      <button onClick={() => setEditUnit({ id: big.id, name: big.name, display_name: big.display_name || '' })}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#17a2b8', padding: 2 }}><Edit2 size={14} /></button>
                      <button onClick={() => deleteUnit(big.id)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc3545', padding: 2 }}><Trash2 size={14} /></button>
                    </div>
                  ) : null}
                </div>

                {/* 小节列表（可折叠） */}
                {expandedUnits.has(big.id) && (big.sections || []).length > 0 && (
                  <div style={{ borderTop: '1px solid #f0f0f0', background: '#fafcfb' }}>
                    {(big.sections || []).map(sec => (
                      <div key={sec.id} style={{ padding: '10px 20px 10px 56px', display: 'flex', alignItems: 'center', gap: 10, borderBottom: '1px solid #f0f0f0' }}>
                        {editUnit && editUnit.id === sec.id ? (
                          <form onSubmit={handleUpdateUnit} style={{ display: 'flex', gap: 8, alignItems: 'center', flex: 1 }}>
                            <input value={editUnit.display_name} onChange={e => setEditUnit(p => ({ ...p, display_name: e.target.value }))}
                              style={{ flex: 1, padding: '4px 10px', borderRadius: 6, border: '1.5px solid #11998e', fontSize: 13 }} autoFocus />
                            <button type="submit" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#11998e' }}><CheckCircle size={16} /></button>
                            <button type="button" onClick={() => setEditUnit(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ccc' }}><X size={16} /></button>
                          </form>
                        ) : (
                          <>
                            <span style={{ fontSize: 13, color: '#555', flex: 1 }}>{sec.display_name || sec.name}</span>
                            <span style={{ fontSize: 12, color: '#aaa' }}>{sec.question_count} 题</span>
                            <button onClick={() => setEditUnit({ id: sec.id, name: sec.name, display_name: sec.display_name || '', parent: sec.parent })}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#17a2b8', padding: 2 }}><Edit2 size={14} /></button>
                            <button onClick={() => deleteUnit(sec.id)}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc3545', padding: 2 }}><Trash2 size={14} /></button>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {expandedUnits.has(big.id) && (!big.sections || big.sections.length === 0) && (
                  <div style={{ padding: '12px 20px 12px 56px', color: '#bbb', fontSize: 13, borderTop: '1px solid #f0f0f0', background: '#fafcfb' }}>
                    暂无小节
                  </div>
                )}
              </div>
            ))}

            {/* 新建大单元弹窗 */}
            {newBigUnitOpen && (
              <ModalWrap onClose={() => setNewBigUnitOpen(false)}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                  <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>新建大单元</h2>
                  <button onClick={() => setNewBigUnitOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}><X size={20} /></button>
                </div>
                <MsgBanner msg={unitMsg} />
                <form onSubmit={handleCreateBigUnit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>年级</label>
                    <select value={unitForm.grade} onChange={e => setUnitForm(p => ({ ...p, grade: e.target.value }))}
                      style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }}>
                      <option value="七年级">七年级</option>
                      <option value="八年级">八年级</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>大单元名称 *</label>
                    <input value={unitForm.display_name} onChange={e => setUnitForm(p => ({ ...p, display_name: e.target.value }))}
                      placeholder="如：第一章 算法基础"
                      style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, boxSizing: 'border-box' }} required />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                    <button type="button" onClick={() => setNewBigUnitOpen(false)} style={{ padding: '9px 18px', borderRadius: 8, border: '1.5px solid #ddd', background: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>取消</button>
                    <button type="submit" style={{ padding: '9px 20px', borderRadius: 8, border: 'none', background: '#11998e', color: 'white', cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>创建</button>
                  </div>
                </form>
              </ModalWrap>
            )}

            {/* 新建/编辑小节弹窗 */}
            {sectionModal.open && (
              <ModalWrap onClose={() => setSectionModal({ open: false, bigUnit: null })}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                  <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>
                    {sectionModal.bigUnit ? `在"${sectionModal.bigUnit.display_name}"下新增小节` : '编辑小节'}
                  </h2>
                  <button onClick={() => setSectionModal({ open: false, bigUnit: null })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}><X size={20} /></button>
                </div>
                <MsgBanner msg={unitMsg} />
                <form onSubmit={handleSaveSection} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>所属大单元</label>
                    <input value={sectionModal.bigUnit?.display_name || ''} disabled
                      style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #eee', fontSize: 13, background: '#f5f5f5', color: '#666', boxSizing: 'border-box' }} />
                    <input type="hidden" value={sectionModal.bigUnit?.id || ''} name="parent" />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>小节名称 *</label>
                    <input value={unitForm.display_name} onChange={e => setUnitForm(p => ({ ...p, display_name: e.target.value }))}
                      placeholder="如：1.1 变量的概念"
                      style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, boxSizing: 'border-box' }} required />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                    <button type="button" onClick={() => setSectionModal({ open: false, bigUnit: null })} style={{ padding: '9px 18px', borderRadius: 8, border: '1.5px solid #ddd', background: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>取消</button>
                    <button type="submit" style={{ padding: '9px 20px', borderRadius: 8, border: 'none', background: '#11998e', color: 'white', cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>保存</button>
                  </div>
                </form>
              </ModalWrap>
            )}
          </div>
        )}

        {/* ─── Tab1: 题库管理 ─────────────────────────────────────────────── */}
        {tab === 'questions' && (
          <div style={{ display: 'flex, flexDirection: column', gap: 24 }}>

            {/* 题目列表卡片 */}
            <div style={{ background: 'white', borderRadius: 14, overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              <div style={{ padding: '18px 24px', borderBottom: '2px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <BookOpen size={18} style={{ color: '#11998e' }} />
                <span style={{ fontSize: 15, fontWeight: 700, color: '#333' }}>题目列表</span>
                <span style={{ marginLeft: 4, fontSize: 12, color: '#888' }}>共 {questions.length} 题</span>

                {/* 年级筛选 */}
                <select value={qGradeFilter} onChange={e => setQGradeFilter(e.target.value)}
                  style={{ padding: '6px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, minWidth: 90 }}>
                  <option value="七年级">七年级</option>
                  <option value="八年级">八年级</option>
                </select>

                {/* 大单元筛选 */}
                <select value={qBigUnitFilter} onChange={e => { setQBigUnitFilter(e.target.value); setFilterUnit('') }}
                  style={{ padding: '6px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, minWidth: 160 }}>
                  <option value="">全部大单元</option>
                  {qBigUnits.map(b => (
                    <option key={b.id} value={b.name}>{b.display_name || b.name}</option>
                  ))}
                </select>

                {/* 小节/单元筛选 */}
                <select value={filterUnit} onChange={e => setFilterUnit(e.target.value)}
                  style={{ padding: '6px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, minWidth: 160 }}>
                  <option value="">全部小节</option>
                  {qAllUnits
                    .filter(u => u.parent != null)                                    // 只要小节
                    .filter(u => qBigUnitFilter === '' || u.parent?.name === qBigUnitFilter)  // 属于选中大单元
                    .map(u => (
                    <option key={u.id} value={u.name}>
                      {'　└ '}{u.display_name || u.name}
                    </option>
                  ))}
                </select>

                <button onClick={openImportModal} style={{
                  padding: '7px 16px', borderRadius: 8, border: '1.5px solid #667eea', background: 'white', color: '#667eea',
                  cursor: 'pointer', fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6,
                }}><FileText size={14} /> 导入本地文件</button>
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

{/* ─── Tab3: 成绩统计（对标AI成绩页：左成绩表+右满分灯阵）───── */}
        {tab === 'stats' && (
          <div>
            {/* 筛选栏 */}
            <div style={{ background: 'white', borderRadius: 14, padding: '16px 20px', boxShadow: '0 2px 8px rgba(0,0,0,0.06)', marginBottom: 20, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#555' }}>年级</span>
                <select value={statsFilter.grade} onChange={e => setStatsFilter(f => ({ ...f, grade: e.target.value }))} style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13, minWidth: 90 }}>
                  <option value="">全部年级</option>
                  {[
                    { value: '七年级', label: '七年级' },
                    { value: '八年级', label: '八年级' },
                    { value: '九年级', label: '九年级' },
                    { value: '高一', label: '高一' },
                    { value: '高二', label: '高二' },
                    { value: '高三', label: '高三' },
                  ].map(g => <option key={g.value} value={g.value}>{g.label}</option>)}
                </select>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#555' }}>班级</span>
                <select value={statsFilter.class_num} onChange={e => setStatsFilter(f => ({ ...f, class_num: e.target.value }))} style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13, minWidth: 80 }}>
                  <option value="">全部班级</option>
                  {[1,2,3,4,5,6,7,8].map(c => <option key={c} value={c}>{c}班</option>)}
                </select>
              </div>
              {/* 小测选择 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: '#555' }}>小测</span>
                <select
                  value={selectedQuiz}
                  onChange={e => setSelectedQuiz(e.target.value)}
                  style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13, minWidth: 200, background: selectedQuiz ? '#f0f7ff' : '#fafafa' }}
                >
                  <option value="">— 全部小测 —</option>
                  {matrixData.sessions.map(s => (
                    <option key={s.id} value={String(s.id)}>{s.title || `小测${s.id}`}</option>
                  ))}
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

            {statsLoading ? (
              <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>加载中...</div>
            ) : (
              <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>

                {/* ── LEFT: 成绩表格 ─────────────────────────── */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  {/* 统计栏 */}
                  {(() => {
                    const si = selectedQuiz ? matrixData.sessions.findIndex(s => String(s.id) === String(selectedQuiz)) : -1
                    const totalStu = matrixData.students.length
                    let submitted = 0, sum = 0, count = 0, fullCount = 0
                    const selSession = si >= 0 ? matrixData.sessions[si] : null
                    const maxScore = selSession ? (selSession.max_score || 100) : 100
                    matrixData.students.forEach(stu => {
                      if (si >= 0 && si < stu.scores.length && stu.scores[si] !== null) {
                        const sc = stu.scores[si]
                        submitted++; sum += sc; count++
                        if (sc === maxScore) fullCount++
                      }
                    })
                    const avg = count > 0 ? (sum / count).toFixed(1) : 0
                    return (
                      <div style={{ background: '#e3f2fd', borderRadius: 12, padding: '16px 24px', marginBottom: 20, display: 'flex', gap: 40, flexWrap: 'wrap' }}>
                        {[
                          { label: '学生总数', value: totalStu, color: '#1976d2' },
                          { label: '已提交', value: submitted, color: '#1976d2' },
                          { label: '平均分', value: avg, color: '#1976d2' },
                          { label: '满分人数', value: fullCount, color: '#2e7d32' },
                        ].map(s => (
                          <div key={s.label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 80 }}>
                            <div style={{ fontSize: 24, fontWeight: 800, color: s.color }}>{s.value}</div>
                            <div style={{ fontSize: 12, color: '#5a6c7d', marginTop: 4 }}>{s.label}</div>
                          </div>
                        ))}
                      </div>
                    )
                  })()}

                  {/* 成绩表格 */}
                  {matrixData.students.length === 0 ? (
                    <div style={{ background: 'white', borderRadius: 16, padding: '60px 24px', textAlign: 'center', boxShadow: '0 2px 10px rgba(0,0,0,0.06)', color: '#888' }}>
                      <BarChart3 size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
                      <p>暂无成绩记录</p>
                    </div>
                  ) : (
                    <div style={{ background: 'white', borderRadius: 16, overflow: 'hidden', boxShadow: '0 2px 10px rgba(0,0,0,0.06)', overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 500 }}>
                        <thead>
                          <tr style={{ background: '#495057' }}>
                            <th style={{ padding: '12px 14px', color: 'white', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>年级</th>
                            <th style={{ padding: '12px 14px', color: 'white', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>班级</th>
                            <th style={{ padding: '12px 14px', color: 'white', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>姓名</th>
                            <th style={{ padding: '12px 14px', color: 'white', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>学号</th>
                            {selectedQuiz ? (() => {
                              const si = matrixData.sessions.findIndex(s => String(s.id) === String(selectedQuiz))
                              const ses = si >= 0 ? matrixData.sessions[si] : null
                              return (
                                <th style={{ padding: '12px 14px', color: '#ffd700', textAlign: 'center', fontSize: 12, fontWeight: 600 }}>
                                  {ses?.title || '该小测'}
                                </th>
                              )
                            })() : (
                              <th style={{ padding: '12px 14px', color: 'rgba(255,255,255,0.6)', textAlign: 'center', fontSize: 13 }}>选择小测查看成绩</th>
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {matrixData.students.slice().sort((a, b) => (parseInt(a.student_number) || 0) - (parseInt(b.student_number) || 0)).map((stu, i) => {
                            const si = selectedQuiz ? matrixData.sessions.findIndex(s => String(s.id) === String(selectedQuiz)) : -1
                            const score = si >= 0 && si < stu.scores.length ? stu.scores[si] : null
                            const ses = si >= 0 ? matrixData.sessions[si] : null
                            const maxScore = ses ? (ses.max_score || 100) : 100
                            const hasFull = score !== null && score === maxScore
                            const sc = score !== null ? scoreColor(score) : { bg: '#f8f9fa', color: '#6c757d', text: '—' }
                            return (
                              <tr key={stu.user_id || i}
                                style={{ background: hasFull ? '#e8f5e9' : (i % 2 === 0 ? 'white' : '#f8f9fa'), transition: 'background 0.15s' }}
                                onMouseEnter={e => e.currentTarget.style.background = '#e8f0ff'}
                                onMouseLeave={e => e.currentTarget.style.background = hasFull ? '#e8f5e9' : (i % 2 === 0 ? 'white' : '#f8f9fa')}
                              >
                                <td style={{ padding: '10px 14px', textAlign: 'center', borderBottom: '1px solid #e9ecef' }}>
                                  <span style={{ background: `${gradeColor(stu.grade)}18`, color: gradeColor(stu.grade), padding: '2px 8px', borderRadius: 8, fontWeight: 700, fontSize: 12 }}>
                                    {stu.grade || '—'}
                                  </span>
                                </td>
                                <td style={{ padding: '10px 14px', textAlign: 'center', borderBottom: '1px solid #e9ecef', fontSize: 13, color: '#666' }}>
                                  {stu.class_num ? `${stu.class_num}班` : '—'}
                                </td>
                                <td style={{ padding: '10px 14px', textAlign: 'center', borderBottom: '1px solid #e9ecef', fontSize: 14, color: '#333', fontWeight: 600 }}>
                                  {stu.display_name || '—'}
                                </td>
                                <td style={{ padding: '10px 14px', textAlign: 'center', borderBottom: '1px solid #e9ecef', fontSize: 13, color: '#666', fontFamily: 'monospace' }}>
                                  {stu.student_number || '—'}
                                </td>
                                {selectedQuiz ? (
                                  <td style={{ padding: '10px 14px', textAlign: 'center', borderBottom: '1px solid #e9ecef', background: sc.bg, color: sc.color, fontWeight: 700, fontSize: 15 }}>
                                    {sc.text}
                                  </td>
                                ) : (
                                  <td style={{ padding: '10px 14px', textAlign: 'center', color: '#aaa', fontStyle: 'italic', borderBottom: '1px solid #e9ecef' }}>—</td>
                                )}
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {/* 图例 */}
                  <div style={{ marginTop: 16, display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 12, color: '#666' }}>
                    <span>图例：</span>
                    {[
                      { bg: '#d4edda', color: '#155724', label: '满分' },
                      { bg: '#d1ecf1', color: '#0c5460', label: '优秀 (≥90)' },
                      { bg: '#fff3cd', color: '#856404', label: '良好 (75-89)' },
                      { bg: '#f8d7da', color: '#721c24', label: '及格 (60-74)' },
                      { bg: '#f8f9fa', color: '#6c757d', label: '不及格 (<60)' },
                      { bg: '#f8f9fa', color: '#6c757d', label: '未提交' },
                    ].map(l => (
                      <span key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 14, height: 14, borderRadius: 3, background: l.bg, border: `1px solid ${l.color}40`, display: 'inline-block' }}></span>
                        <span style={{ color: l.color }}>{l.label}</span>
                      </span>
                    ))}
                  </div>
                </div>

                {/* ── RIGHT: 满分灯阵 ───────────────────────── */}
                <div style={{
                  background: '#1a1a2e', borderRadius: 16, padding: '24px',
                  boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                  display: 'flex', flexDirection: 'column', gap: 12, minWidth: 360,
                }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#e0e0e0', textAlign: 'center', letterSpacing: 2 }}>
                    满分监控 · 学号1-50
                  </div>
                  {(() => {
                    const si = selectedQuiz ? matrixData.sessions.findIndex(s => String(s.id) === String(selectedQuiz)) : -1
                    const sel = si >= 0 ? matrixData.sessions[si] : null
                    const maxScore = sel ? (sel.max_score || 100) : 100
                    const scoreMap = {}
                    matrixData.students.forEach(stu => {
                      if (si >= 0 && si < stu.scores.length && stu.scores[si] !== null) {
                        const num = parseInt(stu.student_number) || 0
                        if (num >= 1 && num <= ROWS * COLS) {
                          scoreMap[num] = Math.max(scoreMap[num] || 0, stu.scores[si])
                        }
                      }
                    })
                    const fullCount = Object.values(scoreMap).length > 0
                      ? Object.values(scoreMap).filter(v => v === maxScore).length
                      : 0
                    const submittedCount = Object.keys(scoreMap).length
                    return (
                      <>
                        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${COLS}, 1fr)`, gap: 6 }}>
                          {Array.from({ length: ROWS * COLS }, (_, idx) => {
                            const lampNum = idx + 1
                            const score = scoreMap[lampNum] ?? null
                            const isFull = score !== null && score === maxScore
                            return (
                              <div key={idx} title={`学号${lampNum}${score !== null ? ` · ${score}分` : ' · 未参加'}`}
                                style={{
                                  width: 30, height: 30, borderRadius: 5,
                                  background: isFull ? '#4caf50' : score !== null ? '#b71c1c' : '#2a2a3a',
                                  boxShadow: isFull ? '0 0 10px #4caf50' : 'inset 0 1px 3px rgba(0,0,0,0.6)',
                                  border: `1px solid ${isFull ? '#81c784' : score !== null ? '#7f0000' : '#3a3a4a'}`,
                                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                                  fontSize: 11, fontWeight: 700,
                                  color: isFull ? '#fff' : '#555',
                                  transition: 'background 0.3s, box-shadow 0.3s',
                                }}
                              >{lampNum}</div>
                            )
                          })}
                        </div>
                        <div style={{ fontSize: 11, color: '#888', textAlign: 'center' }}>
                          {fullCount}/{submittedCount || '—'} 满分 · {submittedCount || 0}/{ROWS * COLS} 人提交
                        </div>
                      </>
                    )
                  })()}
                </div>

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
                  {qAllUnits.map(u => <option key={u.id} value={u.name}>{u.parent ? '　└ ' : ''}{u.display_name || u.name}</option>)}
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

      {/* ─── 批量导入弹窗 ─────────────────────────────────────────────────── */}
      {importModal.open && (
        <ModalWrap onClose={() => setImportModal({ open: false, unit: '', grade: '七年级', file: null })}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>
              <FileText size={18} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 8, color: '#667eea' }} />
              批量导入题目
            </h2>
            <button onClick={() => setImportModal({ open: false, unit: '', grade: '七年级', file: null })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}><X size={20} /></button>
          </div>

          <MsgBanner msg={importMsg} />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* 第一步：选择年级 */}
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 6 }}>步骤1：选择年级</label>
              <div style={{ display: 'flex', gap: 8 }}>
                {['七年级', '八年级'].map(g => (
                  <button key={g} onClick={() => {
                    const newGrade = g
                    setImportModal(p => ({ ...p, grade: newGrade, unit: '' }))
                  }}
                    style={{
                      padding: '7px 18px', borderRadius: 8, border: '1.5px solid',
                      borderColor: importModal.grade === g ? '#667eea' : '#ddd',
                      background: importModal.grade === g ? '#667eea' : 'white',
                      color: importModal.grade === g ? 'white' : '#555',
                      cursor: 'pointer', fontWeight: 700, fontSize: 13,
                    }}>
                    {g}
                  </button>
                ))}
              </div>
            </div>

            {/* 第二步：选择单元（小节） */}
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 6 }}>步骤2：选择目标单元（小节）</label>
              <select value={importModal.unit} onChange={e => setImportModal(p => ({ ...p, unit: e.target.value }))}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }}>
                <option value="">— 请先选择年级 —</option>
                {qBigUnits
                  .filter(b => b.grade === importModal.grade)
                  .map(big => [
                    <optgroup key={big.id} label={big.display_name || big.name}>
                      {(big.sections || []).map(sec => (
                        <option key={sec.id} value={sec.name}>{sec.display_name || sec.name}</option>
                      ))}
                    </optgroup>
                  ])
                  .flat()
                  .length === 0 ? (
                    <option value="" disabled>该年级暂无单元，请先去「单元管理」创建</option>
                  ) : (
                    qBigUnits
                      .filter(b => b.grade === importModal.grade)
                      .map(big => (
                        <optgroup key={big.id} label={big.display_name || big.name}>
                          {(big.sections || []).map(sec => (
                            <option key={sec.id} value={sec.name}>{sec.display_name || sec.name}</option>
                          ))}
                        </optgroup>
                      ))
                  )
                }
              </select>
              {importModal.unit && (
                <p style={{ margin: '6px 0 0', fontSize: 12, color: '#11998e' }}>
                  ✓ 题目将导入到：「{qBigUnits.find(b => b.sections?.some(s => s.name === importModal.unit))?.display_name} → {importModal.unit}」
                </p>
              )}
            </div>

            {/* 第三步：选择文件 */}
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 6 }}>步骤3：上传 JSON 文件</label>
              <div
                onDrop={handleDrop}
                onDragOver={e => e.preventDefault()}
                style={{
                  border: '2px dashed #667eea', borderRadius: 12,
                  padding: '32px 20px', textAlign: 'center', cursor: 'pointer',
                  background: importFileName ? '#f5f0ff' : '#fafbff',
                  transition: 'all 0.2s',
                }}
                onClick={() => document.getElementById('import-file-input').click()}
              >
                <input id="import-file-input" type="file" accept=".json" onChange={handleFileSelect} style={{ display: 'none' }} />
                {importFileName ? (
                  <>
                    <FileText size={32} style={{ color: '#667eea', marginBottom: 8 }} />
                    <p style={{ fontSize: 13, fontWeight: 700, color: '#333', margin: '0 0 4px' }}>{importFileName}</p>
                    <p style={{ fontSize: 12, color: '#11998e', margin: 0 }}>✓ 文件已选择 {importPreview !== null ? `· 解析出 ${importPreview} 道题目` : ''}</p>
                    <p style={{ fontSize: 11, color: '#aaa', margin: '8px 0 0' }}>点击重新选择文件</p>
                  </>
                ) : (
                  <>
                    <Upload size={32} style={{ color: '#667eea', marginBottom: 8 }} />
                    <p style={{ fontSize: 13, fontWeight: 700, color: '#333', margin: '0 0 4px' }}>拖拽 JSON 文件到这里</p>
                    <p style={{ fontSize: 12, color: '#888', margin: 0 }}>或点击选择文件 · 仅支持 .json 格式</p>
                  </>
                )}
              </div>
            </div>

            {/* 文件格式说明 */}
            <div style={{ background: '#f0f4ff', borderRadius: 8, padding: '12px 16px', fontSize: 12, color: '#555', lineHeight: 1.8 }}>
              <strong style={{ color: '#333' }}>JSON 文件格式示例：</strong>
              <pre style={{ margin: '8px 0 0', fontSize: 11, fontFamily: 'monospace', color: '#555', whiteSpace: 'pre-wrap' }}>
{`[
  {
    "difficulty": "easy",
    "category": "人工智能基础",
    "text": "下列关于人工智能的说法，正确的是（）",
    "options": [
      { "key": "A", "text": "人工智能就是机器人" },
      { "key": "B", "text": "人工智能能模拟人类智能" },
      { "key": "C", "text": "人工智能不需要数据" },
      { "key": "D", "text": "人工智能已经超越人类智能" }
    ],
    "answer": "B",
    "explanation": "人工智能是研究用计算机模拟人类智能行为的科学。"
  }
]`}
              </pre>
            </div>

            {/* 操作按钮 */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button onClick={() => setImportModal({ open: false, unit: '', grade: '七年级', file: null })}
                style={{ padding: '9px 18px', borderRadius: 8, border: '1.5px solid #ddd', background: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
                取消
              </button>
              <button onClick={doImport} disabled={!importModal.unit || !importModal.file || importing}
                style={{
                  padding: '9px 20px', borderRadius: 8, border: 'none',
                  background: (!importModal.unit || !importModal.file || importing) ? '#aaa' : '#667eea',
                  color: 'white', cursor: (!importModal.unit || !importModal.file || importing) ? 'not-allowed' : 'pointer',
                  fontWeight: 700, fontSize: 13,
                }}>
                {importing ? '导入中...' : '开始导入'}
              </button>
            </div>
          </div>
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
