import { useCallback, useEffect, useMemo, useState } from 'react'
import { Archive, BookOpen, Edit2, Eye, EyeOff, RefreshCw, RotateCcw, Tag } from 'lucide-react'

import {
  archiveAdminProblem, getAdminAIUnits, getAdminProblems, restoreAdminProblem,
  syncAdminProblems, updateProblemPublication,
} from '../../../api/index.js'
import { GRADES } from '../../../constants/grades.js'
import ProblemEditModal from '../components/ProblemEditModal.jsx'

const panel = { background: '#fff', borderRadius: 14, boxShadow: '0 2px 8px rgba(0,0,0,.06)' }
const DIFFICULTY_COLORS = { '简单': '#18794e', '中等': '#a15c00', '困难': '#b3313d', '入门': '#18794e', '进阶': '#a15c00', '高级': '#b3313d' }
const GRADE_TAG_COLORS = {
  '七年级': ['#eef1ff', '#5369d8'], '八年级': ['#e8f8ef', '#18794e'],
  '九年级': ['#fff4dc', '#a15c00'], '高一': ['#f2eaff', '#7048b8'],
  '高二': ['#e6f6fb', '#15728a'], '高三': ['#ffeaec', '#b3313d'],
}
const filterControlStyle = {
  minHeight: 36, padding: '7px 34px 7px 11px', border: '1px solid #d9deea',
  borderRadius: 8, background: '#fff', color: '#4d5565', fontSize: 12,
  fontFamily: 'inherit', cursor: 'pointer', outlineColor: '#667eea',
}
const iconButtonStyle = (color, background) => ({
  width: 32, height: 32, padding: 0, border: 0, borderRadius: 8,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  color, background, cursor: 'pointer', flexShrink: 0,
  transition: 'transform .15s ease, box-shadow .15s ease, background .15s ease',
})

