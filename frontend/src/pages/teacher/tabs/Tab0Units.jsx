import { useState } from 'react'
import {
  Plus, Edit2, Trash2, ListChecks, CheckCircle, X
} from 'lucide-react'

export default function Tab0Units({
  bigUnits, unitGradeFilter, setUnitGradeFilter,
  expandedUnits, toggleUnit,
  openNewBigUnit, openAddSection,
  editUnit, setEditUnit, handleUpdateUnit,
  deleteUnit,
  newBigUnitOpen, sectionModal,
  unitForm, setUnitForm,
  unitMsg, handleCreateBigUnit, handleSaveSection,
  loadUnits,
  gradeColor,
  API, headers,
}) {
  const grades = [
    { value: '七年级', label: '七年级' },
    { value: '八年级', label: '八年级' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* 顶部栏 */}
      <div style={{
        background: 'white', borderRadius: 14, padding: '16px 20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
        display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap'
      }}>
        <ListChecks size={18} style={{ color: '#11998e' }} />
        <span style={{ fontSize: 15, fontWeight: 700, color: '#333' }}>单元列表</span>
        <span style={{ marginLeft: 4, fontSize: 12, color: '#888' }}>共 {bigUnits.length} 个大单元</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#555' }}>年级</span>
          <select value={unitGradeFilter} onChange={e => setUnitGradeFilter(e.target.value)}
            style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid #ddd', fontSize: 13, minWidth: 100 }}>
            {grades.map(g => <option key={g.value} value={g.value}>{g.label}</option>)}
          </select>
        </div>
        <button onClick={openNewBigUnit}
          style={{
            padding: '7px 16px', borderRadius: 8, border: 'none', background: '#11998e', color: 'white',
            cursor: 'pointer', fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6
          }}>
          <Plus size={14} /> 新建大单元
        </button>
      </div>

      {/* 空状态 */}
      {bigUnits.length === 0 && (
        <div style={{
          background: 'white', borderRadius: 14, padding: '48px 24px', textAlign: 'center',
          color: '#aaa', boxShadow: '0 2px 8px rgba(0,0,0,0.06)'
        }}>
          <ListChecks size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
          <p>该年级暂无大单元，请点击"新建大单元"创建</p>
        </div>
      )}

      {/* 大单元列表 */}
      {bigUnits.map(big => (
        <div key={big.id} style={{
          background: 'white', borderRadius: 14,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)', overflow: 'hidden'
        }}>
          {/* 大单元标题行 */}
          <div style={{
            padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 10,
            background: expandedUnits.has(big.id) ? '#f0faf9' : 'white',
            borderLeft: `4px solid ${gradeColor(unitGradeFilter)}`
          }}>
            <button onClick={() => toggleUnit(big.id)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#555', padding: 0 }}>
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
            {(!editUnit || editUnit.id !== big.id) && (
              <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={() => openAddSection(big)}
                  style={{ background: 'none', border: '1px solid #11998e', borderRadius: 6, cursor: 'pointer', color: '#11998e', padding: '3px 10px', fontSize: 12, fontWeight: 600 }}>
                  + 小节
                </button>
                <button onClick={() => setEditUnit({ id: big.id, name: big.name, display_name: big.display_name || '' })}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#17a2b8', padding: 2 }}><Edit2 size={14} /></button>
                <button onClick={() => deleteUnit(big.id)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc3545', padding: 2 }}><Trash2 size={14} /></button>
              </div>
            )}
          </div>

          {/* 小节列表 */}
          {expandedUnits.has(big.id) && (big.sections || []).length > 0 && (
            <div style={{ borderTop: '1px solid #f0f0f0', background: '#fafcfb' }}>
              {(big.sections || []).map(sec => (
                <div key={sec.id} style={{
                  padding: '10px 20px 10px 56px', display: 'flex', alignItems: 'center', gap: 10,
                  borderBottom: '1px solid #f0f0f0'
                }}>
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
        <BigUnitModal
          unitForm={unitForm} setUnitForm={setUnitForm}
          unitMsg={unitMsg} handleSubmit={handleCreateBigUnit}
          onClose={() => {}}
          unitGradeFilter={unitGradeFilter}
        />
      )}

      {/* 新建/编辑小节弹窗 */}
      {sectionModal.open && (
        <SectionModal
          sectionModal={sectionModal}
          unitForm={unitForm} setUnitForm={setUnitForm}
          unitMsg={unitMsg} handleSubmit={handleSaveSection}
          onClose={() => {}}
        />
      )}
    </div>
  )
}

// ── 新建大单元弹窗 ──────────────────────────────────────────────────────────
function BigUnitModal({ unitForm, setUnitForm, unitMsg, handleSubmit, onClose, unitGradeFilter }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }} onClick={onClose}>
      <div style={{ background: 'white', borderRadius: 16, padding: '28px', maxWidth: 480, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>新建大单元</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}><X size={20} /></button>
        </div>
        {unitMsg.text ? (
          <div style={{
            padding: '10px 16px', borderRadius: 8, marginBottom: 16, fontSize: 13, fontWeight: 600,
            background: unitMsg.type === 'success' ? '#d4edda' : '#f8d7da',
            color: unitMsg.type === 'success' ? '#155724' : '#721c24',
            border: `1px solid ${unitMsg.type === 'success' ? '#c3e6cb' : '#f5c6cb'}`
          }}>{unitMsg.text}</div>
        ) : null}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
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
            <button type="button" onClick={onClose} style={{ padding: '9px 18px', borderRadius: 8, border: '1.5px solid #ddd', background: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>取消</button>
            <button type="submit" style={{ padding: '9px 20px', borderRadius: 8, border: 'none', background: '#11998e', color: 'white', cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>创建</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── 新建/编辑小节弹窗 ───────────────────────────────────────────────────────
function SectionModal({ sectionModal, unitForm, setUnitForm, unitMsg, handleSubmit, onClose }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }} onClick={onClose}>
      <div style={{ background: 'white', borderRadius: 16, padding: '28px', maxWidth: 480, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>
            在"{sectionModal.bigUnit?.display_name}"下新增小节
          </h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}><X size={20} /></button>
        </div>
        {unitMsg.text ? (
          <div style={{
            padding: '10px 16px', borderRadius: 8, marginBottom: 16, fontSize: 13, fontWeight: 600,
            background: unitMsg.type === 'success' ? '#d4edda' : '#f8d7da',
            color: unitMsg.type === 'success' ? '#155724' : '#721c24',
            border: `1px solid ${unitMsg.type === 'success' ? '#c3e6cb' : '#f5c6cb'}`
          }}>{unitMsg.text}</div>
        ) : null}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>所属大单元</label>
            <input value={sectionModal.bigUnit?.display_name || ''} disabled
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #eee', fontSize: 13, background: '#f5f5f5', color: '#666', boxSizing: 'border-box' }} />
          </div>
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>小节名称 *</label>
            <input value={unitForm.display_name} onChange={e => setUnitForm(p => ({ ...p, display_name: e.target.value }))}
              placeholder="如：1.1 变量的概念"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, boxSizing: 'border-box' }} required />
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
            <button type="button" onClick={onClose} style={{ padding: '9px 18px', borderRadius: 8, border: '1.5px solid #ddd', background: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>取消</button>
            <button type="submit" style={{ padding: '9px 20px', borderRadius: 8, border: 'none', background: '#11998e', color: 'white', cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>保存</button>
          </div>
        </form>
      </div>
    </div>
  )
}
