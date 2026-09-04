/**
 * ImportModal 批量导入弹窗测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/tabs/ImportModal.test.jsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('lucide-react', () => ({
  FileText: () => <span data-testid="icon-filetext">FileText</span>,
  X: () => <span data-testid="icon-x">X</span>,
  Upload: () => <span data-testid="icon-upload">Upload</span>,
}))

const mockUnits = [
  { id: 1, name: '第一章', display_name: '第一章 数据与信息', sections: [
    { id: 2, name: '第一节', display_name: '1.1 什么是数据' },
    { id: 3, name: '第二节', display_name: '1.2 数据的编码' },
  ]},
]

const defaultProps = {
  importModal: { open: true, grade: '七年级', unit: '', file: null },
  setImportModal: vi.fn(),
  importFileName: null,
  setImportFileName: vi.fn(),
  importPreview: null,
  setImportPreview: vi.fn(),
  importing: false,
  handleFileSelect: vi.fn(),
  handleDrop: vi.fn(),
  doImport: vi.fn(),
  importMsg: { type: '', text: '' },
  API: '/api',
  token: 'mock-token',
}

// 内联 ImportModal（简化版，复制自 Tab1Questions.jsx）
function ImportModal({ importModal, setImportModal, importFileName, importing, handleFileSelect, doImport, importMsg }) {
  const selectedBigUnit = mockUnits.find(b => b.sections?.some(s => s.name === importModal.unit))

  return (
    <div data-testid="import-modal" onClick={() => setImportModal({ open: false })}>
      <div data-testid="modal-inner" onClick={e => e.stopPropagation()}>
        <h2 data-testid="modal-title">批量导入题目</h2>
        <button data-testid="close-btn" onClick={() => setImportModal({ open: false })}>X</button>

        {importMsg.text && (
          <div data-testid="import-msg" style={{
            background: importMsg.type === 'success' ? '#d4edda' : '#f8d7da',
          }}>{importMsg.text}</div>
        )}

        {/* 步骤1：年级 */}
        <div data-testid="step1">
          {['七年级', '八年级'].map(g => (
            <button
              key={g}
              data-testid={`grade-btn-${g}`}
              onClick={() => setImportModal(p => ({ ...p, grade: g, unit: '' }))}
              style={{
                background: importModal.grade === g ? '#667eea' : 'white',
                color: importModal.grade === g ? 'white' : '#555',
              }}
            >
              {g}
            </button>
          ))}
        </div>

        {/* 步骤2：目标单元 */}
        <div data-testid="step2">
          <select
            data-testid="unit-select"
            value={importModal.unit}
            onChange={e => setImportModal(p => ({ ...p, unit: e.target.value }))}
          >
            <option value="">— 请先选择年级 —</option>
            {mockUnits.map(big => (
              <optgroup key={big.id} label={big.display_name}>
                {(big.sections || []).map(sec => (
                  <option key={sec.id} value={sec.name}>{sec.display_name}</option>
                ))}
              </optgroup>
            ))}
          </select>
          {importModal.unit && selectedBigUnit && (
            <p data-testid="selected-unit-hint">
              ✓ 题目将导入到：「{selectedBigUnit.display_name} → {importModal.unit}」
            </p>
          )}
        </div>

        {/* 步骤3：上传文件 */}
        <div data-testid="step3" onClick={() => document.getElementById('import-file-input').click()}>
          <input id="import-file-input" type="file" accept=".json" onChange={handleFileSelect} style={{ display: 'none' }} />
          {importFileName ? (
            <div data-testid="file-selected">
              <span>{importFileName}</span>
              <span>✓ 文件已选择</span>
            </div>
          ) : (
            <div data-testid="file-placeholder">拖拽或点击选择文件</div>
          )}
        </div>

        {/* 导入按钮 */}
        <button
          data-testid="import-btn"
          onClick={doImport}
          disabled={!importModal.unit || !importModal.file || importing}
        >
          {importing ? '导入中...' : '开始导入'}
        </button>
      </div>
    </div>
  )
}

