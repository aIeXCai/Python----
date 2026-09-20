import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FreePracticeWorkspace from './FreePracticeWorkspace.jsx'

const mocks = vi.hoisted(() => ({
  runCode: vi.fn(),
  pollExecutionTask: vi.fn(),
  setContext: vi.fn(),
}))

vi.mock('@monaco-editor/react', () => ({
  default: ({ value, onChange, options }) => (
    <textarea
      aria-label={options.ariaLabel}
      value={value}
      onChange={event => onChange(event.target.value)}
    />
  ),
}))

vi.mock('../../../api/index.js', () => ({
  runCode: mocks.runCode,
  pollExecutionTask: mocks.pollExecutionTask,
}))

vi.mock('../../../contexts/ChatContext.jsx', () => ({
  useChat: () => ({ setContext: mocks.setContext }),
}))

describe('FreePracticeWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.runCode.mockResolvedValue({ output: 'hello\n', error: '' })
  })

  it('只展示自由编程所需控件，空代码时不能运行', () => {
    render(<FreePracticeWorkspace />)

    expect(screen.getByRole('textbox', { name: 'Python 代码编辑器' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '运行代码' })).toBeDisabled()
    expect(screen.queryByText('题目描述')).not.toBeInTheDocument()
    expect(screen.queryByText('提交评测')).not.toBeInTheDocument()
    expect(screen.queryByText(/分$/)).not.toBeInTheDocument()
  })

  it('直接运行不含 input() 的代码并展示同步兼容结果', async () => {
    const user = userEvent.setup()
    render(<FreePracticeWorkspace />)

    await user.type(screen.getByRole('textbox', { name: 'Python 代码编辑器' }), 'print("hello")')
    await user.click(screen.getByRole('button', { name: '运行代码' }))

    await waitFor(() => expect(mocks.runCode).toHaveBeenCalledWith('print("hello")', ''))
    expect(await screen.findByText('hello')).toBeInTheDocument()
  })

  it('轮询异步执行任务并展示最终输出', async () => {
    mocks.runCode.mockResolvedValue({ task_id: 'task-1', status: 'queued', poll_after_ms: 1 })
    mocks.pollExecutionTask.mockImplementation(async (_taskId, options) => {
      options.onUpdate({ status: 'running' })
      return { status: 'succeeded', output: 'done\n', error: '' }
    })
    const user = userEvent.setup()
    render(<FreePracticeWorkspace />)

    await user.type(screen.getByRole('textbox', { name: 'Python 代码编辑器' }), 'print("done")')
    await user.click(screen.getByRole('button', { name: '运行代码' }))

    await waitFor(() => expect(mocks.pollExecutionTask).toHaveBeenCalledWith('task-1', expect.objectContaining({
      initialDelay: 1,
      signal: expect.any(AbortSignal),
      onUpdate: expect.any(Function),
    })))
    expect(await screen.findByText('done')).toBeInTheDocument()
  })

  it('正在创建或执行任务时禁用运行按钮，避免重复提交', async () => {
    let resolveRun
    mocks.runCode.mockImplementation(() => new Promise(resolve => { resolveRun = resolve }))
    const user = userEvent.setup()
    render(<FreePracticeWorkspace />)

    await user.type(screen.getByRole('textbox', { name: 'Python 代码编辑器' }), 'print(1)')
    await user.click(screen.getByRole('button', { name: '运行代码' }))

    const runningButton = screen.getByRole('button', { name: '排队中…' })
    expect(runningButton).toBeDisabled()
    fireEvent.click(runningButton)
    expect(mocks.runCode).toHaveBeenCalledTimes(1)

    resolveRun({ status: 'succeeded', output: '1\n', error: '' })
    expect(await screen.findByText('1')).toBeInTheDocument()
  })

  it('含 input() 时先弹窗，提交多行输入后再运行', async () => {
    const user = userEvent.setup()
    render(<FreePracticeWorkspace />)
    const editor = screen.getByRole('textbox', { name: 'Python 代码编辑器' })

    fireEvent.change(editor, { target: { value: 'name = input()\nage = input()\nprint(name, age)' } })
    await user.click(screen.getByRole('button', { name: '运行代码' }))

    expect(screen.getByRole('dialog', { name: '📥 输入' })).toBeInTheDocument()
    expect(mocks.runCode).not.toHaveBeenCalled()

    await user.type(screen.getByPlaceholderText('在此输入...'), '小明{enter}14')
    await user.click(screen.getByRole('button', { name: '运行' }))

    await waitFor(() => expect(mocks.runCode).toHaveBeenCalledWith(
      'name = input()\nage = input()\nprint(name, age)',
      '小明\n14',
    ))
  })

  it('取消输入弹窗时不执行代码', async () => {
    const user = userEvent.setup()
    render(<FreePracticeWorkspace />)

    fireEvent.change(screen.getByRole('textbox', { name: 'Python 代码编辑器' }), { target: { value: 'print(input())' } })
    await user.click(screen.getByRole('button', { name: '运行代码' }))
    await user.type(screen.getByPlaceholderText('在此输入...'), 'abc')
    await user.click(screen.getByRole('button', { name: '取消' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mocks.runCode).not.toHaveBeenCalled()
  })

  it('展示无输出、运行错误和请求异常', async () => {
    const user = userEvent.setup()
    render(<FreePracticeWorkspace />)
    const editor = screen.getByRole('textbox', { name: 'Python 代码编辑器' })

    mocks.runCode.mockResolvedValueOnce({ status: 'succeeded', output: '', error: '' })
    fireEvent.change(editor, { target: { value: 'x = 1' } })
    await user.click(screen.getByRole('button', { name: '运行代码' }))
    expect(await screen.findByText('（无输出）')).toBeInTheDocument()

    mocks.runCode.mockResolvedValueOnce({ status: 'runtime_error', output: '', error: 'NameError' })
    await user.click(screen.getByRole('button', { name: '运行代码' }))
    expect(await screen.findByText('NameError')).toBeInTheDocument()

    mocks.runCode.mockRejectedValueOnce(new Error('网络异常'))
    await user.click(screen.getByRole('button', { name: '运行代码' }))
    expect(await screen.findByText('网络异常')).toBeInTheDocument()
  })

  it('代码变化时实时更新小 P 上下文，卸载时清理', async () => {
    const { unmount } = render(<FreePracticeWorkspace />)
    expect(mocks.setContext).toHaveBeenCalledWith({
      type: 'ai_free_practice', title: '自由练习', code: '',
    })

    fireEvent.change(screen.getByRole('textbox', { name: 'Python 代码编辑器' }), {
      target: { value: 'for i in range(3):\n    print(i)' },
    })
    await waitFor(() => expect(mocks.setContext).toHaveBeenLastCalledWith({
      type: 'ai_free_practice',
      title: '自由练习',
      code: 'for i in range(3):\n    print(i)',
    }))

    unmount()
    expect(mocks.setContext).toHaveBeenLastCalledWith(null)
  })
})
