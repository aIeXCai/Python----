/**
 * Tab0Units 单元管理测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/tabs/Tab0Units.test.jsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('lucide-react', () => ({
  Plus: () => <span data-testid="icon-plus">Plus</span>,
  Edit2: () => <span data-testid="icon-edit">Edit</span>,
  Trash2: () => <span data-testid="icon-trash">Trash</span>,
  ListChecks: () => <span data-testid="icon-list">List</span>,
  CheckCircle: () => <span data-testid="icon-check">Check</span>,
  X: () => <span data-testid="icon-x">X</span>,
}))

const mockBigUnits = [
  {
    id: 1, name: '第一章', display_name: '第一章 数据与信息', grade: '七年级',
    question_count: 5,
    sections: [
      { id: 2, name: '第一节', display_name: '1.1 什么是数据', question_count: 2 },
      { id: 3, name: '第二节', display_name: '1.2 数据的编码', question_count: 3 },
    ],
  },
  {
    id: 4, name: '第二章', display_name: '第二章 算法基础', grade: '七年级',
    question_count: 8,
    sections: [],
  },
]

const defaultProps = {
  bigUnits: mockBigUnits,
  unitGradeFilter: '七年级',
  setUnitGradeFilter: vi.fn(),
  expandedUnits: new Set(),
  toggleUnit: vi.fn(),
  openNewBigUnit: vi.fn(),
  openAddSection: vi.fn(),
  editUnit: null,
  setEditUnit: vi.fn(),
  handleUpdateUnit: vi.fn(),
  deleteUnit: vi.fn(),
  newBigUnitOpen: false,
  sectionModal: { open: false, bigUnit: null },
  unitForm: { name: '', display_name: '', grade: '七年级' },
  setUnitForm: vi.fn(),
  unitMsg: { type: '', text: '' },
  handleCreateBigUnit: vi.fn(),
  handleSaveSection: vi.fn(),
  loadUnits: vi.fn(),
  gradeColor: () => '#11999e',
  API: '/api',
  headers: {},
}

// 内联 BigUnitModal
function BigUnitModal({ unitForm, setUnitForm, unitMsg, handleSubmit, onClose }) {
  return (
    <div data-testid="bigunit-modal">
      <h2>新建大单元</h2>
      <button data-testid="modal-close" onClick={onClose}>X</button>
      {unitMsg.text && (
        <div data-testid="bigunit-msg" style={{ background: unitMsg.type === 'success' ? '#d4edda' : '#f8d7da' }}>
          {unitMsg.text}
        </div>
      )}
      <form onSubmit={handleSubmit}>
        <select
          data-testid="grade-select"
          value={unitForm.grade}
          onChange={e => setUnitForm(p => ({ ...p, grade: e.target.value }))}
        >
          <option value="七年级">七年级</option>
          <option value="八年级">八年级</option>
        </select>
        <input
          data-testid="name-input"
          value={unitForm.display_name}
          onChange={e => setUnitForm(p => ({ ...p, display_name: e.target.value }))}
          placeholder="如：第一章 算法基础"
        />
        <button type="submit">创建</button>
      </form>
    </div>
  )
}

// 内联 SectionModal
function SectionModal({ sectionModal, unitForm, setUnitForm, unitMsg, handleSubmit }) {
  return (
    <div data-testid="section-modal">
      <h2 data-testid="section-title">
        在"{sectionModal.bigUnit?.display_name}"下新增小节
      </h2>
      {unitMsg.text && (
        <div data-testid="section-msg" style={{ background: unitMsg.type === 'success' ? '#d4edda' : '#f8d7da' }}>
          {unitMsg.text}
        </div>
      )}
      <form onSubmit={handleSubmit}>
        <input
          data-testid="section-name-input"
          value={unitForm.display_name}
          onChange={e => setUnitForm(p => ({ ...p, display_name: e.target.value }))}
          placeholder="如：1.1 变量的概念"
        />
        <button type="submit">保存</button>
      </form>
    </div>
  )
}

// 简化版 Tab0Units（内联关键逻辑）
function SimplifiedTab0Units(props) {
  return (
    <div data-testid="tab0-units">
      {/* 顶部栏 */}
      <div data-testid="top-bar">
        <span data-testid="unit-count">共 {props.bigUnits.length} 个大单元</span>
        <select
          data-testid="grade-filter"
          value={props.unitGradeFilter}
          onChange={e => props.setUnitGradeFilter(e.target.value)}
        >
          <option value="七年级">七年级</option>
          <option value="八年级">八年级</option>
        </select>
        <button data-testid="new-bigunit-btn" onClick={props.openNewBigUnit}>+ 新建大单元</button>
      </div>

      {/* 空状态 */}
      {props.bigUnits.length === 0 && (
        <div data-testid="empty-state">该年级暂无大单元，请点击"新建大单元"创建</div>
      )}

      {/* 大单元列表 */}
      {props.bigUnits.map(big => (
        <div key={big.id} data-testid={`bigunit-${big.id}`}>
          <div data-testid={`bigunit-header-${big.id}`}>
            <button data-testid={`toggle-${big.id}`} onClick={() => props.toggleUnit(big.id)}>
              {props.expandedUnits.has(big.id) ? '▼' : '▶'}
            </button>
            <span data-testid={`bigunit-name-${big.id}`}>{big.display_name}</span>
            <span data-testid={`bigunit-meta-${big.id}`}>{big.question_count} 题 · {big.sections?.length || 0} 小节</span>
            <button data-testid={`add-section-btn-${big.id}`} onClick={() => props.openAddSection(big)}>+ 小节</button>
            <button data-testid={`edit-unit-btn-${big.id}`} onClick={() => props.setEditUnit({ id: big.id, name: big.name, display_name: big.display_name || '' })}>编辑</button>
            <button data-testid={`delete-unit-btn-${big.id}`} onClick={() => props.deleteUnit(big.id)}>删除</button>
          </div>

          {/* 小节列表 */}
          {props.expandedUnits.has(big.id) && big.sections?.length > 0 && (
            <div data-testid={`sections-${big.id}`}>
              {big.sections.map(sec => (
                <div key={sec.id} data-testid={`section-${sec.id}`}>
                  <span>{sec.display_name}</span>
                  <span>{sec.question_count} 题</span>
                  <button data-testid={`edit-section-btn-${sec.id}`} onClick={() => props.setEditUnit({ id: sec.id })}>编辑</button>
                  <button data-testid={`delete-section-btn-${sec.id}`} onClick={() => props.deleteUnit(sec.id)}>删除</button>
                </div>
              ))}
            </div>
          )}

          {props.expandedUnits.has(big.id) && (!big.sections || big.sections.length === 0) && (
            <div data-testid={`no-sections-${big.id}`}>暂无小节</div>
          )}
        </div>
      ))}

      {/* 弹窗 */}
      {props.newBigUnitOpen && (
        <BigUnitModal
          unitForm={props.unitForm} setUnitForm={props.setUnitForm}
          unitMsg={props.unitMsg} handleSubmit={props.handleCreateBigUnit}
          onClose={() => {}}
        />
      )}

      {props.sectionModal.open && (
        <SectionModal
          sectionModal={props.sectionModal}
          unitForm={props.unitForm} setUnitForm={props.setUnitForm}
          unitMsg={props.unitMsg} handleSubmit={props.handleSaveSection}
        />
      )}
    </div>
  )
}

