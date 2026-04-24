import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, ClipboardList, BarChart2, ListChecks, X, Home } from 'lucide-react'

import Tab0Units from './tabs/Tab0Units'
import Tab1Questions from './tabs/Tab1Questions'
import Tab2Sessions from './tabs/Tab2Sessions'
import Tab3Stats from './tabs/Tab3Stats'

const API = 'http://localhost:8080/api'
const DIFFICULTY_COLORS = { easy: '#38ef7d', medium: '#f59e0b', hard: '#ef4444' }

// ── 工具函数 ────────────────────────────────────────────────────────────────
const difficultyLabel = d => ({ easy: '容易', medium: '中等', hard: '困难' }[d] || d)
const gradeColor = g => ({ '七年级': '#38ef7d', '八年级': '#11999e', '九年级': '#f59e0b' }[g] || '#888')
const gradeDisplay = g => ({ '七年级': '七年级', '八年级': '八年级', '九年级': '九年级' }[g] || g)
const scoreColor = s => {
  if (s == null || s === '') return '#ccc'
  if (s >= 90) return '#38ef7d'
  if (s >= 75) return '#11999e'
  if (s >= 60) return '#f59e0b'
  return '#ef4444'
}

// ── 样式常量 ────────────────────────────────────────────────────────────────
const TABS = [
  { key: 'units', label: '单元管理', icon: ListChecks },
  { key: 'questions', label: '题库管理', icon: BookOpen },
  { key: 'sessions', label: '小测管理', icon: ClipboardList },
  { key: 'stats', label: '成绩统计', icon: BarChart2 },
]

