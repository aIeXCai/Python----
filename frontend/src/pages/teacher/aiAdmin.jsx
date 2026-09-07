import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Archive, ArrowLeft, Bot, BookOpen, BarChart3, RefreshCw, Eye,
  Upload, Edit2, EyeOff, RotateCcw, Tag
} from 'lucide-react'
import { API_BASE_URL } from '../../api/config.js'
import {
  archiveAdminProblem,
  getAdminProblems,
  getCurrentUser,
  restoreAdminProblem,
  syncAdminProblems,
  updateProblemPublication,
} from '../../api/index.js'
import { GRADES } from '../../constants/grades.js'
import ProblemEditModal from './components/ProblemEditModal.jsx'

const API = API_BASE_URL
const DIFFICULTY_COLORS = { '简单': '#38ef7d', '中等': '#f59e0b', '困难': '#ef4444', '入门': '#38ef7d', '进阶': '#f59e0b', '高级': '#ef4444' }
const GRADE_TAG_COLORS = {
  '七年级': ['#eef1ff', '#5369d8'],
  '八年级': ['#e8f8ef', '#18794e'],
  '九年级': ['#fff4dc', '#a15c00'],
  '高一': ['#f2eaff', '#7048b8'],
  '高二': ['#e6f6fb', '#15728a'],
  '高三': ['#ffeaec', '#b3313d'],
}

