import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, X } from 'lucide-react'
import {
  getProblemClassOptions,
  updateAdminProblem,
  updateProblemPublication,
} from '../../../api/index.js'
import { GRADES } from '../../../constants/grades.js'

const fieldStyle = {
  width: '100%', boxSizing: 'border-box', border: '1px solid #d9dce5',
  borderRadius: 8, padding: '9px 11px', fontSize: 13,
}

function buildInitialScopes(problem, allowedGrades) {
  const existing = new Map((problem.publication?.scopes || []).map(scope => [scope.grade, scope]))
  return Object.fromEntries(allowedGrades.map(grade => [grade, {
    grade,
    visible: existing.get(grade)?.visible || false,
    all_classes: existing.get(grade)?.all_classes || false,
    classes: existing.get(grade)?.classes || [],
  }]))
}

function Dropdown({ label, summary, disabled, children }) {
  return (
    <div>
      <div style={labelStyle}>{label}</div>
      <details style={{ position: 'relative' }}>
        <summary style={{
          ...dropdownSummaryStyle,
          color: disabled ? '#aaa' : '#3f4654',
          background: disabled ? '#f4f5f7' : 'white',
          cursor: disabled ? 'not-allowed' : 'pointer',
          pointerEvents: disabled ? 'none' : 'auto',
        }}>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{summary}</span>
          <ChevronDown size={16} />
        </summary>
        <div style={dropdownPanelStyle}>{children}</div>
      </details>
    </div>
  )
}