// ── 主组件 ──────────────────────────────────────────────────────────────────
export default function InfoAdmin() {
  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json', 'Authorization': `Token ${token}` }

  // Tab 状态
  const [tab, setTab] = useState('units')

  // ── Tab0: 单元 ────────────────────────────────────────────────────────────
  const [bigUnits, setBigUnits] = useState([])
  const [unitGradeFilter, setUnitGradeFilter] = useState('七年级')
  const [expandedUnits, setExpandedUnits] = useState(new Set())
  const [newBigUnitOpen, setNewBigUnitOpen] = useState(false)
  const [sectionModal, setSectionModal] = useState({ open: false, bigUnit: null })
  const [editUnit, setEditUnit] = useState(null)
  const [unitForm, setUnitForm] = useState({ name: '', display_name: '', grade: '七年级' })
  const [unitMsg, setUnitMsg] = useState({ type: '', text: '' })

  // ── Tab1: 题库 ────────────────────────────────────────────────────────────
  const [questions, setQuestions] = useState([])
  const [qLoading, setQLoading] = useState(false)
  const [qGradeFilter, setQGradeFilter] = useState('七年级')
  const [qBigUnits, setQBigUnits] = useState([])
  const [qBigUnitFilter, setQBigUnitFilter] = useState('')
  const [qAllUnits, setQAllUnits] = useState([])
  const [filterUnit, setFilterUnit] = useState('')
  const [selectedQuestions, setSelectedQuestions] = useState([])
  const [qModal, setQModal] = useState({ open: false, mode: 'create', data: null })
  const [qForm, setQForm] = useState({ unit: '', difficulty: 'easy', text: '', option_a: '', option_b: '', option_c: '', option_d: '', answer: 'A', category: '', explanation: '' })
  const [qMsg, setQMsg] = useState({ type: '', text: '' })
  const [qSaving, setQSaving] = useState(false)
  const [importModal, setImportModal] = useState({ open: false, unit: '', grade: '七年级', file: null })
  const [importFileName, setImportFileName] = useState('')
  const [importPreview, setImportPreview] = useState(null)
  const [importing, setImporting] = useState(false)
  const [importMsg, setImportMsg] = useState({ type: '', text: '' })

  // ── Tab2: 小测 ────────────────────────────────────────────────────────────
  const [sessions, setSessions] = useState([])
  const [sLoading, setSLoading] = useState(false)
  const [sModal, setSModal] = useState({ open: false, mode: 'create', data: null })
  const [sForm, setSForm] = useState({ name: '', grade: '七年级', unit: '', duration: 30, question_count: 10 })
  const [sMsg, setSMsg] = useState({ type: '', text: '' })
  const [sSaving, setSSaving] = useState(false)

  // ── Tab3: 成绩 ────────────────────────────────────────────────────────────
  const [statsData, setStatsData] = useState(null)
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsFilter, setStatsFilter] = useState({ grade: '七年级', class_num: '' })
  const [selectedQuiz, setSelectedQuiz] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(false)

  // ── 工具函数 ─────────────────────────────────────────────────────────────
  const toggleUnit = id => {
    setExpandedUnits(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  // ── Tab0: 单元 CRUD ───────────────────────────────────────────────────────
  const loadUnits = useCallback(async () => {
    const res = await fetch(`${API}/admin/info/units/?grade=${unitGradeFilter}`, { headers })
    const data = await res.json()
    setBigUnits(Array.isArray(data) ? data : [])
  }, [unitGradeFilter, headers])

  useEffect(() => { if (tab === 'units') loadUnits() }, [tab, loadUnits])

  const openNewBigUnit = () => {
    setUnitForm({ name: '', display_name: '', grade: unitGradeFilter })
    setUnitMsg({ type: '', text: '' })
    setNewBigUnitOpen(true)
  }

  const handleCreateBigUnit = async e => {
    e.preventDefault()
    const res = await fetch(`${API}/admin/info/units/`, {
      method: 'POST', headers,
      body: JSON.stringify({ ...unitForm, order: bigUnits.length + 1 })
    })
    const data = await res.json()
    if (res.ok) {
      setUnitMsg({ type: 'success', text: '创建成功！' })
      setNewBigUnitOpen(false)
      loadUnits()
    } else {
      setUnitMsg({ type: 'error', text: JSON.stringify(data) })
    }
  }

  const openAddSection = bigUnit => {
    setUnitForm({ name: '', display_name: '', grade: bigUnit.grade })
    setUnitMsg({ type: '', text: '' })
    setSectionModal({ open: true, bigUnit })
  }

  const handleSaveSection = async e => {
    e.preventDefault()
    const res = await fetch(`${API}/admin/info/units/`, {
      method: 'POST', headers,
      body: JSON.stringify({
        name: unitForm.display_name, display_name: unitForm.display_name,
        grade: sectionModal.bigUnit.grade, parent: sectionModal.bigUnit.id, order: 1
      })
    })
    const data = await res.json()
    if (res.ok) {
      setUnitMsg({ type: 'success', text: '小节创建成功！' })
      setSectionModal({ open: false, bigUnit: null })
      loadUnits()
      if (qGradeFilter === sectionModal.bigUnit.grade) loadQUnits()
    } else {
      setUnitMsg({ type: 'error', text: JSON.stringify(data) })
    }
  }

  const handleUpdateUnit = async e => {
    e.preventDefault()
    if (!editUnit) return
    const res = await fetch(`${API}/admin/info/units/${editUnit.id}/`, {
      method: 'PUT', headers,
      body: JSON.stringify({ display_name: editUnit.display_name })
    })
    if (res.ok) { setEditUnit(null); loadUnits() }
    else { const d = await res.json(); alert('更新失败: ' + JSON.stringify(d)) }
  }

  const deleteUnit = async id => {
    if (!confirm('确认删除？')) return
    await fetch(`${API}/admin/info/units/${id}/delete/`, { method: 'DELETE', headers })
    loadUnits()
  }

  // ── Tab1: 题库 CRUD ───────────────────────────────────────────────────────
  const loadQUnits = async () => {
    const g = qGradeFilter
    const res = await fetch(`${API}/admin/info/units/?grade=${g}`, { headers })
    const data = await res.json()
    setQBigUnits(Array.isArray(data) ? data : [])
    const all = Array.isArray(data)
      ? data.flatMap(b => [{ ...b, parent: null }, ...(b.sections || []).map(s => ({ ...s, parent: b }))])
      : []
    setQAllUnits(all)
  }

  const loadQuestions = useCallback(async () => {
    setQLoading(true)
    try {
      const params = new URLSearchParams({ grade: qGradeFilter })
      if (qBigUnitFilter) params.set('big_unit_name', qBigUnitFilter)
      if (filterUnit) params.set('unit', filterUnit)
      const res = await fetch(`${API}/admin/info/questions/?${params}`, { headers })
      const data = await res.json()
      setQuestions(Array.isArray(data) ? data : [])
    } finally { setQLoading(false) }
  }, [qGradeFilter, qBigUnitFilter, filterUnit, headers])

  useEffect(() => { if (tab === 'questions') { loadQUnits(); loadQuestions() } }, [tab])

  // 年级切换时重置大/小单元筛选并重新加载
  useEffect(() => {
    if (tab === 'questions') {
      setQBigUnitFilter('')
      setFilterUnit('')
      setSelectedQuestions([])
      loadQUnits()
      loadQuestions()
    }
  }, [qGradeFilter])

  const handleApplyFilter = () => {
    setSelectedQuestions([])
    loadQuestions()
  }

  const handleSelectAll = checked => {
    if (checked) setSelectedQuestions(questions.map(q => q.id))
    else setSelectedQuestions([])
  }

  const handleSelectOne = id => {
    setSelectedQuestions(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  const handleBatchDelete = async () => {
    if (!window.confirm(`确定删除选中的 ${selectedQuestions.length} 道题目？此操作不可恢复。`)) return
    setQLoading(true)
    try {
      await Promise.all(selectedQuestions.map(id =>
        fetch(`${API}/admin/info/questions/${id}/delete/`, { method: 'DELETE', headers })
      ))
      setSelectedQuestions([])
      loadQuestions()
    } finally { setQLoading(false) }
  }

  const openNewQuestion = () => {
    setQForm({ unit: '', difficulty: 'easy', text: '', option_a: '', option_b: '', option_c: '', option_d: '', answer: 'A', category: '', explanation: '' })
    setQMsg({ type: '', text: '' })
    setQModal({ open: true, mode: 'create', data: null })
  }

  const openEditQuestion = q => {
    setQForm({
      unit: q.unit || q.unit_name || '', difficulty: q.difficulty || 'easy',
      text: q.text, option_a: q.option_a || '', option_b: q.option_b || '',
      option_c: q.option_c || '', option_d: q.option_d || '',
      answer: q.answer || 'A', category: q.category || '', explanation: q.explanation || ''
    })
    setQMsg({ type: '', text: '' })
    setQModal({ open: true, mode: 'edit', data: q })
  }

  const handleSaveQuestion = async e => {
    e.preventDefault()
    setQSaving(true)
    try {
      const payload = { ...qForm, grade: qGradeFilter }
      const url = qModal.mode === 'edit' ? `${API}/admin/info/questions/${qModal.data.id}/` : `${API}/admin/info/questions/`
      const res = await fetch(url, { method: qModal.mode === 'edit' ? 'PUT' : 'POST', headers, body: JSON.stringify(payload) })
      const data = await res.json()
      if (res.ok) {
        setQMsg({ type: 'success', text: qModal.mode === 'edit' ? '更新成功！' : '创建成功！' })
        if (qModal.mode === 'edit') setQModal(p => ({ ...p, data: { ...p.data, ...qForm } }))
        loadQuestions()
      } else {
        setQMsg({ type: 'error', text: JSON.stringify(data) })
      }
    } finally { setQSaving(false) }
  }

  const deleteQuestion = async q => {
    if (!confirm(`删除题目：${q.text.slice(0, 20)}...？`)) return
    await fetch(`${API}/admin/info/questions/${q.id}/delete/`, { method: 'DELETE', headers })
    loadQuestions()
  }

  const openImportModal = () => {
    setImportModal({ open: true, unit: '', grade: qGradeFilter, file: null })
    setImportFileName(''); setImportPreview(null); setImportMsg({ type: '', text: '' })
    loadQUnits()
  }

  const handleFileSelect = e => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = ev => {
      try {
        const parsed = JSON.parse(ev.target.result)
        const arr = Array.isArray(parsed) ? parsed : []
        setImportModal(p => ({ ...p, file }))
        setImportFileName(file.name)
        setImportPreview(arr.length)
      } catch { alert('JSON 解析失败，请检查文件格式') }
    }
    reader.readAsText(file)
  }

  const handleDrop = e => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (!file) return
    handleFileSelect({ target: { files: [file], value: '' } })
    // 复用 handleFileSelect
    const reader = new FileReader()
    reader.onload = ev => {
      try {
        const parsed = JSON.parse(ev.target.result)
        const arr = Array.isArray(parsed) ? parsed : []
        setImportModal(p => ({ ...p, file }))
        setImportFileName(file.name)
        setImportPreview(arr.length)
      } catch { alert('JSON 解析失败') }
    }
    reader.readAsText(file)
  }

  const doImport = async () => {
    if (!importModal.file) return
    setImporting(true)
    setImportMsg({ type: '', text: '' })
    try {
      const text = await importModal.file.text()
      const questions = JSON.parse(text)
      const big = qBigUnits.find(b => b.sections?.some(s => s.name === importModal.unit))
      const sec = qBigUnits.flatMap(b => b.sections || []).find(s => s.name === importModal.unit)
      const res = await fetch(`${API}/admin/info/questions/import/`, {
        method: 'POST', headers,
        body: JSON.stringify({
          unit: importModal.unit,
          unit_display_name: sec?.display_name || importModal.unit,
          grade: importModal.grade,
          questions
        })
      })
      const data = await res.json()
      if (res.ok) {
        setImportMsg({ type: 'success', text: `成功导入 ${data.imported || questions.length} 道题目！` })
        loadQuestions()
        setTimeout(() => setImportModal(p => ({ ...p, open: false })), 1500)
      } else {
        setImportMsg({ type: 'error', text: JSON.stringify(data) })
      }
    } catch (err) { setImportMsg({ type: 'error', text: '文件读取失败: ' + err.message }) }
    finally { setImporting(false) }
  }

  // ── Tab2: 小测 CRUD ───────────────────────────────────────────────────────
  const loadSessions = useCallback(async () => {
    setSLoading(true)
    try {
      const params = new URLSearchParams()
      if (unitGradeFilter) params.set('grade', unitGradeFilter)
      const res = await fetch(`${API}/admin/info/sessions/?${params}`, { headers })
      const data = await res.json()
      setSessions(Array.isArray(data) ? data : [])
    } finally { setSLoading(false) }
  }, [unitGradeFilter, headers])

  useEffect(() => { if (tab === 'sessions') loadSessions() }, [tab])

  const openNewSession = () => {
    setSForm({ name: '', grade: unitGradeFilter, units: [], duration: 30, question_count: 10, difficulty_ratio: { easy: 10 } })
    setSMsg({ type: '', text: '' })
    setSModal({ open: true, mode: 'create', data: null })
  }

  const openEditSession = s => {
    // s.units 是后端返回的 [unit_id, ...] 数组，直接用
    setSForm({ name: s.title, grade: s.grade || s.visible_grades?.[0] || '七年级', units: s.units || [], duration: s.time_limit || 30, question_count: s.num_questions || 10, difficulty_ratio: s.difficulty_ratio || { easy: 10 } })
    setSMsg({ type: '', text: '' })
    setSModal({ open: true, mode: 'edit', data: s })
  }

  const handleSaveSession = async e => {
    e.preventDefault()
    setSSaving(true)
    try {
      // 字段映射：前端 sForm → 后端 QuizSessionCreateSerializer
      const payload = {
        title:            sForm.name,
        units:            sForm.units,                    // [unit_id, ...] 多选
        num_questions:    sForm.question_count,
        difficulty_ratio: sForm.difficulty_ratio || { easy: 10 },
        time_limit:       sForm.duration,
        is_visible:       false,
        visible_grades:   sForm.grade ? [sForm.grade] : [],
      }
      const url = sModal.mode === 'edit'
        ? `${API}/admin/info/sessions/${sModal.data.id}/`
        : `${API}/admin/info/sessions/create/`
      const res = await fetch(url, { method: sModal.mode === 'edit' ? 'PUT' : 'POST', headers, body: JSON.stringify(payload) })
      const data = await res.json()
      if (res.ok) {
        setSMsg({ type: 'success', text: '保存成功！' })
        setTimeout(() => { setSModal({ open: false, mode: 'create', data: null }); loadSessions() }, 1000)
      } else { setSMsg({ type: 'error', text: JSON.stringify(data) }) }
    } finally { setSSaving(false) }
  }

  const deleteSession = async s => {
    if (!confirm(`删除小测"${s.title}"？`)) return
    await fetch(`${API}/admin/info/sessions/${s.id}/delete/`, { method: 'DELETE', headers })
    loadSessions()
  }

  const handleStartSession = async id => {
    await fetch(`${API}/admin/info/sessions/${id}/toggle/`, {
      method: 'PATCH', headers,
      body: JSON.stringify({ is_visible: true, visible_grades: [] })
    })
    loadSessions()
  }

  const handleEndSession = async id => {
    await fetch(`${API}/admin/info/sessions/${id}/toggle/`, {
      method: 'PATCH', headers,
      body: JSON.stringify({ is_visible: false, visible_grades: [] })
    })
    loadSessions()
  }

  // ── Tab3: 成绩统计 ─────────────────────────────────────────────────────────
  const loadStats = useCallback(async () => {
    setStatsLoading(true)
    try {
      const params = new URLSearchParams()
      if (statsFilter.grade) params.set('grade', statsFilter.grade)
      if (statsFilter.class_num) params.set('class_num', statsFilter.class_num)
      if (selectedQuiz) params.set('session_id', selectedQuiz)
      const sessionsParams = new URLSearchParams()
      if (statsFilter.grade) sessionsParams.set('grade', statsFilter.grade)
      const [sessionsRes, studentsRes] = await Promise.all([
        fetch(`${API}/admin/info/stats/sessions/?${sessionsParams}`, { headers }),
        fetch(`${API}/admin/info/stats/submissions/?${params}`, { headers }),
      ])
      const sessionsData = await sessionsRes.json()
      const studentsData = await studentsRes.json()
      // sessions from /stats/sessions/ endpoint (array) vs /stats/submissions/ endpoint ({sessions:[...]})
      const sessionsFromEndpoint = Array.isArray(sessionsData) ? sessionsData : (sessionsData.sessions || [])
      const sessionsFromSubs = studentsData.sessions || []
      // use sessions from submissions endpoint (has id+title) as primary, fallback to sessions endpoint
      const finalSessions = sessionsFromSubs.length > 0 ? sessionsFromSubs : sessionsFromEndpoint.map(s => ({
        id: s.session_id || s.id,
        title: s.title,
        is_visible: s.is_visible,
      }))
      setStatsData({ sessions: finalSessions, students: studentsData.students || [], scores: studentsData.scores || [] })
    } catch { setStatsData(null) }
    finally { setStatsLoading(false) }
  }, [API, headers, statsFilter, selectedQuiz])

  useEffect(() => { if (tab === 'stats') loadStats() }, [tab])

  // ── 渲染 ───────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#f0f4f8', overflow: 'hidden' }}>

      {/* 顶部标题栏 */}
      <div style={{
        background: 'linear-gradient(135deg, #11999e 0%, #0e6066 100%)',
        padding: '16px 24px', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
        boxShadow: '0 2px 12px rgba(17,153,158,0.3)'
      }}>
        <button onClick={() => navigate('/teacher')} style={{
          padding: '6px 14px', borderRadius: 20, border: '1.5px solid rgba(255,255,255,0.7)',
          background: 'rgba(255,255,255,0.15)', color: 'white',
          cursor: 'pointer', fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <Home size={14} /> 返回主页
        </button>
        <ListChecks size={24} style={{ color: 'white' }} />
        <h1 style={{ fontSize: 18, fontWeight: 800, color: 'white', margin: 0 }}>信息课管理</h1>
        <div style={{ display: 'flex', gap: 6, marginLeft: 'auto', flexWrap: 'wrap' }}>
          {TABS.map(t => {
            const Icon = t.icon
            const active = tab === t.key
            return (
              <button key={t.key} onClick={() => setTab(t.key)} style={{
                padding: '7px 16px', borderRadius: 20, border: '1.5px solid white',
                background: active ? 'white' : 'transparent', color: active ? '#11999e' : 'white',
                cursor: 'pointer', fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6,
                transition: 'all 0.2s',
              }}>
                <Icon size={14} /> {t.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Tab 内容区 */}
      <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
        {tab === 'units' && (
          <Tab0Units
            bigUnits={bigUnits} unitGradeFilter={unitGradeFilter} setUnitGradeFilter={setUnitGradeFilter}
            expandedUnits={expandedUnits} toggleUnit={toggleUnit}
            openNewBigUnit={openNewBigUnit} openAddSection={openAddSection}
            editUnit={editUnit} setEditUnit={setEditUnit} handleUpdateUnit={handleUpdateUnit}
            deleteUnit={deleteUnit}
            newBigUnitOpen={newBigUnitOpen} sectionModal={sectionModal}
            unitForm={unitForm} setUnitForm={setUnitForm}
            unitMsg={unitMsg} handleCreateBigUnit={handleCreateBigUnit} handleSaveSection={handleSaveSection}
            loadUnits={loadUnits}
            gradeColor={gradeColor}
            API={API} headers={headers}
          />
        )}

        {tab === 'questions' && (
          <Tab1Questions
            questions={questions} qLoading={qLoading}
            qGradeFilter={qGradeFilter} setQGradeFilter={setQGradeFilter}
            qBigUnits={qBigUnits} qBigUnitFilter={qBigUnitFilter} setQBigUnitFilter={setQBigUnitFilter}
            qAllUnits={qAllUnits} filterUnit={filterUnit} setFilterUnit={setFilterUnit}
            openNewQuestion={openNewQuestion} openEditQuestion={openEditQuestion} deleteQuestion={deleteQuestion}
            openImportModal={openImportModal}
            difficultyLabel={difficultyLabel}
            importModal={importModal} setImportModal={setImportModal}
            importFileName={importFileName} setImportFileName={setImportFileName}
            importPreview={importPreview} setImportPreview={setImportPreview}
            importing={importing}
            handleFileSelect={handleFileSelect} handleDrop={handleDrop}
            doImport={doImport} importMsg={importMsg}
            qModal={qModal} setQModal={setQModal}
            qForm={qForm} setQForm={setQForm}
            qMsg={qMsg} handleSaveQuestion={handleSaveQuestion} qSaving={qSaving}
            handleApplyFilter={handleApplyFilter}
            selectedQuestions={selectedQuestions}
            handleSelectAll={handleSelectAll} handleSelectOne={handleSelectOne}
            handleBatchDelete={handleBatchDelete}
            API={API} token={token}
          />
        )}

        {tab === 'sessions' && (
          <Tab2Sessions
            sessions={sessions} sLoading={sLoading}
            unitGradeFilter={unitGradeFilter}
            openNewSession={openNewSession} openEditSession={openEditSession} deleteSession={deleteSession}
            handleStartSession={handleStartSession} handleEndSession={handleEndSession}
            sModal={sModal} setSModal={setSModal}
            sForm={sForm} setSForm={setSForm}
            sMsg={sMsg} handleSaveSession={handleSaveSession} sSaving={sSaving}
          />
        )}

        {tab === 'stats' && (
          <Tab3Stats
            API={API} headers={headers}
            statsData={statsData} statsLoading={statsLoading}
            statsFilter={statsFilter} setStatsFilter={setStatsFilter}
            selectedQuiz={selectedQuiz} setSelectedQuiz={setSelectedQuiz}
            autoRefresh={autoRefresh} setAutoRefresh={setAutoRefresh}
            loadStats={loadStats}
            gradeDisplay={gradeDisplay} gradeColor={gradeColor} scoreColor={scoreColor}
          />
        )}
      </div>
    </div>
  )
}