const iconButtonStyle = (color, background) => ({
  width: 30,
  height: 30,
  padding: 0,
  border: 'none',
  borderRadius: 8,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  color,
  background,
  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
})

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
  const [currentUser] = useState(() => getCurrentUser())
  const token = localStorage.getItem('token')
  const headers = useMemo(() => ({
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json',
  }), [token])

  // ─── Tab0: 题库管理 ─────────────────────────────────────────────────────────
  const [problems, setProblems] = useState([])
  const [pLoading, setPLoading] = useState(true)
  const [pSyncing, setPSyncing] = useState(false)
  const [pMsg, setPMsg] = useState({ type: '', text: '' })
  const [editProblem, setEditProblem] = useState(null)
  const [includeArchived, setIncludeArchived] = useState(false)
  const [gradeTagFilter, setGradeTagFilter] = useState('all')

  const filteredProblems = useMemo(() => {
    if (gradeTagFilter === 'all') return problems
    if (gradeTagFilter === 'unclassified') return problems.filter(problem => !problem.grade_tag)
    return problems.filter(problem => problem.grade_tag === gradeTagFilter)
  }, [gradeTagFilter, problems])

  const gradeTagCounts = useMemo(() => {
    const counts = Object.fromEntries(GRADES.map(grade => [grade, 0]))
    counts.unclassified = 0
    problems.forEach(problem => {
      if (problem.grade_tag && Object.hasOwn(counts, problem.grade_tag)) counts[problem.grade_tag] += 1
      else counts.unclassified += 1
    })
    return counts
  }, [problems])

  const loadProblems = useCallback(async () => {
    setPLoading(true)
    try {
      setProblems(await getAdminProblems({ includeArchived }))
    } catch (e) { console.error(e) }
    setPLoading(false)
  }, [includeArchived])

  useEffect(() => { loadProblems() }, [loadProblems])

  const syncFromDisk = async () => {
    setPSyncing(true)
    try {
      const data = await syncAdminProblems()
      const failedText = data.failed.length
        ? `；失败：${data.failed.map(item => `${item.problem_id}（${item.reason}）`).join('、')}`
        : ''
      setPMsg({
        type: data.failed.length ? 'error' : 'success',
        text: `同步完成：新增 ${data.created.length} 题，更新 ${data.updated.length} 题，跳过 ${data.skipped.length} 题${failedText}。新题默认不发布。`,
      })
      loadProblems()
    } catch (e) { setPMsg({ type: 'error', text: '同步失败：' + e.message }) }
    setPSyncing(false)
    setTimeout(() => setPMsg({ type: '', text: '' }), 5000)
  }

  const replaceProblem = (updated) => {
    setProblems(current => current.map(problem => (
      problem.problem_id === updated.problem_id ? { ...problem, ...updated } : problem
    )))
  }

  const saveAndClose = (updated, close) => {
    replaceProblem(updated)
    close(null)
    setPMsg({ type: 'success', text: `题目「${updated.title || updated.problem_id}」已保存` })
  }

  const toggleProblemVisibility = async (problem) => {
    const publication = problem.publication || { scopes: [] }
    const teacherScope = publication.scopes?.[0]
    const teacherTargetVisible = !teacherScope?.visible
    const rememberedClasses = teacherScope?.classes || []
    const values = currentUser.is_superuser ? {
      expected_version: problem.management_version,
      publishing_suspended: !problem.publishing_suspended,
      all_school: publication.all_school,
      scopes: publication.scopes || [],
    } : {
      expected_version: problem.management_version,
      visible: teacherTargetVisible,
      all_classes: Boolean(teacherScope?.all_classes) || (teacherTargetVisible && rememberedClasses.length === 0),
      classes: rememberedClasses,
    }
    try {
      const nextPublication = await updateProblemPublication(problem.problem_id, values)
      replaceProblem({
        ...problem,
        publication: nextPublication,
        publishing_suspended: nextPublication.publishing_suspended,
        management_version: nextPublication.management_version,
      })
      setPMsg({ type: 'success', text: '题目可见状态已更新' })
    } catch (error) {
      setPMsg({ type: 'error', text: error.message })
    }
  }

  const archiveProblem = async (problem) => {
    if (!window.confirm(`确定归档题目「${problem.title || problem.problem_id}」吗？学生将看不到它，但历史成绩会保留。`)) return
    try {
      await archiveAdminProblem(problem.problem_id, problem.management_version)
      setPMsg({ type: 'success', text: `题目「${problem.title || problem.problem_id}」已归档，历史成绩已保留` })
      loadProblems()
    } catch (error) {
      setPMsg({ type: 'error', text: error.message })
    }
  }

  const restoreProblem = async (problem) => {
    try {
      await restoreAdminProblem(problem.problem_id, problem.management_version)
      setPMsg({ type: 'success', text: `题目「${problem.title || problem.problem_id}」已恢复，当前仍为暂停发布` })
      loadProblems()
    } catch (error) {
      setPMsg({ type: 'error', text: error.message })
    }
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

  const loadScores = useCallback(async () => {
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
  }, [headers, sFilters])

  useEffect(() => { loadScores() }, [loadScores])
  useEffect(() => { const id = setInterval(loadScores, 5000); return () => clearInterval(id) }, [loadScores])

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
                {currentUser.is_superuser && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#666', cursor: 'pointer' }}>
                    <input type="checkbox" checked={includeArchived} onChange={e => setIncludeArchived(e.target.checked)} />
                    显示已归档
                  </label>
                )}
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

            <div style={{
              background: 'white', borderRadius: 14, padding: '14px 18px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.06)', display: 'flex',
              alignItems: 'center', gap: 8, flexWrap: 'wrap',
            }}>
              <Tag size={16} style={{ color: '#667eea' }} />
              <span style={{ fontSize: 13, fontWeight: 700, color: '#444', marginRight: 4 }}>适用年级</span>
              {[
                { value: 'all', label: '全部', count: problems.length },
                ...GRADES.map(grade => ({ value: grade, label: grade, count: gradeTagCounts[grade] })),
                { value: 'unclassified', label: '未分类', count: gradeTagCounts.unclassified },
              ].map(option => {
                const active = gradeTagFilter === option.value
                return (
                  <button
                    type="button"
                    key={option.value}
                    aria-pressed={active}
                    onClick={() => setGradeTagFilter(option.value)}
                    style={{
                      border: `1px solid ${active ? '#667eea' : '#e2e5ed'}`,
                      background: active ? '#667eea' : '#fff',
                      color: active ? '#fff' : '#5d6472',
                      borderRadius: 18, padding: '6px 11px', fontSize: 12,
                      fontWeight: active ? 700 : 500, cursor: 'pointer',
                    }}
                  >{option.label} <span style={{ opacity: active ? 0.82 : 0.58 }}>{option.count}</span></button>
                )
              })}
              {gradeTagFilter !== 'all' && (
                <span style={{ marginLeft: 'auto', color: '#8a909d', fontSize: 12 }}>
                  已筛选 {filteredProblems.length} / {problems.length} 题
                </span>
              )}
            </div>

            {/* 题目卡片网格 */}
            <div style={{ background: 'white', borderRadius: 14, overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
              {pLoading ? (
                <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>加载中...</div>
              ) : problems.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>
                  <BookOpen size={48} style={{ marginBottom: 16, opacity: 0.3 }} />
                  <p>暂无题目，点击「从磁盘同步」导入</p>
                </div>
              ) : filteredProblems.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 52, color: '#888' }}>
                  <Tag size={38} style={{ marginBottom: 12, opacity: 0.3 }} />
                  <p style={{ margin: 0 }}>当前年级标签下暂无题目</p>
                </div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14, padding: 20 }}>
                  {filteredProblems.map(p => {
                    const teacherScope = p.publication?.scopes?.[0]
                    const visible = currentUser.is_superuser
                      ? !p.publishing_suspended && (p.publication?.all_school || p.publication?.scopes?.some(scope => scope.visible))
                      : !p.publishing_suspended && (p.publication?.all_school || teacherScope?.visible)
                    const canToggleVisibility = currentUser.is_superuser
                      || (currentUser.managed_grade && !p.publication?.all_school)
                    const [gradeTagBackground, gradeTagColor] = GRADE_TAG_COLORS[p.grade_tag] || ['#f1f2f5', '#6d7480']
                    return (
                    <div key={p.problem_id} style={{
                      position: 'relative', border: '2px solid #e9ecef', borderRadius: 12, padding: 14, minHeight: 112,
                      transition: 'all 0.2s', background: p.archived_at ? '#f7f7f7' : 'white', opacity: p.archived_at ? 0.78 : 1,
                    }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = '#667eea'; e.currentTarget.style.background = '#f8f9ff' }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = '#e9ecef'; e.currentTarget.style.background = p.archived_at ? '#f7f7f7' : 'white' }}>
                      <div style={{ paddingRight: p.archived_at ? 40 : 112 }}>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: '#333', marginBottom: 3 }}>
                            {p.title || `题目${p.problem_id}`}
                          </div>
                          <div style={{ fontSize: 11, color: '#888' }}>编号：{p.problem_id} · 测试点：{p.test_count}</div>
                          <div style={{ marginTop: 7, display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                            <span style={{ padding: '2px 7px', borderRadius: 8, fontSize: 10, fontWeight: 700, background: gradeTagBackground, color: gradeTagColor }}>{p.grade_tag || '未分类'}</span>
                            <span style={{
                              padding: '2px 7px', borderRadius: 8, fontSize: 10, fontWeight: 700,
                              background: visible ? '#e6f7ed' : '#f1f2f5', color: visible ? '#18794e' : '#6d7480',
                            }}>{p.archived_at ? '已归档' : (visible ? '可见' : '不可见')}</span>
                            <span title={p.publication_label} style={{
                              padding: '2px 7px', borderRadius: 8, fontSize: 10, color: '#5b67a8',
                              background: '#eef0ff', maxWidth: 170, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                            }}>{p.publication_label}</span>
                          </div>
                        </div>
                        <span style={{
                          display: 'inline-block', marginTop: 9,
                          padding: '3px 8px', borderRadius: 8, fontSize: 11, fontWeight: 800, whiteSpace: 'nowrap',
                          background: `${DIFFICULTY_COLORS[p.difficulty] || '#888'}18`,
                          color: DIFFICULTY_COLORS[p.difficulty] || '#888',
                        }}>{p.difficulty || '—'}</span>
                      </div>
                      <div style={{ position: 'absolute', top: 10, right: 10, display: 'flex', gap: 5 }}>
                        {!p.archived_at && <button
                          type="button"
                          aria-label={`编辑${p.title || p.problem_id}`}
                          title="编辑题目与可见范围"
                          onClick={() => setEditProblem(p)}
                          style={iconButtonStyle('#5369d8', '#eef1ff')}
                        ><Edit2 size={15} /></button>}
                        {!p.archived_at && canToggleVisibility && <button
                          type="button"
                          aria-label={`${visible ? '隐藏' : '显示'}${p.title || p.problem_id}`}
                          title={visible ? '设为不可见' : '设为可见'}
                          onClick={() => toggleProblemVisibility(p)}
                          style={iconButtonStyle(visible ? '#c27700' : '#18794e', visible ? '#fff4d8' : '#e6f7ed')}
                        >{visible ? <EyeOff size={15} /> : <Eye size={15} />}</button>}
                        {p.can_archive && !p.archived_at && <button
                          type="button"
                          aria-label={`归档${p.title || p.problem_id}`}
                          title="归档题目（保留历史成绩）"
                          onClick={() => archiveProblem(p)}
                          style={iconButtonStyle('#c23843', '#ffeaec')}
                        ><Archive size={15} /></button>}
                        {p.can_archive && p.archived_at && <button
                          type="button"
                          aria-label={`恢复${p.title || p.problem_id}`}
                          title="恢复题目"
                          onClick={() => restoreProblem(p)}
                          style={iconButtonStyle('#18794e', '#e6f7ed')}
                        ><RotateCcw size={15} /></button>}
                      </div>
                    </div>
                  )})}
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

      {editProblem && (
        <ProblemEditModal
          key={`${editProblem.problem_id}-${editProblem.management_version}`}
          problem={editProblem}
          user={currentUser}
          onClose={() => setEditProblem(null)}
          onSaved={updated => saveAndClose(updated, setEditProblem)}
        />
      )}
    </div>
  )
}