export default function ProblemEditModal({ problem, user, onClose, onSaved }) {
  const allowedGrades = useMemo(
    () => user.is_superuser ? GRADES : [user.managed_grade].filter(Boolean),
    [user.is_superuser, user.managed_grade],
  )
  const [form, setForm] = useState({
    title: problem.title || '',
    difficulty: problem.difficulty || '',
    grade_tag: problem.grade_tag || '',
    description: problem.description || '',
    template_code: problem.template_code || '',
  })
  const [allSchool, setAllSchool] = useState(problem.publication?.all_school || false)
  const [teacherVisible, setTeacherVisible] = useState(
    () => Boolean(problem.publication?.scopes?.[0]?.visible),
  )
  const [scopes, setScopes] = useState(() => buildInitialScopes(problem, allowedGrades))
  const [selectedGrades, setSelectedGrades] = useState(() => {
    if (!user.is_superuser) return allowedGrades
    return allowedGrades.filter(grade => {
      const scope = problem.publication?.scopes?.find(item => item.grade === grade)
      return Boolean(scope?.visible || scope?.all_classes || scope?.classes?.length)
    })
  })
  const [classOptions, setClassOptions] = useState({})
  const [loadingGrades, setLoadingGrades] = useState([])
  const requestedGrades = useRef(new Set())
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const canEditContent = Boolean(problem.can_edit_content)
  const lockedByAllSchool = !user.is_superuser && problem.publication?.all_school
  const missingTeacherScope = !user.is_superuser && !user.managed_grade
  const canEditAudience = !lockedByAllSchool && !missingTeacherScope

  useEffect(() => {
    const requested = requestedGrades.current
    const missing = selectedGrades.filter(grade => !requested.has(grade))
    if (!missing.length) return undefined
    let active = true
    missing.forEach(grade => requested.add(grade))
    setLoadingGrades(current => [...new Set([...current, ...missing])])
    Promise.all(missing.map(async grade => {
      const data = await getProblemClassOptions(grade)
      return [grade, data.classes]
    }))
      .then(entries => {
        if (active) setClassOptions(current => ({ ...current, ...Object.fromEntries(entries) }))
      })
      .catch(requestError => {
        missing.forEach(grade => requested.delete(grade))
        if (active) setError(requestError.message)
      })
      .finally(() => {
        if (active) setLoadingGrades(current => current.filter(grade => !missing.includes(grade)))
      })
    return () => {
      active = false
      // React StrictMode 会在开发环境中执行一次 setup → cleanup → setup。
      // 清理时释放“正在请求”标记，确保第二次 setup 能重新加载班级，
      // 否则 loadingGrades 会一直非空，保存按钮将永久禁用。
      missing.forEach(grade => requested.delete(grade))
    }
  }, [selectedGrades])

  const updateField = (field, value) => setForm(current => ({ ...current, [field]: value }))
  const updateScope = (grade, changes) => {
    setScopes(current => ({ ...current, [grade]: { ...current[grade], ...changes } }))
  }

  const toggleGrade = (grade) => {
    if (!user.is_superuser) return
    setSelectedGrades(current => current.includes(grade)
      ? current.filter(value => value !== grade)
      : [...current, grade])
  }

  const toggleClass = (grade, classNum) => {
    const scope = scopes[grade]
    const classes = scope.classes.includes(classNum)
      ? scope.classes.filter(value => value !== classNum)
      : [...scope.classes, classNum]
    updateScope(grade, { classes, all_classes: false })
  }

  const allSelectedGradesAreComplete = selectedGrades.length > 0
    && selectedGrades.every(grade => scopes[grade]?.all_classes)

  const toggleAllSelectedClasses = (checked) => {
    setScopes(current => {
      const next = { ...current }
      selectedGrades.forEach(grade => {
        next[grade] = { ...next[grade], all_classes: checked, classes: checked ? [] : next[grade].classes }
      })
      return next
    })
  }

  const gradeSummary = selectedGrades.length ? selectedGrades.join('、') : '请选择可见年级'
  const classSummary = allSelectedGradesAreComplete
    ? '已全选所有已选年级'
    : selectedGrades.length
      ? `已选 ${selectedGrades.length} 个年级，点击配置班级`
      : '请先选择年级'

  const validateAudience = () => {
    if (!canEditAudience || allSchool) return ''
    if (!user.is_superuser && !teacherVisible) return ''
    if (!selectedGrades.length) return '请至少选择一个可见年级'
    const incompleteGrade = selectedGrades.find(grade => (
      !scopes[grade]?.all_classes && !scopes[grade]?.classes?.length
    ))
    return incompleteGrade ? `请为${incompleteGrade}选择可见班级，或选择“全年级”` : ''
  }

  const submit = async (event) => {
    event.preventDefault()
    const audienceError = validateAudience()
    if (audienceError) {
      setError(audienceError)
      return
    }

    setSaving(true)
    setError('')
    let updated = problem
    let contentSaved = false
    try {
      const contentChanged = canEditContent && Object.entries(form).some(
        ([field, value]) => value !== (problem[field] || ''),
      )
      if (contentChanged) {
        updated = await updateAdminProblem(problem.problem_id, {
          expected_version: problem.management_version,
          ...form,
        })
        contentSaved = true
      }

      if (canEditAudience) {
        const gradeScopes = allowedGrades.map(grade => ({
          ...scopes[grade],
          visible: selectedGrades.includes(grade),
        }))
        const payload = user.is_superuser ? {
          expected_version: updated.management_version,
          publishing_suspended: updated.publishing_suspended,
          all_school: allSchool,
          scopes: gradeScopes,
        } : {
          expected_version: updated.management_version,
          visible: teacherVisible,
          all_classes: gradeScopes[0]?.all_classes || false,
          classes: gradeScopes[0]?.classes || [],
        }
        const publication = await updateProblemPublication(problem.problem_id, payload)
        updated = {
          ...updated,
          publication,
          publishing_suspended: publication.publishing_suspended,
          management_version: publication.management_version,
        }
      }
      onSaved(updated)
    } catch (requestError) {
      setError(contentSaved
        ? `题目内容已保存，但可见范围保存失败：${requestError.message}`
        : requestError.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={overlayStyle} onClick={onClose} role="presentation">
      <form style={modalStyle} onSubmit={submit} onClick={event => event.stopPropagation()}>
        <div style={titleRowStyle}>
          <div>
            <h2 style={{ margin: 0, fontSize: 19 }}>编辑 AI 题目</h2>
            <div style={{ color: '#8a909d', fontSize: 12, marginTop: 4 }}>题号 {problem.problem_id}（不可修改）</div>
          </div>
          <button type="button" aria-label="关闭" onClick={onClose} style={iconButtonStyle}><X size={20} /></button>
        </div>

        {error && <div role="alert" style={errorStyle}>{error}</div>}
        {!canEditContent && <div style={noticeStyle}>这是共享题目，你可以设置本年级的可见范围，但不能修改题目内容。</div>}

        <section style={sectionStyle}>
          <h3 style={sectionTitleStyle}>题目内容</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
            <div>
              <label style={labelStyle} htmlFor="ai-problem-title">题目名称</label>
              <input id="ai-problem-title" disabled={!canEditContent} value={form.title} onChange={event => updateField('title', event.target.value)} style={fieldStyle} />
            </div>
            <div>
              <label style={labelStyle} htmlFor="ai-problem-difficulty">难度</label>
              <input id="ai-problem-difficulty" disabled={!canEditContent} value={form.difficulty} onChange={event => updateField('difficulty', event.target.value)} style={fieldStyle} placeholder="入门 / 进阶 / 高级" />
            </div>
            <div>
              <label style={labelStyle} htmlFor="ai-problem-grade-tag">适用年级标签</label>
              <select id="ai-problem-grade-tag" disabled={!canEditContent} value={form.grade_tag} onChange={event => updateField('grade_tag', event.target.value)} style={fieldStyle}>
                <option value="">未分类</option>
                {GRADES.map(grade => <option key={grade} value={grade}>{grade}</option>)}
              </select>
            </div>
          </div>

          <label style={labelStyle} htmlFor="ai-problem-description">题目描述</label>
          <textarea id="ai-problem-description" disabled={!canEditContent} value={form.description} onChange={event => updateField('description', event.target.value)} style={{ ...fieldStyle, minHeight: 120, resize: 'vertical' }} />

          <label style={labelStyle} htmlFor="ai-problem-template">初始代码</label>
          <textarea id="ai-problem-template" disabled={!canEditContent} value={form.template_code} onChange={event => updateField('template_code', event.target.value)} style={{ ...fieldStyle, minHeight: 100, resize: 'vertical', fontFamily: 'monospace' }} />
        </section>

        <section style={{ ...sectionStyle, marginTop: 16 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
            <div>
              <h3 style={sectionTitleStyle}>可见范围</h3>
              <p style={sectionHintStyle}>先选年级，再为已选年级配置可见班级。</p>
            </div>
            {user.is_superuser && (
              <label style={allSchoolStyle}>
                <input type="checkbox" checked={allSchool} onChange={event => setAllSchool(event.target.checked)} />
                <span><strong>全校可见</strong><small style={smallStyle}>自动包含以后新增班级</small></span>
              </label>
            )}
          </div>

          {lockedByAllSchool && <div style={noticeStyle}>该题目由 Alex 设为全校可见，普通教师不能覆盖。</div>}
          {missingTeacherScope && <div style={noticeStyle}>当前账号尚未配置管理年级，请先联系 Alex。</div>}
          {!user.is_superuser && canEditAudience && (
            <label style={{ ...allSchoolStyle, marginTop: 10, width: 'fit-content' }}>
              <input type="checkbox" checked={teacherVisible} onChange={event => setTeacherVisible(event.target.checked)} />
              <span><strong>对我管理的年级可见</strong><small style={smallStyle}>关闭后保留上次班级选择</small></span>
            </label>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 12, marginTop: 12 }}>
            <Dropdown label="1. 可见年级（可多选）" summary={gradeSummary} disabled={!canEditAudience || allSchool}>
              {allowedGrades.map(grade => (
                <label key={grade} style={optionStyle}>
                  <input type="checkbox" checked={selectedGrades.includes(grade)} disabled={!user.is_superuser} onChange={() => toggleGrade(grade)} />
                  {grade}
                  {!user.is_superuser && <span style={managedTagStyle}>我的管理年级</span>}
                </label>
              ))}
            </Dropdown>

            <Dropdown label="2. 可见班级" summary={classSummary} disabled={!canEditAudience || allSchool || !selectedGrades.length}>
              <label style={{ ...optionStyle, borderBottom: '1px solid #eceef3', paddingBottom: 10 }}>
                <input type="checkbox" checked={allSelectedGradesAreComplete} onChange={event => toggleAllSelectedClasses(event.target.checked)} />
                <strong style={{ color: '#5868d8' }}>全选已选年级的所有班级</strong>
              </label>
              {selectedGrades.map(grade => {
                const scope = scopes[grade]
                const options = classOptions[grade] || []
                return (
                  <div key={grade} style={gradeGroupStyle}>
                    <div style={gradeGroupTitleStyle}>{grade}</div>
                    <label style={optionStyle}>
                      <input type="checkbox" checked={scope.all_classes} onChange={event => updateScope(grade, { all_classes: event.target.checked, classes: event.target.checked ? [] : scope.classes })} />
                      <strong>全年级（全选）</strong>
                    </label>
                    {loadingGrades.includes(grade) ? (
                      <div style={emptyStyle}>正在加载班级…</div>
                    ) : options.length ? options.map(classNum => (
                      <label key={classNum} style={optionStyle}>
                        <input type="checkbox" checked={!scope.all_classes && scope.classes.includes(classNum)} disabled={scope.all_classes} onChange={() => toggleClass(grade, classNum)} />
                        {classNum}班
                      </label>
                    )) : <div style={emptyStyle}>暂无已注册班级，可选“全年级”</div>}
                  </div>
                )
              })}
            </Dropdown>
          </div>
          <p style={{ ...sectionHintStyle, marginTop: 10 }}>选择“全年级”后，以后新增的该年级班级也会自动可见。</p>
        </section>

        <div style={actionsStyle}>
          <button type="button" onClick={onClose} style={secondaryButtonStyle}>取消</button>
          <button type="submit" disabled={saving} style={primaryButtonStyle}>{saving ? '保存中…' : '保存修改'}</button>
        </div>
      </form>
    </div>
  )
}

const overlayStyle = { position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(25, 29, 43, .52)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }
const modalStyle = { boxSizing: 'border-box', background: '#fbfbfd', width: 'min(820px, 100%)', maxHeight: '92vh', overflowY: 'auto', borderRadius: 18, padding: 'clamp(16px, 4vw, 24px)', boxShadow: '0 24px 70px rgba(24, 31, 67, .28)' }
const titleRowStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 18 }
const iconButtonStyle = { border: 'none', background: 'transparent', color: '#747b89', cursor: 'pointer', padding: 4 }
const labelStyle = { display: 'block', color: '#555d6b', fontSize: 13, fontWeight: 700, margin: '12px 0 6px' }
const sectionStyle = { background: 'white', border: '1px solid #e5e7ef', borderRadius: 12, padding: 16 }
const sectionTitleStyle = { margin: 0, fontSize: 15, color: '#303744' }
const sectionHintStyle = { margin: '4px 0 0', color: '#8a909d', fontSize: 12, lineHeight: 1.6 }
const dropdownSummaryStyle = { listStyle: 'none', border: '1px solid #d9dce5', borderRadius: 9, padding: '10px 12px', fontSize: 13, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }
const dropdownPanelStyle = { position: 'absolute', left: 0, right: 0, zIndex: 4, marginTop: 5, background: 'white', border: '1px solid #d9dce5', borderRadius: 10, boxShadow: '0 12px 34px rgba(25, 33, 66, .16)', padding: 10, maxHeight: 300, overflowY: 'auto' }
const optionStyle = { display: 'flex', alignItems: 'center', gap: 8, padding: '7px 5px', fontSize: 13, cursor: 'pointer' }
const gradeGroupStyle = { padding: '8px 4px', borderBottom: '1px solid #f0f1f5' }
const gradeGroupTitleStyle = { color: '#667085', fontSize: 12, fontWeight: 800, margin: '2px 0 4px' }
const emptyStyle = { color: '#999fac', fontSize: 12, padding: '6px 5px' }
const allSchoolStyle = { minWidth: 220, border: '1px solid #cfd5ff', background: '#f4f5ff', borderRadius: 10, padding: '9px 11px', display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 13, cursor: 'pointer' }
const smallStyle = { display: 'block', color: '#80879a', fontWeight: 400, fontSize: 11, marginTop: 2 }
const managedTagStyle = { marginLeft: 'auto', color: '#6775d9', background: '#eef0ff', borderRadius: 10, padding: '2px 7px', fontSize: 10 }
const noticeStyle = { background: '#fff8df', color: '#745600', borderRadius: 8, padding: '9px 12px', fontSize: 12, marginTop: 10 }
const errorStyle = { background: '#fff0f0', color: '#a61b1b', borderRadius: 8, padding: '9px 12px', fontSize: 12, marginBottom: 12 }
const actionsStyle = { display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }
const secondaryButtonStyle = { border: '1px solid #d9dce5', background: 'white', borderRadius: 8, padding: '9px 18px', cursor: 'pointer', fontWeight: 700 }
const primaryButtonStyle = { border: 'none', background: '#667eea', color: 'white', borderRadius: 8, padding: '9px 22px', cursor: 'pointer', fontWeight: 700 }