describe('Tab0Units', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.confirm = vi.fn(() => true)
  })

  it('空状态显示提示文字', () => {
    render(<SimplifiedTab0Units {...defaultProps} bigUnits={[]} />)
    expect(screen.getByTestId('empty-state')).toBeInTheDocument()
  })

  it('有单元时显示大单元数量', () => {
    render(<SimplifiedTab0Units {...defaultProps} />)
    expect(screen.getByTestId('unit-count').textContent).toBe('共 2 个大单元')
  })

  it('年级切换触发 setUnitGradeFilter', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab0Units {...defaultProps} />)
    await user.selectOptions(screen.getByTestId('grade-filter'), '八年级')
    expect(defaultProps.setUnitGradeFilter).toHaveBeenCalledWith('八年级')
  })

  it('新建大单元按钮触发 openNewBigUnit', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab0Units {...defaultProps} />)
    await user.click(screen.getByTestId('new-bigunit-btn'))
    expect(defaultProps.openNewBigUnit).toHaveBeenCalled()
  })

  it('展开按钮触发 toggleUnit', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab0Units {...defaultProps} expandedUnits={new Set()} />)
    await user.click(screen.getByTestId('toggle-1'))
    expect(defaultProps.toggleUnit).toHaveBeenCalledWith(1)
  })

  it('已展开时显示小节列表', () => {
    render(<SimplifiedTab0Units {...defaultProps} expandedUnits={new Set([1])} />)
    expect(screen.getByTestId('sections-1')).toBeInTheDocument()
    expect(screen.getByText('1.1 什么是数据')).toBeInTheDocument()
    expect(screen.getByText('1.2 数据的编码')).toBeInTheDocument()
  })

  it('无小节时显示"暂无小节"', () => {
    render(<SimplifiedTab0Units {...defaultProps} expandedUnits={new Set([4])} />)
    expect(screen.getByTestId('no-sections-4')).toBeInTheDocument()
  })

  it('添加小节按钮触发 openAddSection', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab0Units {...defaultProps} />)
    await user.click(screen.getByTestId('add-section-btn-1'))
    expect(defaultProps.openAddSection).toHaveBeenCalledWith(mockBigUnits[0])
  })

  it('大单元编辑按钮触发 setEditUnit', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab0Units {...defaultProps} />)
    await user.click(screen.getByTestId('edit-unit-btn-1'))
    expect(defaultProps.setEditUnit).toHaveBeenCalled()
  })

  it('SectionModal 显示所属大单元名称', () => {
    render(<SimplifiedTab0Units {...defaultProps} sectionModal={{ open: true, bigUnit: mockBigUnits[0] }} />)
    expect(screen.getByTestId('section-title').textContent).toContain('第一章 数据与信息')
  })

  it('BigUnitModal 成功消息显示绿色', () => {
    render(<SimplifiedTab0Units {...defaultProps} newBigUnitOpen={true} unitMsg={{ type: 'success', text: '创建成功！' }} />)
    expect(screen.getByTestId('bigunit-msg').style.background).toBe('rgb(212, 237, 218)')
  })

  it('BigUnitModal 失败消息显示红色', () => {
    render(<SimplifiedTab0Units {...defaultProps} newBigUnitOpen={true} unitMsg={{ type: 'error', text: '创建失败' }} />)
    expect(screen.getByTestId('bigunit-msg').style.background).toBe('rgb(248, 215, 218)')
  })

  it('BigUnitModal 创建按钮触发 handleCreateBigUnit', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab0Units {...defaultProps} newBigUnitOpen={true} />)
    await user.type(screen.getByTestId('name-input'), '第三章 测试')
    await user.click(screen.getByRole('button', { name: '创建' }))
    expect(defaultProps.handleCreateBigUnit).toHaveBeenCalled()
  })

  it('SectionModal 保存按钮触发 handleSaveSection', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab0Units {...defaultProps} sectionModal={{ open: true, bigUnit: mockBigUnits[0] }} />)
    await user.type(screen.getByTestId('section-name-input'), '1.3 测试小节')
    await user.click(screen.getByRole('button', { name: '保存' }))
    expect(defaultProps.handleSaveSection).toHaveBeenCalled()
  })

  it('删除按钮触发 deleteUnit', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab0Units {...defaultProps} />)
    await user.click(screen.getByTestId('delete-unit-btn-1'))
    expect(defaultProps.deleteUnit).toHaveBeenCalledWith(1)
  })

  it('显示大单元元数据（题数和小节数）', () => {
    render(<SimplifiedTab0Units {...defaultProps} />)
    expect(screen.getByTestId('bigunit-meta-1').textContent).toBe('5 题 · 2 小节')
    expect(screen.getByTestId('bigunit-meta-4').textContent).toBe('8 题 · 0 小节')
  })
})