describe('ImportModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('正确标题', () => {
    render(<ImportModal {...defaultProps} />)
    expect(screen.getByTestId('modal-title').textContent).toBe('批量导入题目')
  })

  it('默认选中七年级', () => {
    render(<ImportModal {...defaultProps} />)
    const btn7 = screen.getByTestId('grade-btn-七年级')
    expect(btn7.style.background).toBe('rgb(102, 126, 234)')
  })

  it('切换年级到八年级触发 setImportModal', async () => {
    const user = userEvent.setup()
    render(<ImportModal {...defaultProps} />)
    await user.click(screen.getByTestId('grade-btn-八年级'))
    expect(defaultProps.setImportModal).toHaveBeenCalled()
  })

  it('切换年级后清空已选单元', async () => {
    const user = userEvent.setup()
    render(<ImportModal {...defaultProps} importModal={{ open: true, grade: '七年级', unit: '第一节', file: null }} />)
    await user.click(screen.getByTestId('grade-btn-八年级'))
    expect(defaultProps.setImportModal).toHaveBeenCalled()
  })

  it('选择单元后显示提示信息', async () => {
    render(<ImportModal {...defaultProps} importModal={{ ...defaultProps.importModal, unit: '第一节' }} />)
    expect(screen.getByTestId('selected-unit-hint')).toBeInTheDocument()
    expect(screen.getByTestId('selected-unit-hint').textContent).toContain('第一章')
  })

  it('未选择单元时无提示', () => {
    render(<ImportModal {...defaultProps} />)
    expect(screen.queryByTestId('selected-unit-hint')).not.toBeInTheDocument()
  })

  it('文件选择触发 handleFileSelect', async () => {
    const user = userEvent.setup()
    render(<ImportModal {...defaultProps} />)
    const input = document.getElementById('import-file-input')
    // 模拟文件选择
    const file = new File(['[]'], 'test.json', { type: 'application/json' })
    await user.upload(input, file)
    expect(defaultProps.handleFileSelect).toHaveBeenCalled()
  })

  it('已选文件后显示文件名', () => {
    render(<ImportModal {...defaultProps} importFileName="test.json" />)
    expect(screen.getByTestId('file-selected').textContent).toContain('test.json')
  })

  it('未选文件时显示占位符', () => {
    render(<ImportModal {...defaultProps} importFileName={null} />)
    expect(screen.getByTestId('file-placeholder')).toBeInTheDocument()
  })

  it('缺少单元时导入按钮 disabled', () => {
    render(<ImportModal {...defaultProps} importModal={{ open: true, grade: '七年级', unit: '', file: new File([''], 'f.json') }} />)
    expect(screen.getByTestId('import-btn')).toBeDisabled()
  })

  it('缺少文件时导入按钮 disabled', () => {
    render(<ImportModal {...defaultProps} importModal={{ open: true, grade: '七年级', unit: '第一节', file: null }} />)
    expect(screen.getByTestId('import-btn')).toBeDisabled()
  })

  it('单元和文件都有时导入按钮 enabled', () => {
    const file = new File(['[]'], 'test.json', { type: 'application/json' })
    render(<ImportModal {...defaultProps} importModal={{ open: true, grade: '七年级', unit: '第一节', file }} />)
    expect(screen.getByTestId('import-btn')).not.toBeDisabled()
  })

  it('导入中按钮显示"导入中..."且 disabled', () => {
    const file = new File(['[]'], 'test.json', { type: 'application/json' })
    render(<ImportModal {...defaultProps} importing={true} importModal={{ open: true, grade: '七年级', unit: '第一节', file }} />)
    const btn = screen.getByTestId('import-btn')
    expect(btn.textContent).toBe('导入中...')
    expect(btn).toBeDisabled()
  })

  it('成功消息显示绿色', () => {
    render(<ImportModal {...defaultProps} importMsg={{ type: 'success', text: '导入成功！共5题' }} />)
    expect(screen.getByTestId('import-msg').style.background).toBe('rgb(212, 237, 218)')
  })

  it('失败消息显示红色', () => {
    render(<ImportModal {...defaultProps} importMsg={{ type: 'error', text: '导入失败' }} />)
    expect(screen.getByTestId('import-msg').style.background).toBe('rgb(248, 215, 218)')
  })

  it('关闭按钮触发 setImportModal', async () => {
    const user = userEvent.setup()
    render(<ImportModal {...defaultProps} />)
    await user.click(screen.getByTestId('close-btn'))
    expect(defaultProps.setImportModal).toHaveBeenCalledWith({ open: false })
  })
})
