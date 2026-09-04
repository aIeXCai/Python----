import { useState, useEffect } from 'react'
import { ClipboardList, Plus, Edit2, Trash2, Play, X, ChevronDown } from 'lucide-react'
import { apiUrl } from '../../../api/config.js'
import { GRADES } from '../../../constants/grades.js'

export default function Tab2Sessions({
  sessions, sLoading,
  unitGradeFilter,
  openNewSession, openEditSession, deleteSession,
  handleStartSession, handleEndSession,
  // 弹窗状态
  sModal, setSModal, sForm, setSForm, sMsg, handleSaveSession, sSaving,
}) {
  const gradeColor = (g) => ({ '七年级': '#38ef7d', '八年级': '#11999e', '九年级': '#f59e0b' })[g] || '#888'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* 顶部操作栏 */}
      <div style={{
        background: 'white', borderRadius: 14, padding: '16px 20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap'
      }}>
        <ClipboardList size={18} style={{ color: '#667eea' }} />
        <span style={{ fontSize: 15, fontWeight: 700, color: '#333' }}>小测列表</span>
        <span style={{ marginLeft: 4, fontSize: 12, color: '#888' }}>共 {sessions.length} 场小测</span>
        <button onClick={openNewSession} style={{
          marginLeft: 'auto', padding: '7px 16px', borderRadius: 8, border: 'none', background: '#667eea', color: 'white',
          cursor: 'pointer', fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6
        }}>
          <Plus size={14} /> 新建小测
        </button>
      </div>

      {/* 小测表格 */}
      <div style={{ background: 'white', borderRadius: 14, overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        {sLoading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>加载中...</div>
        ) : sessions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
            <ClipboardList size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
            <p>暂无小测</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#f8f9fa' }}>
                  {['#', '名称', '年级', '可见班级', '大单元', '小节', '时长', '题数', '状态', '操作'].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 700, color: '#666', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map((s, i) => {
                  const status = s.status === 'open'
                    ? { label: '进行中', color: '#38ef7d', bg: '#d4edda' }
                    : s.status === 'closed'
                      ? { label: `已关闭(${s.submission_count})`, color: '#667eea', bg: '#e8eafc' }
                      : { label: '未发布', color: '#888', bg: '#f0f0f0' }
                  return (
                    <tr key={s.id} style={{ borderBottom: '1px solid #f0f0f0' }}
                      onMouseEnter={e => e.currentTarget.style.background = '#f8f9fa'}
                      onMouseLeave={e => e.currentTarget.style.background = 'white'}>
                      <td style={{ padding: '10px 14px', color: '#888' }}>{i + 1}</td>
                      <td style={{ padding: '10px 14px', fontWeight: 700, color: '#333' }}>{s.title}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: `${gradeColor(s.grade)}22`, color: gradeColor(s.grade) }}>
                          {s.grade}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px', color: '#555', whiteSpace: 'nowrap' }}>
                        {s.visible_classes?.length
                          ? s.visible_classes.map(value => `${value}班`).join('、')
                          : '全年级'}
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: '#e8d5f5', color: '#7c3aed' }}>
                          {s.big_unit_names?.join('、') || '—'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: '#d1fae5', color: '#15803d' }}>
                          {s.section_names?.join('、') || '—'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px', color: '#666' }}>{s.time_limit}分钟</td>
                      <td style={{ padding: '10px 14px', color: '#666' }}>{s.num_questions}题</td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: status.bg, color: status.color }}>
                          {status.label}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>
                        {s.status === 'open' ? (
                          <button onClick={() => handleEndSession(s.id)} style={{ background: 'none', border: '1px solid #f59e0b', borderRadius: 6, cursor: 'pointer', color: '#f59e0b', padding: '3px 10px', fontSize: 12, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            结束
                          </button>
                        ) : s.status === 'draft' || s.status === 'closed' ? (
                          <button onClick={() => handleStartSession(s.id)} style={{ background: 'none', border: '1px solid #38ef7d', borderRadius: 6, cursor: 'pointer', color: '#38ef7d', padding: '3px 10px', fontSize: 12, fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            <Play size={11} /> {s.status === 'closed' ? '重新开放' : '开始'}
                          </button>
                        ) : null}
                        <button aria-label={`编辑${s.title}`} onClick={() => openEditSession(s)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#17a2b8', padding: '4px', display: 'inline-flex', marginLeft: 6 }}><Edit2 size={14} /></button>
                        <button aria-label={`删除${s.title}`} onClick={() => deleteSession(s)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc3545', padding: '4px', display: 'inline-flex', marginLeft: 2 }}><Trash2 size={14} /></button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 新建/编辑小测弹窗 */}
      {sModal.open && (
        <SessionModal
          sModal={sModal} setSModal={setSModal}
          sForm={sForm} setSForm={setSForm}
          sMsg={sMsg} handleSaveSession={handleSaveSession}
          sSaving={sSaving}
          unitGradeFilter={unitGradeFilter}
        />
      )}
    </div>
  )
}

// ── 小测弹窗 ────────────────────────────────────────────────────────────────
function SessionModal({ sModal, setSModal, sForm, setSForm, sMsg, handleSaveSession, sSaving, unitGradeFilter }) {
  const [modalUnits, setModalUnits] = useState([])  // 自主管理，不依赖父组件
  const [availableClasses, setAvailableClasses] = useState([])
  const [classDropdownOpen, setClassDropdownOpen] = useState(false)

  // 年级变化时重新加载该年级的单元
  useEffect(() => {
    if (!sModal.open) return
    const grade = sForm.grade || unitGradeFilter || '七年级'
    // 从 InfoAdmin 的 token/headers 需要通过 props 传入，这里用 localStorage 凑合
    const token = localStorage.getItem('token') || ''
    fetch(apiUrl(`/admin/info/units/?grade=${encodeURIComponent(grade)}`), {
      headers: { 'Authorization': `Token ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data)) {
          const flat = data.flatMap(b => [
            { ...b, parent: null, is_big: true },
            ...(b.sections || []).map(s => ({ ...s, parent: b, is_big: false }))
          ])
          setModalUnits(flat)
        }
      })
      .catch(() => setModalUnits([]))

    fetch(apiUrl(`/admin/info/classes/?grade=${encodeURIComponent(grade)}`), {
      headers: { 'Authorization': `Token ${token}` }
    })
      .then(r => r.json())
      .then(data => setAvailableClasses(Array.isArray(data?.classes) ? data.classes : []))
      .catch(() => setAvailableClasses([]))
  }, [sModal.open, sForm.grade, unitGradeFilter])

  const selectedUnitNames = sForm.units
    ? modalUnits.filter(u => sForm.units.includes(u.id)).map(u => u.display_name)
    : []

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }} onClick={() => setSModal({ open: false, mode: 'create', data: null })}>
      <div style={{ background: 'white', borderRadius: 16, padding: '28px', maxWidth: 520, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>
            {sModal.mode === 'edit' ? '编辑小测' : '新建小测'}
          </h2>
          <button onClick={() => setSModal({ open: false, mode: 'create', data: null })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}><X size={20} /></button>
        </div>

        {sMsg.text ? (
          <div style={{
            padding: '10px 16px', borderRadius: 8, marginBottom: 16, fontSize: 13, fontWeight: 600,
            background: sMsg.type === 'success' ? '#d4edda' : '#f8d7da',
            color: sMsg.type === 'success' ? '#155724' : '#721c24',
            border: `1px solid ${sMsg.type === 'success' ? '#c3e6cb' : '#f5c6cb'}`
          }}>{sMsg.text}</div>
        ) : null}

        <form onSubmit={handleSaveSession} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>小测名称 *</label>
            <input value={sForm.name} onChange={e => setSForm(p => ({ ...p, name: e.target.value }))}
              placeholder="如：第一章 算法基础 小测"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, boxSizing: 'border-box' }} required />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>年级</label>
              <select value={sForm.grade} onChange={e => {
                setClassDropdownOpen(false)
                setSForm(p => ({ ...p, grade: e.target.value, units: [], visible_classes: [] }))
              }}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }}>
                {GRADES.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>时长（分钟）</label>
              <input type="number" value={sForm.duration} onChange={e => setSForm(p => ({ ...p, duration: parseInt(e.target.value) || 10 }))}
                min={5} max={120} style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, boxSizing: 'border-box' }} />
            </div>
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 6 }}>
              可见班级
            </label>
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                aria-label="选择可见班级"
                aria-expanded={classDropdownOpen}
                aria-haspopup="listbox"
                onClick={() => setClassDropdownOpen(open => !open)}
                style={{
                  width: '100%', minHeight: 38, padding: '8px 10px', borderRadius: 8,
                  border: `1.5px solid ${classDropdownOpen ? '#667eea' : '#ddd'}`,
                  background: 'white', cursor: 'pointer', fontSize: 13, color: '#333',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
                  boxSizing: 'border-box', textAlign: 'left'
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {sForm.visible_classes?.length
                    ? sForm.visible_classes.map(value => `${value}班`).join('、')
                    : '全年级（全选）'}
                </span>
                <ChevronDown size={16} style={{ flexShrink: 0, color: '#777', transform: classDropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />
              </button>

              {classDropdownOpen && (
                <div
                  role="listbox"
                  aria-label="可见班级列表"
                  aria-multiselectable="true"
                  style={{
                    position: 'absolute', zIndex: 20, left: 0, right: 0, top: 'calc(100% + 4px)',
                    maxHeight: 180, overflowY: 'auto', padding: '8px 10px', border: '1.5px solid #ddd',
                    borderRadius: 8, background: 'white', boxShadow: '0 8px 24px rgba(0,0,0,0.14)',
                    display: 'flex', flexDirection: 'column', gap: 7
                  }}
                >
                  <label style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', fontSize: 13, fontWeight: 700, color: '#667eea' }}>
                    <input
                      type="checkbox"
                      aria-label="全年级"
                      checked={!sForm.visible_classes?.length}
                      onChange={() => setSForm(p => ({ ...p, visible_classes: [] }))}
                      style={{ accentColor: '#667eea' }}
                    />
                    全年级（全选）
                  </label>
                  {availableClasses.map(classNum => {
                    const selected = sForm.visible_classes || []
                    const checked = selected.includes(classNum)
                    return (
                      <label key={classNum} style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', fontSize: 13 }}>
                        <input
                          type="checkbox"
                          aria-label={`${classNum}班`}
                          checked={checked}
                          onChange={() => {
                            setSForm(p => {
                              const current = p.visible_classes || []
                              if (!current.length) return { ...p, visible_classes: [classNum] }
                              if (current.includes(classNum)) {
                                if (current.length === 1) return p
                                return { ...p, visible_classes: current.filter(value => value !== classNum) }
                              }
                              return { ...p, visible_classes: [...current, classNum] }
                            })
                          }}
                          style={{ accentColor: '#667eea' }}
                        />
                        {classNum}班
                      </label>
                    )
                  })}
                  {availableClasses.length === 0 && (
                    <span style={{ color: '#888', fontSize: 12 }}>该年级暂无班级数据，将按全年级开放</span>
                  )}
                </div>
              )}
            </div>
            <div style={{ marginTop: 5, color: '#888', fontSize: 11 }}>
              选择“全年级”会自动包含以后新增的班级；点击具体班级可切换为多班级范围。
            </div>
          </div>

          {/* 关联小节（多选） */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>
              关联小节 <span style={{ color: '#dc3545' }}>*</span>
            </label>
            {modalUnits.length === 0 ? (
              <div style={{ fontSize: 12, color: '#888', padding: '4px 0' }}>加载中...</div>
            ) : (
              <div style={{ maxHeight: 180, overflowY: 'auto', border: '1.5px solid #ddd', borderRadius: 8, padding: '6px 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {modalUnits.map(u => (
                  <label key={u.id} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, padding: '2px 0' }}>
                    <input
                      type="checkbox"
                      checked={sForm.units?.includes(u.id) || false}
                      onChange={e => {
                        const cur = sForm.units || []
                        const updated = e.target.checked
                          ? [...cur, u.id]
                          : cur.filter(id => id !== u.id)
                        setSForm(p => ({ ...p, units: updated }))
                      }}
                      style={{ accentColor: '#667eea' }}
                    />
                    {u.is_big
                      ? <span style={{ color: '#8b5cf6', fontWeight: 600 }}>{u.display_name}</span>
                      : <span style={{ color: '#333' }}>{u.display_name}</span>
                    }
                  </label>
                ))}
              </div>
            )}
            {selectedUnitNames.length > 0 && (
              <div style={{ marginTop: 6, fontSize: 11, color: '#667eea' }}>
                已选：{selectedUnitNames.join('、')}
              </div>
            )}
          </div>

          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>抽题数量</label>
            <input type="number" value={sForm.question_count} onChange={e => setSForm(p => ({ ...p, question_count: parseInt(e.target.value) || 5 }))}
              min={1} max={50} style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, boxSizing: 'border-box' }} />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 4 }}>
            <button type="button" onClick={() => setSModal({ open: false, mode: 'create', data: null })} style={{ padding: '9px 18px', borderRadius: 8, border: '1.5px solid #ddd', background: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>取消</button>
            <button type="submit" disabled={sSaving || !sForm.units?.length} style={{ padding: '9px 20px', borderRadius: 8, border: 'none', background: (sSaving || !sForm.units?.length) ? '#aaa' : '#667eea', color: 'white', cursor: (sSaving || !sForm.units?.length) ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 13 }}>
              {sSaving ? '保存中...' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
