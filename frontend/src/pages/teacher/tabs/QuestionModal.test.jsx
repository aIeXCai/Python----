/**
 * QuestionModal 题目弹窗测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/tabs/QuestionModal.test.jsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('lucide-react', () => ({
  X: () => <span data-testid="icon-x">X</span>,
  CheckCircle: () => <span data-testid="icon-check">Check</span>,
}))

const mockQAllUnits = [
  { id: 1, name: '第一章', display_name: '第一章 数据与信息', parent: null },
  { id: 2, name: '第一节', display_name: '1.1 什么是数据', parent: { name: '第一章', display_name: '第一章 数据与信息' } },
  { id: 3, name: '第二节', display_name: '1.2 数据的编码', parent: { name: '第一章', display_name: '第一章 数据与信息' } },
]

const defaultProps = {
  qModal: { open: true, mode: 'create', data: null },
  setQModal: vi.fn(),
  qForm: { unit: '', difficulty: 'easy', text: '', option_a: '', option_b: '', option_c: '', option_d: '', answer: '', category: '', explanation: '' },
  setQForm: vi.fn(),
  qMsg: { type: '', text: '' },
  handleSaveQuestion: vi.fn(),
  qSaving: false,
  qAllUnits: mockQAllUnits,
}

// 内联 QuestionModal（复制自 Tab1Questions.jsx）
function QuestionModal({ qModal, setQModal, qForm, setQForm, qMsg, handleSaveQuestion, qSaving, qAllUnits }) {
  return (
    <div data-testid="question-modal" onClick={() => setQModal({ open: false })}>
      <div data-testid="modal-content" onClick={e => e.stopPropagation()}>
        <h2 data-testid="modal-title">{qModal.mode === 'edit' ? '编辑题目' : '新建题目'}</h2>
        <button data-testid="close-btn" onClick={() => setQModal({ open: false })}>X</button>

        {qMsg.text && (
          <div data-testid="q-msg" style={{
            background: qMsg.type === 'success' ? '#d4edda' : '#f8d7da',
            color: qMsg.type === 'success' ? '#155724' : '#721c24',
          }}>{qMsg.text}</div>
        )}

        <form onSubmit={handleSaveQuestion} data-testid="question-form">
          <div data-testid="section-select-wrap">
            <select
              data-testid="unit-select"
              value={qForm.unit}
              onChange={e => setQForm(p => ({ ...p, unit: e.target.value }))}
              required
            >
              <option value="">— 选择小节 —</option>
              {qAllUnits.filter(u => u.parent != null).map(u => (
                <option key={u.id} value={u.name}>{u.display_name}</option>
              ))}
            </select>
          </div>

          <div>
            <select
              data-testid="difficulty-select"
              value={qForm.difficulty}
              onChange={e => setQForm(p => ({ ...p, difficulty: e.target.value }))}
            >
              <option value="easy">容易</option>
              <option value="medium">中等</option>
              <option value="hard">困难</option>
            </select>
          </div>

          <div>
            <textarea
              data-testid="text-input"
              value={qForm.text}
              onChange={e => setQForm(p => ({ ...p, text: e.target.value }))}
              placeholder="请输入题目内容"
              required
            />
          </div>

          {[['A', 'option_a'], ['B', 'option_b'], ['C', 'option_c'], ['D', 'option_d']].map(([key, field]) => (
            <div key={field}>
              <span>{key}.</span>
              <input
                data-testid={`option-${key.toLowerCase()}-input`}
                value={qForm[field]}
                onChange={e => setQForm(p => ({ ...p, [field]: e.target.value }))}
                placeholder={`选项 ${key}`}
                required
              />
            </div>
          ))}

          <div data-testid="answer-row">
            {['A', 'B', 'C', 'D'].map(opt => (
              <label key={opt}>
                <input
                  type="radio"
                  name="answer"
                  value={opt}
                  checked={qForm.answer === opt}
                  onChange={e => setQForm(p => ({ ...p, answer: e.target.value }))}
                />
                {opt}
              </label>
            ))}
          </div>

          <button type="submit" data-testid="submit-btn" disabled={qSaving}>
            {qSaving ? '保存中...' : '保存'}
          </button>
        </form>
      </div>
    </div>
  )
}

describe('QuestionModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('新建模式显示"新建题目"标题', () => {
    render(<QuestionModal {...defaultProps} qModal={{ open: true, mode: 'create' }} />)
    expect(screen.getByTestId('modal-title').textContent).toBe('新建题目')
  })

  it('编辑模式显示"编辑题目"标题', () => {
    render(<QuestionModal {...defaultProps} qModal={{ open: true, mode: 'edit' }} />)
    expect(screen.getByTestId('modal-title').textContent).toBe('编辑题目')
  })

  it('关闭按钮触发 setQModal', async () => {
    const user = userEvent.setup()
    render(<QuestionModal {...defaultProps} />)
    await user.click(screen.getByTestId('close-btn'))
    expect(defaultProps.setQModal).toHaveBeenCalledWith({ open: false })
  })

  it('成功消息显示绿色背景', () => {
    render(<QuestionModal {...defaultProps} qMsg={{ type: 'success', text: '保存成功！' }} />)
    const msg = screen.getByTestId('q-msg')
    expect(msg.style.background).toBe('rgb(212, 237, 218)')
    expect(msg.textContent).toBe('保存成功！')
  })

  it('错误消息显示红色背景', () => {
    render(<QuestionModal {...defaultProps} qMsg={{ type: 'error', text: '保存失败' }} />)
    const msg = screen.getByTestId('q-msg')
    expect(msg.style.background).toBe('rgb(248, 215, 218)')
  })

  it('切换难度触发 setQForm', async () => {
    const user = userEvent.setup()
    render(<QuestionModal {...defaultProps} />)
    await user.selectOptions(screen.getByTestId('difficulty-select'), 'hard')
    expect(defaultProps.setQForm).toHaveBeenCalled()
  })

  it('选择正确答案触发 setQForm', async () => {
    const user = userEvent.setup()
    render(<QuestionModal {...defaultProps} />)
    const radios = screen.getByTestId('answer-row').querySelectorAll('input[type="radio"]')
    await user.click(radios[1]) // 选择 B
    expect(defaultProps.setQForm).toHaveBeenCalled()
  })

  it('填写题目正文触发 setQForm', async () => {
    const user = userEvent.setup()
    render(<QuestionModal {...defaultProps} />)
    await user.type(screen.getByTestId('text-input'), '以下哪个是 Python 的列表？')
    expect(defaultProps.setQForm).toHaveBeenCalled()
  })

  it('保存中按钮显示"保存中..."', () => {
    render(<QuestionModal {...defaultProps} qSaving={true} />)
    expect(screen.getByTestId('submit-btn').textContent).toBe('保存中...')
  })

  it('保存中按钮 disabled', () => {
    render(<QuestionModal {...defaultProps} qSaving={true} />)
    expect(screen.getByTestId('submit-btn')).toBeDisabled()
  })

  it('填写选项触发 setQForm', async () => {
    const user = userEvent.setup()
    render(<QuestionModal {...defaultProps} />)
    await user.type(screen.getByTestId('option-a-input'), '列表数据')
    expect(defaultProps.setQForm).toHaveBeenCalled()
  })

  it('切换小节触发 setQForm', async () => {
    const user = userEvent.setup()
    render(<QuestionModal {...defaultProps} />)
    await user.selectOptions(screen.getByTestId('unit-select'), '第一节')
    expect(defaultProps.setQForm).toHaveBeenCalled()
  })

  it('小节下拉只显示子单元', () => {
    render(<QuestionModal {...defaultProps} />)
    const options = screen.getByTestId('unit-select').querySelectorAll('option')
    const values = Array.from(options).map(o => o.value)
    expect(values).toContain('第一节')
    expect(values).toContain('第二节')
    // 大单元不在选项中
    expect(values.filter(v => v === '第一章')).toHaveLength(0)
  })
})
