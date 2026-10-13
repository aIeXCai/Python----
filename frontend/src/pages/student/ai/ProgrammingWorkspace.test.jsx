import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mocks = vi.hoisted(() => ({ detail: vi.fn(), prepare: vi.fn(), run: vi.fn(), grade: vi.fn(), context: vi.fn(), disabled: vi.fn() }))
vi.mock('@monaco-editor/react', () => ({ default: ({ value, onChange }) => <textarea aria-label="代码编辑器" value={value} onChange={event => onChange(event.target.value)} /> }))
vi.mock('../../../api/aiStudentQuiz.js', () => ({ getAIQuizProgrammingItem: (...args) => mocks.detail(...args) }))
vi.mock('./localPython.js', () => ({
  prepareLocalPython: (...args) => mocks.prepare(...args),
  runLocalPython: (...args) => mocks.run(...args),
  gradeLocalPython: (...args) => mocks.grade(...args),
}))
vi.mock('../../../contexts/ChatContext.jsx', () => ({ useChat: () => ({ setContext: mocks.context, setDisabled: mocks.disabled }) }))

import ProgrammingWorkspace from './ProgrammingWorkspace.jsx'

describe('ProgrammingWorkspace local execution', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.detail.mockResolvedValue({ title: '代码题', description: '请输出：\n```python\nprint("<ok>")\n```', template_code: 'print(1)', points: '40.0', test_cases: [{ number: 1, input: '', output: '<ok>\n' }] })
    mocks.prepare.mockResolvedValue(undefined)
    mocks.run.mockResolvedValue({ status: 'succeeded', output: '<ok>\n', error: '' })
    mocks.grade.mockResolvedValue({ score: 100, passed: 1, total: 1 })
  })

  it('加载预制代码并安全显示题干', async () => {
    const change = vi.fn()
    const { container } = render(<ProgrammingWorkspace sessionId="12" item={{ item_id: 'p1', title: '代码题' }} draft={undefined} onDraftChange={change} />)
    expect(await screen.findByText('题目描述')).toBeInTheDocument()
    expect(change).toHaveBeenCalledWith('p1', 'print(1)')
    fireEvent.click(screen.getByRole('button', { name: '重做' }))
    expect(change).toHaveBeenLastCalledWith('p1', 'print(1)')
    expect(container.querySelector('.question-code-block code').textContent).toBe('print("<ok>")')
  })

  it('运行和评分都在本机完成', async () => {
    render(<ProgrammingWorkspace sessionId="12" item={{ item_id: 'p1', title: '代码题' }} draft="print(input())" onDraftChange={vi.fn()} />)
    await screen.findByText('题目描述')
    fireEvent.change(screen.getByPlaceholderText('每个输入值按题目要求换行'), { target: { value: 'abc' } })
    fireEvent.click(screen.getByRole('button', { name: /运行代码/ }))
    await waitFor(() => expect(mocks.run).toHaveBeenCalledWith('print(input())', 'abc'))
    expect(mocks.grade).toHaveBeenCalledWith('print(input())', [{ number: 1, input: '', output: '<ok>\n' }])
    expect(await screen.findByText(/参考分 100/)).toBeInTheDocument()
  })
})
