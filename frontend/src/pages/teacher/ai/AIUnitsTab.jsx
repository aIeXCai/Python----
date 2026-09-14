import { useCallback, useEffect, useMemo, useState } from 'react'
import { Archive, ChevronDown, ChevronRight, Edit2, Layers3, Plus, RotateCcw, Trash2, X } from 'lucide-react'

import {
  archiveAIUnit, createAIUnit, deleteAIUnit, getAIUnits, restoreAIUnit, updateAIUnit,
} from '../../../api/aiQuiz.js'
import { GRADES } from '../../../constants/grades.js'

const panel = {
  background: '#fff', borderRadius: 14, boxShadow: '0 2px 8px rgba(0,0,0,.06)',
}

function Notice({ value }) {
  if (!value.text) return null
  return <div role="status" style={{
    padding: '10px 14px', borderRadius: 9,
    background: value.type === 'error' ? '#ffeaec' : '#e6f7ed',
    color: value.type === 'error' ? '#a61b29' : '#18794e', fontSize: 13,
  }}>{value.text}</div>
}

function UnitDialog({ value, roots, defaultGrade, allowedGrades, onClose, onSave }) {
  const isEdit = Boolean(value?.id)
  const [form, setForm] = useState({
    grade: value?.grade || defaultGrade,
    parent: value?.parent || null,
    display_name: value?.display_name || '',
    order: value?.order || 0,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const submit = async event => {
    event.preventDefault()
    setSaving(true)
    setError('')
    try {
      await onSave({
        ...form,
        name: value?.name || form.display_name.trim(),
        parent: form.parent ? Number(form.parent) : null,
        order: Number(form.order) || 0,
      })
      onClose()
    } catch (reason) {
      setError(reason.message)
    } finally {
      setSaving(false)
    }
  }
  return <div role="presentation" onMouseDown={event => event.target === event.currentTarget && onClose()} style={{
    position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(28,35,55,.52)',
    display: 'grid', placeItems: 'center', padding: 20,
  }}>
    <div role="dialog" aria-modal="true" aria-labelledby="unit-dialog-title" style={{
      width: 'min(480px, 100%)', background: '#fff', borderRadius: 16,
      boxShadow: '0 24px 70px rgba(22,30,55,.28)', padding: 24,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 18 }}>
        <h2 id="unit-dialog-title" style={{ margin: 0, fontSize: 18 }}>{isEdit ? '编辑 AI 单元' : '新建 AI 单元'}</h2>
        <button aria-label="关闭单元弹窗" onClick={onClose} style={{ marginLeft: 'auto', border: 0, background: 'transparent', cursor: 'pointer' }}><X size={20} /></button>
      </div>
      {error && <div role="alert" style={{ color: '#a61b29', background: '#ffeaec', padding: 10, borderRadius: 8, marginBottom: 12 }}>{error}</div>}
      <form onSubmit={submit} style={{ display: 'grid', gap: 14 }}>
        {!isEdit && <>
          <label style={{ display: 'grid', gap: 6, fontSize: 13, fontWeight: 700 }}>年级
            <select aria-label="单元年级" value={form.grade} onChange={event => setForm(current => ({ ...current, grade: event.target.value, parent: null }))} style={{ padding: 10, border: '1px solid #d9deea', borderRadius: 8 }}>
              {allowedGrades.map(grade => <option key={grade}>{grade}</option>)}
            </select>
          </label>
          <label style={{ display: 'grid', gap: 6, fontSize: 13, fontWeight: 700 }}>层级
            <select aria-label="单元层级" value={form.parent || ''} onChange={event => setForm(current => ({ ...current, parent: event.target.value || null }))} style={{ padding: 10, border: '1px solid #d9deea', borderRadius: 8 }}>
              <option value="">大单元</option>
              {roots.filter(root => root.grade === form.grade && !root.archived_at).map(root => <option key={root.id} value={root.id}>小节 · {root.display_name}</option>)}
            </select>
          </label>
        </>}
        <label style={{ display: 'grid', gap: 6, fontSize: 13, fontWeight: 700 }}>显示名称
          <input autoFocus aria-label="单元显示名称" required value={form.display_name} onChange={event => setForm(current => ({ ...current, display_name: event.target.value }))} placeholder="如：人工智能基础" style={{ padding: 10, border: '1px solid #d9deea', borderRadius: 8 }} />
        </label>
        <label style={{ display: 'grid', gap: 6, fontSize: 13, fontWeight: 700 }}>排序
          <input aria-label="单元排序" type="number" value={form.order} onChange={event => setForm(current => ({ ...current, order: event.target.value }))} style={{ padding: 10, border: '1px solid #d9deea', borderRadius: 8 }} />
        </label>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 6 }}>
          <button type="button" onClick={onClose} style={{ padding: '9px 16px', border: '1px solid #d9deea', borderRadius: 8, background: '#fff', cursor: 'pointer' }}>取消</button>
          <button disabled={saving} type="submit" style={{ padding: '9px 18px', border: 0, borderRadius: 8, background: '#667eea', color: '#fff', fontWeight: 700, cursor: 'pointer' }}>{saving ? '保存中…' : '保存'}</button>
        </div>
      </form>
    </div>
  </div>
}

