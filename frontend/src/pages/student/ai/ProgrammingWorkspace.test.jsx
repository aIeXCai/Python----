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

  it('恢复模板与活跃任务，并安全显示编程题题干', async () => {
    const change = vi.fn(); const score = vi.fn()
    const { container } = render(<ProgrammingWorkspace sessionId="12" attemptId={91} item={{ item_id: 'p1', title: '代码题' }} draft={undefined} onDraftChange={change} onScore={score} />)
    expect(await screen.findByText('题目描述')).toBeInTheDocument()
    expect(change).toHaveBeenCalledWith('p1', 'print(1)')
    expect(container.querySelector('.question-code-block code').textContent).toBe('print("<ok>")')
    expect(mocks.active).toHaveBeenCalledTimes(2)
  })

  it('运行代码携带标准输入，正式提交后更新本次最高分', async () => {
    const score = vi.fn()
    render(<ProgrammingWorkspace sessionId="12" attemptId={91} item={{ item_id: 'p1', title: '代码题' }} draft="print(input())" onDraftChange={vi.fn()} onScore={score} />)
    await screen.findByText('题目描述')
    fireEvent.change(screen.getByPlaceholderText('每个输入值按题目要求换行'), { target: { value: 'abc' } })
    fireEvent.click(screen.getByRole('button', { name: /运行代码/ }))
    await waitFor(() => expect(mocks.run).toHaveBeenCalledWith('12', 'p1', 91, 'print(input())', 'abc'))
    expect(await screen.findByText('<ok>')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /提交评测/ }))
    await waitFor(() => expect(score).toHaveBeenCalledWith('p1', 100))
    expect(screen.getByText(/本次最高：100分/)).toBeInTheDocument()
  })
})
