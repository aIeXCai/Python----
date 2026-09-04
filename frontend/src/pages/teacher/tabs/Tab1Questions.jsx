import { useState, useEffect } from 'react'
import { BookOpen, Plus, Edit2, Trash2, FileText, X, Upload, CheckCircle } from 'lucide-react'
import { GRADES } from '../../../constants/grades.js'

const DIFFICULTY_COLORS = { easy: '#38ef7d', medium: '#f59e0b', hard: '#ef4444' }

export default function Tab1Questions({
  questions, qLoading, qGradeFilter, setQGradeFilter,
  qBigUnits, qBigUnitFilter, setQBigUnitFilter,
  qAllUnits, filterUnit, setFilterUnit,
  openNewQuestion, openEditQuestion, deleteQuestion,
  openImportModal,
  difficultyLabel,
  // 导入弹窗状态
  importModal, setImportModal,
  importFileName, setImportFileName,
  importPreview, setImportPreview,
  importing,
  handleFileSelect, handleDrop,
  doImport, importMsg,
  // 题目弹窗
  qModal, setQModal, qForm, setQForm, qMsg, handleSaveQuestion, qSaving,
  // 筛选 & 批量
  handleApplyFilter,
  selectedQuestions, handleSelectAll, handleSelectOne, handleBatchDelete,
  API, token,
}) {
  const difficultyBadgeColor = (d) => DIFFICULTY_COLORS[d] || '#888'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* 题目列表卡片 */}
      <div style={{ background: 'white', borderRadius: 14, overflow: 'hidden', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }}>
        {/* 单行布局：标题 + 筛选 + 按钮 */}
        <div style={{
          padding: '12px 24px',
          display: 'flex', alignItems: 'center', gap: 8
        }}>
          <BookOpen size={18} style={{ color: '#11999e', flexShrink: 0 }} />
          <span style={{ fontSize: 15, fontWeight: 700, color: '#333', marginRight: 6, flexShrink: 0 }}>题目列表</span>
          <span style={{ fontSize: 12, color: '#888', marginRight: 12, flexShrink: 0 }}>共 {questions.length} 题</span>

          {/* 年级筛选 */}
          <select value={qGradeFilter} onChange={e => setQGradeFilter(e.target.value)}
            style={{ padding: '4px 6px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 12, flexShrink: 0 }}>
            {GRADES.map(g => <option key={g} value={g}>{g}</option>)}
          </select>

          {/* 大单元筛选 */}
          <select value={qBigUnitFilter} onChange={e => { setQBigUnitFilter(e.target.value); setFilterUnit('') }}
            style={{ padding: '4px 6px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 12, flexShrink: 0 }}>
            <option value="">全部大单元</option>
            {qBigUnits.map(b => (
              <option key={b.id} value={b.name}>{b.display_name || b.name}</option>
            ))}
          </select>

          {/* 小节筛选 */}
          <select value={filterUnit} onChange={e => setFilterUnit(e.target.value)}
            style={{ padding: '4px 6px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 12, flexShrink: 0 }}>
            <option value="">全部小节</option>
            {qAllUnits
              .filter(u => u.parent != null)
              .filter(u => qBigUnitFilter === '' || u.parent?.name === qBigUnitFilter)
              .map(u => (
                <option key={u.id} value={u.name}>└ {u.display_name || u.name}</option>
              ))}
          </select>

          {/* 筛选按钮 */}
          <button onClick={handleApplyFilter} style={{
            padding: '5px 12px', borderRadius: 8, border: '1.5px solid #11998e', background: 'white', color: '#11998e',
            cursor: 'pointer', fontWeight: 700, fontSize: 12, flexShrink: 0,
          }}>
            🔍 筛选
          </button>

          {/* 批量删除 */}
          {selectedQuestions.length > 0 && (
            <button onClick={handleBatchDelete} style={{
              padding: '5px 12px', borderRadius: 8, border: 'none', background: '#ef4444', color: 'white',
              cursor: 'pointer', fontWeight: 700, fontSize: 12, flexShrink: 0,
            }}>
              🗑 已选 {selectedQuestions.length}
            </button>
          )}

          {/* 右侧操作按钮 */}
          <button onClick={openImportModal} style={{
            padding: '5px 12px', borderRadius: 8, border: '1.5px solid #667eea', background: 'white', color: '#667eea',
            cursor: 'pointer', fontWeight: 700, fontSize: 12, display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0,
          }}>
            <FileText size={12} /> 导入
          </button>

          <button onClick={openNewQuestion} style={{
            padding: '5px 12px', borderRadius: 8, border: 'none', background: '#11998e', color: 'white',
            cursor: 'pointer', fontWeight: 700, fontSize: 12, display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0,
          }}>
            <Plus size={12} /> 新建题目
          </button>
        </div>

        {/* 表格 */}
        {qLoading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>加载中...</div>
        ) : questions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
            <BookOpen size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
            <p>暂无题目</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#f8f9fa' }}>
                  <th style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 700, color: '#666', whiteSpace: 'nowrap' }}>
                    <input type="checkbox"
                      checked={questions.length > 0 && selectedQuestions.length === questions.length}
                      onChange={e => handleSelectAll(e.target.checked)}
                      style={{ cursor: 'pointer', width: 16, height: 16 }}
                    />
                  </th>
                  {['#', '年级', '大单元', '小节', '难度', '题目摘要', '答案', '操作'].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontWeight: 700, color: '#666', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {questions.map((q, i) => (
                  <tr key={q.id} style={{ borderBottom: '1px solid #f0f0f0', background: selectedQuestions.includes(q.id) ? '#fff3cd' : 'white' }}
                    onMouseEnter={e => e.currentTarget.style.background = selectedQuestions.includes(q.id) ? '#ffeeba' : '#f8f9fa'}
                    onMouseLeave={e => e.currentTarget.style.background = selectedQuestions.includes(q.id) ? '#fff3cd' : 'white'}>
                    <td style={{ padding: '10px 14px' }}>
                      <input type="checkbox"
                        checked={selectedQuestions.includes(q.id)}
                        onChange={() => handleSelectOne(q.id)}
                        style={{ cursor: 'pointer', width: 16, height: 16 }}
                      />
                    </td>
                    <td style={{ padding: '10px 14px', color: '#888' }}>{i + 1}</td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{
                        padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                        background: q.grade === '七年级' ? '#c7d2fe' : '#bbf7d0',
                        color: q.grade === '七年级' ? '#4338ca' : '#15803d'
                      }}>
                        {q.grade}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: '#667eea22', color: '#667eea' }}>
                        {q.big_unit_name || q.unit_name}
                      </span>
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      {q.unit_name && q.big_unit_name && (
                        <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: '#11998e22', color: '#11998e' }}>
                          {q.unit_name}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: `${difficultyBadgeColor(q.difficulty)}22`, color: difficultyBadgeColor(q.difficulty) }}>
                        {difficultyLabel(q.difficulty)}
                      </span>
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

      {/* ── 题目弹窗（新建/编辑） ─────────────────────────────────────────── */}
      {qModal.open && (
        <QuestionModal
          qModal={qModal} setQModal={setQModal}
          qForm={qForm} setQForm={setQForm}
          qMsg={qMsg} handleSaveQuestion={handleSaveQuestion}
          qSaving={qSaving}
          qAllUnits={qAllUnits}
        />
      )}

      {/* ── 批量导入弹窗 ─────────────────────────────────────────────────── */}
      {importModal.open && (
        <ImportModal
          importModal={importModal} setImportModal={setImportModal}
          importFileName={importFileName} setImportFileName={setImportFileName}
          importPreview={importPreview} setImportPreview={setImportPreview}
          importing={importing}
          handleFileSelect={handleFileSelect} handleDrop={handleDrop}
          doImport={doImport} importMsg={importMsg}
          API={API} token={token}
        />
      )}
    </div>
  )
}

// ── 题目弹窗 ────────────────────────────────────────────────────────────────
function QuestionModal({ qModal, setQModal, qForm, setQForm, qMsg, handleSaveQuestion, qSaving, qAllUnits }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }} onClick={() => setQModal({ open: false, mode: 'create', data: null })}>
      <div style={{ background: 'white', borderRadius: 16, padding: '28px', maxWidth: 640, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)', maxHeight: '88vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>
            {qModal.mode === 'edit' ? '编辑题目' : '新建题目'}
          </h2>
          <button onClick={() => setQModal({ open: false, mode: 'create', data: null })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}><X size={20} /></button>
        </div>

        {qMsg.text ? (
          <div style={{
            padding: '10px 16px', borderRadius: 8, marginBottom: 16, fontSize: 13, fontWeight: 600,
            background: qMsg.type === 'success' ? '#d4edda' : '#f8d7da',
            color: qMsg.type === 'success' ? '#155724' : '#721c24',
            border: `1px solid ${qMsg.type === 'success' ? '#c3e6cb' : '#f5c6cb'}`
          }}>{qMsg.text}</div>
        ) : null}

        <form onSubmit={handleSaveQuestion} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* 单元 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>所属小节 *</label>
              <select value={qForm.unit} onChange={e => setQForm(p => ({ ...p, unit: e.target.value }))}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }} required>
                <option value="">— 选择小节 —</option>
                {qAllUnits.filter(u => u.parent != null).map(u => (
                  <option key={u.id} value={u.name}>{u.display_name || u.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>难度</label>
              <select value={qForm.difficulty} onChange={e => setQForm(p => ({ ...p, difficulty: e.target.value }))}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }}>
                <option value="easy">容易</option>
                <option value="medium">中等</option>
                <option value="hard">困难</option>
              </select>
            </div>
          </div>

          {/* 题目正文 */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>题目正文 *</label>
            <textarea value={qForm.text} onChange={e => setQForm(p => ({ ...p, text: e.target.value }))} rows={3}
              placeholder="请输入题目内容"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, resize: 'vertical', boxSizing: 'border-box' }} required />
          </div>

          {/* 选项 */}
          {[['A', 'option_a'], ['B', 'option_b'], ['C', 'option_c'], ['D', 'option_d']].map(([key, field]) => (
            <div key={field} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 20, fontWeight: 800, color: '#11998e', fontSize: 13 }}>{key}.</span>
              <input value={qForm[field]} onChange={e => setQForm(p => ({ ...p, [field]: e.target.value }))}
                placeholder={`选项 ${key}`}
                style={{ flex: 1, padding: '7px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }} required />
            </div>
          ))}

          {/* 正确答案 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666' }}>正确答案 *</label>
            {['A', 'B', 'C', 'D'].map(opt => (
              <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', fontSize: 13 }}>
                <input type="radio" name="answer" value={opt} checked={qForm.answer === opt}
                  onChange={e => setQForm(p => ({ ...p, answer: e.target.value }))} />
                {opt}
              </label>
            ))}
          </div>

          {/* 分类 & 解析 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>知识点分类</label>
              <input value={qForm.category} onChange={e => setQForm(p => ({ ...p, category: e.target.value }))}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }} />
            </div>
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 4 }}>解析（可选）</label>
              <textarea value={qForm.explanation} onChange={e => setQForm(p => ({ ...p, explanation: e.target.value }))} rows={2}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13, resize: 'vertical', boxSizing: 'border-box' }} />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 4 }}>
            <button type="button" onClick={() => setQModal({ open: false, mode: 'create', data: null })} style={{ padding: '9px 18px', borderRadius: 8, border: '1.5px solid #ddd', background: 'white', cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>取消</button>
            <button type="submit" disabled={qSaving} style={{ padding: '9px 20px', borderRadius: 8, border: 'none', background: qSaving ? '#aaa' : '#11998e', color: 'white', cursor: qSaving ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 13 }}>
              {qSaving ? '保存中...' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── 批量导入弹窗 ────────────────────────────────────────────────────────────
function ImportModal({ importModal, setImportModal, importFileName, importPreview, importing, handleFileSelect, handleDrop, doImport, importMsg, API, token }) {
  const [importUnits, setImportUnits] = useState([])

  // 每次年级变化时重新加载对应年级的单元
  useEffect(() => {
    if (!importModal.open) return
    const headers = { 'Content-Type': 'application/json', 'Authorization': `Token ${token}` }
    fetch(`${API}/admin/info/units/?grade=${importModal.grade}`, { headers })
      .then(r => r.json())
      .then(data => {
        setImportUnits(Array.isArray(data) ? data : [])
        // 切换年级后清空已选单元
        setImportModal(p => ({ ...p, unit: '' }))
      })
      .catch(() => setImportUnits([]))
  }, [importModal.grade, importModal.open])

  const selectedBigUnit = importUnits.find(b => b.sections?.some(s => s.name === importModal.unit))

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }} onClick={() => setImportModal({ open: false, unit: '', grade: '七年级', file: null })}>
      <div style={{ background: 'white', borderRadius: 16, padding: '28px', maxWidth: 560, width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)', maxHeight: '88vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, color: '#333', margin: 0 }}>
            <FileText size={18} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 8, color: '#667eea' }} />
            批量导入题目
          </h2>
          <button onClick={() => setImportModal({ open: false, unit: '', grade: '七年级', file: null })} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}><X size={20} /></button>
        </div>

        {importMsg.text ? (
          <div style={{
            padding: '10px 16px', borderRadius: 8, marginBottom: 16, fontSize: 13, fontWeight: 600,
            background: importMsg.type === 'success' ? '#d4edda' : '#f8d7da',
            color: importMsg.type === 'success' ? '#155724' : '#721c24',
            border: `1px solid ${importMsg.type === 'success' ? '#c3e6cb' : '#f5c6cb'}`
          }}>{importMsg.text}</div>
        ) : null}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* 步骤1：选择年级 */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 6 }}>步骤1：选择年级</label>
            <div style={{ display: 'flex', gap: 8 }}>
              {GRADES.map(g => (
                <button key={g} onClick={() => setImportModal(p => ({ ...p, grade: g, unit: '' }))}
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

          {/* 步骤2：选择目标单元 */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 6 }}>步骤2：选择目标单元（小节）</label>
            <select value={importModal.unit} onChange={e => setImportModal(p => ({ ...p, unit: e.target.value }))}
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1.5px solid #ddd', fontSize: 13 }}>
              <option value="">— 请先选择年级 —</option>
              {importUnits.length === 0 ? (
                <option value="" disabled>该年级暂无单元，请先去「单元管理」创建</option>
              ) : (
                importUnits
                  .map(big => (
                    <optgroup key={big.id} label={big.display_name || big.name}>
                      {(big.sections || []).map(sec => (
                        <option key={sec.id} value={sec.name}>{sec.display_name || sec.name}</option>
                      ))}
                    </optgroup>
                  ))
              )}
            </select>
            {importModal.unit && selectedBigUnit && (
              <p style={{ margin: '6px 0 0', fontSize: 12, color: '#11998e' }}>
                ✓ 题目将导入到：「{selectedBigUnit.display_name} → {importModal.unit}」
              </p>
            )}
          </div>

          {/* 步骤3：上传文件 */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#666', display: 'block', marginBottom: 6 }}>步骤3：上传 JSON 文件</label>
            <div
              onDrop={handleDrop}
              onDragOver={e => e.preventDefault()}
              onClick={() => document.getElementById('import-file-input').click()}
              style={{
                border: '2px dashed #667eea', borderRadius: 12,
                padding: '32px 20px', textAlign: 'center', cursor: 'pointer',
                background: importFileName ? '#f5f0ff' : '#fafbff', transition: 'all 0.2s',
              }}>
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

          {/* 格式说明 */}
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
      </div>
    </div>
  )
}