export default function AIUnitsTab({ currentUser, onChanged }) {
  const allowedGrades = currentUser?.is_superuser ? GRADES : [currentUser?.managed_grade || GRADES[0]]
  const [grade, setGrade] = useState(allowedGrades[0])
  const [includeArchived, setIncludeArchived] = useState(false)
  const [units, setUnits] = useState([])
  const [expanded, setExpanded] = useState(new Set())
  const [dialog, setDialog] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState({ type: '', text: '' })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getAIUnits({ grade, includeArchived })
      setUnits(data)
      setExpanded(current => current.size ? current : new Set(data.map(unit => unit.id)))
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setLoading(false)
    }
  }, [grade, includeArchived, setExpanded])
  useEffect(() => { load() }, [load])
  const allRoots = useMemo(() => units, [units])

  const save = async values => {
    if (dialog?.id) await updateAIUnit(dialog.id, { display_name: values.display_name, order: values.order })
    else await createAIUnit(values)
    setNotice({ type: 'success', text: dialog?.id ? '单元已更新' : '单元已创建' })
    await load()
    onChanged?.()
  }
  const toggleArchive = async unit => {
    const action = unit.archived_at ? '恢复' : '归档'
    if (!unit.archived_at && !window.confirm(`确定归档「${unit.display_name}」吗？有内容时系统会阻止归档。`)) return
    try {
      if (unit.archived_at) await restoreAIUnit(unit.id)
      else await archiveAIUnit(unit.id)
      setNotice({ type: 'success', text: `单元已${action}` })
      await load()
      onChanged?.()
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    }
  }
  const remove = async unit => {
    if (!window.confirm(`确定永久删除空${unit.parent ? '小节' : '单元'}「${unit.display_name}」吗？删除后无法恢复。`)) return
    try {
      await deleteAIUnit(unit.id)
      setNotice({ type: 'success', text: `${unit.parent ? '小节' : '单元'}已永久删除` })
      await load()
      onChanged?.()
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    }
  }

  return <section aria-labelledby="ai-units-title" style={{ display: 'grid', gap: 16 }}>
    <div style={{ ...panel, padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
      <Layers3 size={18} color="#667eea" />
      <h2 id="ai-units-title" style={{ margin: 0, fontSize: 16 }}>AI 单元管理</h2>
      <span style={{ fontSize: 12, color: '#7a8190' }}>{units.length} 个大单元</span>
      <label style={{ marginLeft: 'auto', fontSize: 12, display: 'flex', gap: 6, alignItems: 'center' }}>
        年级
        <select aria-label="单元年级筛选" value={grade} onChange={event => setGrade(event.target.value)} style={{ padding: '7px 10px', border: '1px solid #d9deea', borderRadius: 8 }}>
          {allowedGrades.map(item => <option key={item}>{item}</option>)}
        </select>
      </label>
      <label style={{ fontSize: 12, display: 'flex', gap: 6, alignItems: 'center' }}><input type="checkbox" checked={includeArchived} onChange={event => setIncludeArchived(event.target.checked)} />显示已归档</label>
      <button onClick={() => setDialog({ grade })} style={{ border: 0, borderRadius: 8, padding: '8px 14px', background: '#667eea', color: '#fff', fontWeight: 700, display: 'flex', gap: 6, cursor: 'pointer' }}><Plus size={15} />新建单元</button>
    </div>
    <Notice value={notice} />
    {loading ? <div style={{ ...panel, padding: 50, textAlign: 'center', color: '#7a8190' }}>正在加载单元…</div> : units.length === 0 ? <div style={{ ...panel, padding: 50, textAlign: 'center', color: '#7a8190' }}>该年级暂无单元，可先创建大单元，再创建小节。</div> : units.map(root => {
      const open = expanded.has(root.id)
      return <article key={root.id} style={{ ...panel, overflow: 'hidden', opacity: root.archived_at ? .68 : 1 }}>
        <div style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 10, background: open ? '#f6f7ff' : '#fff' }}>
          <button aria-label={`${open ? '收起' : '展开'}${root.display_name}`} onClick={() => setExpanded(current => { const next = new Set(current); if (next.has(root.id)) next.delete(root.id); else next.add(root.id); return next })} style={{ border: 0, background: 'transparent', cursor: 'pointer' }}>{open ? <ChevronDown size={17} /> : <ChevronRight size={17} />}</button>
          <strong>{root.display_name}</strong>
          <span style={{ color: '#7a8190', fontSize: 12 }}>{root.choice_question_count} 道选择题 · {root.programming_problem_count} 道编程题 · {root.sections?.length || 0} 个小节</span>
          {root.archived_at && <span style={{ color: '#a15c00', fontSize: 11 }}>已归档</span>}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
            {!root.archived_at && <button aria-label={`新增${root.display_name}小节`} onClick={() => setDialog({ grade: root.grade, parent: root.id })} style={{ border: '1px solid #667eea', background: '#fff', color: '#5369d8', borderRadius: 7, padding: '5px 9px', cursor: 'pointer' }}>+ 小节</button>}
            {!root.archived_at && <button aria-label={`编辑${root.display_name}`} onClick={() => setDialog(root)} style={{ border: 0, background: '#eef1ff', color: '#5369d8', borderRadius: 7, padding: 6, cursor: 'pointer' }}><Edit2 size={14} /></button>}
            <button aria-label={`${root.archived_at ? '恢复' : '归档'}${root.display_name}`} onClick={() => toggleArchive(root)} style={{ border: 0, background: root.archived_at ? '#e6f7ed' : '#ffeaec', color: root.archived_at ? '#18794e' : '#b3313d', borderRadius: 7, padding: 6, cursor: 'pointer' }}>{root.archived_at ? <RotateCcw size={14} /> : <Archive size={14} />}</button>
            {root.can_delete && <button aria-label={`永久删除${root.display_name}`} title="永久删除空单元" onClick={() => remove(root)} style={{ border: 0, background: '#fff1f2', color: '#c81e36', borderRadius: 7, padding: 6, cursor: 'pointer' }}><Trash2 size={14} /></button>}
          </div>
        </div>
        {open && <div>{(root.sections || []).length === 0 ? <div style={{ padding: '15px 54px', color: '#999', borderTop: '1px solid #edf0f5' }}>暂无小节</div> : root.sections.map(section => <div key={section.id} style={{ padding: '11px 18px 11px 54px', display: 'flex', alignItems: 'center', gap: 10, borderTop: '1px solid #edf0f5', opacity: section.archived_at ? .62 : 1 }}>
          <span style={{ flex: 1 }}>{section.display_name}</span>
          <span style={{ color: '#7a8190', fontSize: 12 }}>{section.choice_question_count} 道选择题 · {section.programming_problem_count} 道编程题</span>
          {section.archived_at && <span style={{ color: '#a15c00', fontSize: 11 }}>已归档</span>}
          {!section.archived_at && <button aria-label={`编辑${section.display_name}`} onClick={() => setDialog(section)} style={{ border: 0, background: '#eef1ff', color: '#5369d8', borderRadius: 7, padding: 6, cursor: 'pointer' }}><Edit2 size={14} /></button>}
          <button aria-label={`${section.archived_at ? '恢复' : '归档'}${section.display_name}`} onClick={() => toggleArchive(section)} style={{ border: 0, background: section.archived_at ? '#e6f7ed' : '#ffeaec', color: section.archived_at ? '#18794e' : '#b3313d', borderRadius: 7, padding: 6, cursor: 'pointer' }}>{section.archived_at ? <RotateCcw size={14} /> : <Archive size={14} />}</button>
          {section.can_delete && <button aria-label={`永久删除${section.display_name}`} title="永久删除空小节" onClick={() => remove(section)} style={{ border: 0, background: '#fff1f2', color: '#c81e36', borderRadius: 7, padding: 6, cursor: 'pointer' }}><Trash2 size={14} /></button>}
        </div>)}</div>}
      </article>
    })}
    {dialog && <UnitDialog value={dialog} roots={allRoots} defaultGrade={grade} allowedGrades={allowedGrades} onClose={() => setDialog(null)} onSave={save} />}
  </section>
}
