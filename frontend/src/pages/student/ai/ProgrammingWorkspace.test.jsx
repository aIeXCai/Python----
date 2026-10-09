import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mocks = vi.hoisted(() => ({ detail: vi.fn(), active: vi.fn(), run: vi.fn(), submit: vi.fn(), poll: vi.fn(), context: vi.fn(), disabled: vi.fn() }))
vi.mock('@monaco-editor/react', () => ({ default: ({ value, onChange }) => <textarea aria-label="代码编辑器" value={value} onChange={event => onChange(event.target.value)} /> }))
vi.mock('../../../api/index.js', () => ({ pollExecutionTask: (...args) => mocks.poll(...args) }))
vi.mock('../../../api/aiStudentQuiz.js', () => ({
  getAIQuizProgrammingItem: (...args) => mocks.detail(...args), getAIQuizActiveExecution: (...args) => mocks.active(...args),
  runAIQuizCode: (...args) => mocks.run(...args), submitAIQuizCode: (...args) => mocks.submit(...args),
}))
vi.mock('../../../contexts/ChatContext.jsx', () => ({ useChat: () => ({ setContext: mocks.context, setDisabled: mocks.disabled }) }))

import ProgrammingWorkspace from './ProgrammingWorkspace.jsx'

describe('ProgrammingWorkspace Step 9', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.detail.mockResolvedValue({ title: '代码题', description: '请输出：\n```python\nprint("<ok>")\n```', template_code: 'print(1)', points: '40.0', best_score: null })
    mocks.active.mockResolvedValue(null)
    mocks.run.mockResolvedValue({ task_id: 'run-1', status: 'pending' })
    mocks.submit.mockResolvedValue({ task_id: 'grade-1', status: 'pending' })
    mocks.poll.mockImplementation(async taskId => taskId === 'run-1' ? { status: 'succeeded', output: '<ok>\n' } : { status: 'succeeded', score: 100 })
  })

  it('加载预制代码、支持重做，并安全显示编程题题干', async () => {
    const change = vi.fn(); const score = vi.fn()
    const { container } = render(<ProgrammingWorkspace sessionId="12" attemptId={91} item={{ item_id: 'p1', title: '代码题' }} draft={undefined} onDraftChange={change} onScore={score} />)
    expect(await screen.findByText('题目描述')).toBeInTheDocument()
    expect(change).toHaveBeenCalledWith('p1', 'print(1)')
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    expect(change).toHaveBeenLastCalledWith('p1', 'print(1)')
    expect(container.querySelector('.question-code-block code').textContent).toBe('print("<ok>")')
    expect(mocks.active).toHaveBeenCalledTimes(2)
  })

  it('没有预制代码时重做会清空编辑器', async () => {
    mocks.detail.mockResolvedValueOnce({ title: '空白代码题', description: '请完成代码', template_code: null, points: '40.0', best_score: null })
    const change = vi.fn()
    render(<ProgrammingWorkspace sessionId="12" attemptId={91} item={{ item_id: 'p2', title: '空白代码题' }} draft="print(2)" onDraftChange={change} onScore={vi.fn()} />)
    await screen.findByText('题目描述')
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    expect(change).toHaveBeenCalledWith('p2', '')
  })

  it('单一运行入口携带标准输入、显示输出并在后台记录成绩', async () => {
    const score = vi.fn()
    render(<ProgrammingWorkspace sessionId="12" attemptId={91} item={{ item_id: 'p1', title: '代码题' }} draft="print(input())" onDraftChange={vi.fn()} onScore={score} />)
    await screen.findByText('题目描述')
    expect(screen.queryByRole('button', { name: /提交评测/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/本次最高/)).not.toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText('每个输入值按题目要求换行'), { target: { value: 'abc' } })
    fireEvent.click(screen.getByRole('button', { name: /运行代码/ }))
    await waitFor(() => expect(mocks.run).toHaveBeenCalledWith('12', 'p1', 91, 'print(input())', 'abc'))
    expect(mocks.submit).toHaveBeenCalledWith('12', 'p1', 91, 'print(input())')
    expect(await screen.findByText('<ok>')).toBeInTheDocument()
    await waitFor(() => expect(score).toHaveBeenCalledWith('p1', 100))
    expect(screen.queryByText('100 分')).not.toBeInTheDocument()
    expect(screen.queryByText('全部测试点通过')).not.toBeInTheDocument()
  })
})