export default function AIProgrammingProblemsTab({ currentUser }) {
  const [problems, setProblems] = useState([])
  const [units, setUnits] = useState([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [includeArchived, setIncludeArchived] = useState(false)
  const [grade, setGrade] = useState('all')
  const [unit, setUnit] = useState('all')
  const [usable, setUsable] = useState('all')
  const [editing, setEditing] = useState(null)
  const [notice, setNotice] = useState({ type: '', text: '' })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [problemData, unitData] = await Promise.all([
        getAdminProblems({ includeArchived }), getAdminAIUnits(),
      ])
      setProblems(problemData); setUnits(unitData)
    } catch (error) { setNotice({ type: 'error', text: error.message }) }
    finally { setLoading(false) }
  }, [includeArchived])
  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => problems.filter(problem => {
    const gradeMatch = grade === 'all' || (grade === 'unclassified' ? !problem.grade_tag : problem.grade_tag === grade)
    const unitMatch = unit === 'all' || (unit === 'unclassified' ? !problem.unit : String(problem.unit) === unit)
    const usableMatch = usable === 'all' || (usable === 'usable' ? problem.quiz_usable : !problem.quiz_usable)
    return gradeMatch && unitMatch && usableMatch
  }), [grade, problems, unit, usable])

  const updateLocal = next => setProblems(current => current.map(problem => problem.problem_id === next.problem_id ? { ...problem, ...next } : problem))
  const toggleVisible = async problem => {
    const scope = problem.publication?.scopes?.[0]
    const target = !scope?.visible
    const values = currentUser.is_superuser ? {
      expected_version: problem.management_version,
      publishing_suspended: !problem.publishing_suspended,
      all_school: problem.publication?.all_school,
      scopes: problem.publication?.scopes || [],
    } : {
      expected_version: problem.management_version,
      visible: target,
      all_classes: Boolean(scope?.all_classes) || (target && !(scope?.classes || []).length),
      classes: scope?.classes || [],
    }
    try {
      const publication = await updateProblemPublication(problem.problem_id, values)
      updateLocal({ ...problem, publication, publishing_suspended: publication.publishing_suspended, management_version: publication.management_version })
      setNotice({ type: 'success', text: '题目可见状态已更新' })
    } catch (error) { setNotice({ type: 'error', text: error.message }) }
  }
  const toggleArchive = async problem => {
    if (!problem.archived_at && !window.confirm(`确定归档题目「${problem.title || problem.problem_id}」吗？历史成绩会保留。`)) return
    try {
      if (problem.archived_at) await restoreAdminProblem(problem.problem_id, problem.management_version)
      else await archiveAdminProblem(problem.problem_id, problem.management_version)
      setNotice({ type: 'success', text: problem.archived_at ? '题目已恢复，当前仍暂停发布' : '题目已归档，历史成绩已保留' })
      await load()
    } catch (error) { setNotice({ type: 'error', text: error.message }) }
  }
  const sync = async () => {
    setSyncing(true)
    try {
      const result = await syncAdminProblems()
      setNotice({ type: result.failed?.length ? 'error' : 'success', text: `同步完成：新增 ${result.created.length}，更新 ${result.updated.length}，跳过 ${result.skipped.length}${result.failed?.length ? `，失败 ${result.failed.length}` : ''}` })
      await load()
    } catch (error) { setNotice({ type: 'error', text: error.message }) }
    finally { setSyncing(false) }
  }

  return <section aria-labelledby="programming-bank-title" style={{ display: 'grid', gap: 16 }}>
    <div style={{ ...panel, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
      <BookOpen size={18} color="#667eea" /><h2 id="programming-bank-title" style={{ margin: 0, fontSize: 16 }}>AI 编程题库</h2><span style={{ color: '#7a8190', fontSize: 12 }}>共 {problems.length} 题</span>
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 9, alignItems: 'center', flexWrap: 'wrap' }}>{currentUser.is_superuser && <label style={{ fontSize: 12, color: '#5d6472', display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}><input type="checkbox" checked={includeArchived} onChange={event => setIncludeArchived(event.target.checked)} /> 显示已归档</label>}<button type="button" data-testid="icon-refresh" onClick={load} aria-label="刷新编程题库" title="刷新题库" style={{ ...iconButtonStyle('#5369d8', '#eef1ff'), border: '1px solid #dde2fb' }}><RefreshCw size={15} /></button><button type="button" onClick={sync} disabled={syncing} style={{ padding: '9px 15px', border: 0, borderRadius: 8, background: syncing ? '#aeb5c4' : '#45b7d1', color: '#fff', fontWeight: 700, fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 6, cursor: syncing ? 'not-allowed' : 'pointer' }}><RefreshCw size={14} className={syncing ? 'spin' : ''} />{syncing ? '同步中…' : '从磁盘同步'}</button></div>
    </div>
    {notice.text && <div role="status" style={{ padding: 10, borderRadius: 8, background: notice.type === 'error' ? '#ffeaec' : '#e6f7ed', color: notice.type === 'error' ? '#a61b29' : '#18794e' }}>{notice.text}</div>}
    <div style={{ ...panel, padding: '13px 16px', display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}><Tag size={16} color="#667eea" /><span style={{ color: '#444b58', fontSize: 12, fontWeight: 700, marginRight: 2 }}>筛选</span><select aria-label="适用年级筛选" value={grade} onChange={event => setGrade(event.target.value)} style={filterControlStyle}><option value="all">全部年级</option>{GRADES.map(item => <option key={item}>{item}</option>)}<option value="unclassified">未分类</option></select><select aria-label="所属 AI 小节筛选" value={unit} onChange={event => setUnit(event.target.value)} style={{ ...filterControlStyle, minWidth: 150 }}><option value="all">全部小节</option><option value="unclassified">未归类到小节</option>{units.map(root => <optgroup key={root.id} label={`${root.grade} · ${root.display_name}`}>{(root.sections || []).map(section => <option key={section.id} value={section.id}>{section.display_name}</option>)}</optgroup>)}</select><select aria-label="可组卷状态筛选" value={usable} onChange={event => setUsable(event.target.value)} style={{ ...filterControlStyle, minWidth: 140 }}><option value="all">全部组卷状态</option><option value="usable">可组卷</option><option value="unusable">暂不可组卷</option></select><span style={{ marginLeft: 'auto', color: '#7a8190', fontSize: 12, whiteSpace: 'nowrap' }}>显示 {filtered.length} / {problems.length} 题</span></div>
    <div style={{ ...panel, overflow: 'hidden' }}>{loading ? <div style={{ padding: 50, textAlign: 'center', color: '#7a8190' }}>正在加载编程题…</div> : filtered.length === 0 ? <div style={{ padding: 50, textAlign: 'center', color: '#7a8190' }}>当前筛选条件下暂无编程题。</div> : <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(300px,1fr))', gap: 14, padding: 18 }}>{filtered.map(problem => {
      const scope = problem.publication?.scopes?.[0]
      const visible = currentUser.is_superuser ? !problem.publishing_suspended && (problem.publication?.all_school || problem.publication?.scopes?.some(item => item.visible)) : !problem.publishing_suspended && (problem.publication?.all_school || scope?.visible)
      const canToggle = currentUser.is_superuser || (currentUser.managed_grade && !problem.publication?.all_school)
      const [gradeBackground, gradeColor] = GRADE_TAG_COLORS[problem.grade_tag] || ['#f1f2f5', '#6d7480']
      return <article key={problem.problem_id} style={{ border: '2px solid #e9ecf2', borderRadius: 12, padding: 14, minHeight: 132, background: problem.archived_at ? '#f7f7f8' : '#fff', opacity: problem.archived_at ? .7 : 1, transition: 'border-color .18s ease, background .18s ease, box-shadow .18s ease' }} onMouseEnter={event => { event.currentTarget.style.borderColor = '#b8c1f3'; event.currentTarget.style.background = problem.archived_at ? '#f7f7f8' : '#fafaff'; event.currentTarget.style.boxShadow = '0 5px 16px rgba(79,93,170,.08)' }} onMouseLeave={event => { event.currentTarget.style.borderColor = '#e9ecf2'; event.currentTarget.style.background = problem.archived_at ? '#f7f7f8' : '#fff'; event.currentTarget.style.boxShadow = 'none' }}>
        <div style={{ display: 'flex', gap: 10 }}><div style={{ minWidth: 0, flex: 1 }}><strong style={{ display: 'block', color: '#30343b', fontSize: 14, lineHeight: 1.4 }}>{problem.title || problem.problem_id}</strong><div style={{ marginTop: 4, color: '#8a909d', fontSize: 11 }}>编号：{problem.problem_id} · 测试点：{problem.test_count}</div></div><div style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>{!problem.archived_at && <button type="button" title="编辑题目与归类" aria-label={`编辑${problem.title || problem.problem_id}`} onClick={() => setEditing(problem)} style={iconButtonStyle('#5369d8', '#eef1ff')}><Edit2 size={15} /></button>}{!problem.archived_at && canToggle && <button type="button" title={visible ? '设为不可见' : '设为可见'} aria-label={`${visible ? '隐藏' : '显示'}${problem.title || problem.problem_id}`} onClick={() => toggleVisible(problem)} style={iconButtonStyle(visible ? '#b36b00' : '#18794e', visible ? '#fff4d8' : '#e6f7ed')}>{visible ? <EyeOff size={15} /> : <Eye size={15} />}</button>}{problem.can_archive && <button type="button" title={problem.archived_at ? '恢复题目' : '归档题目（保留成绩）'} aria-label={`${problem.archived_at ? '恢复' : '归档'}${problem.title || problem.problem_id}`} onClick={() => toggleArchive(problem)} style={iconButtonStyle(problem.archived_at ? '#18794e' : '#b3313d', problem.archived_at ? '#e6f7ed' : '#ffeaec')}>{problem.archived_at ? <RotateCcw size={15} /> : <Archive size={15} />}</button>}</div></div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 12, fontSize: 11 }}><span style={{ background: gradeBackground, color: gradeColor, borderRadius: 8, padding: '3px 7px', fontWeight: 700 }}>{problem.grade_tag || '未分类'}</span><span style={{ background: problem.unit ? '#eaf4ff' : '#fff4dc', color: problem.unit ? '#365f8d' : '#8a5a00', borderRadius: 8, padding: '3px 7px' }}>{problem.unit ? `${problem.big_unit_name} / ${problem.unit_name}` : '未归类小节'}</span><span title={(problem.quiz_unusable_reasons || []).map(reason => reason.label).join('；')} style={{ background: problem.quiz_usable ? '#e6f7ed' : '#fff4dc', color: problem.quiz_usable ? '#18794e' : '#a15c00', borderRadius: 8, padding: '3px 7px', fontWeight: 700 }}>{problem.quiz_usable ? '可组卷' : '暂不可组卷'}</span><span style={{ background: visible ? '#e6f7ed' : '#f1f2f5', color: visible ? '#18794e' : '#6d7480', borderRadius: 8, padding: '3px 7px', fontWeight: 700 }}>{problem.archived_at ? '已归档' : visible ? '可见' : '不可见'}</span></div>
        <div style={{ marginTop: 10, fontSize: 12, color: DIFFICULTY_COLORS[problem.difficulty] || '#6d7480', fontWeight: 700 }}>{problem.difficulty || '未设置难度'} · {problem.publication_label}</div>
      </article>
    })}</div>}</div>
    <div style={{ ...panel, padding: 18, color: '#596172', fontSize: 13, lineHeight: 1.7 }}><strong>新增编程题：</strong>将题目文件夹放入后端 <code>backend/problems/</code> 后点击“从磁盘同步”。同步不会覆盖教师设置的年级和 AI 小节，新题默认不发布。</div>
    {editing && <ProblemEditModal key={`${editing.problem_id}-${editing.management_version}`} problem={editing} user={currentUser} units={units} onClose={() => setEditing(null)} onSaved={updated => { updateLocal(updated); setEditing(null); setNotice({ type: 'success', text: `题目「${updated.title || updated.problem_id}」已保存` }) }} />}
  </section>
}
