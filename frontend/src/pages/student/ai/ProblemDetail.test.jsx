/**
 * ProblemDetail AI课做题页面测试 (Monaco Editor IDE 版本)
 * 运行: cd frontend && npx vitest run src/pages/student/ai/ProblemDetail.test.jsx
 *
 * 验收标准:
 *  - Monaco Editor 正确渲染，Python 语法高亮
 *  - 运行纯输出代码 print("hello") → 输出区域显示 "hello"
 *  - 运行含 input() 代码 → 弹出 stdin 对话框 → 填入内容 → 输出正确
 *  - 运行死循环代码 → 10 秒后显示"执行超时"
 *  - 运行错误代码 → stderr 显示 NameError
 *  - 保存并提交正确代码 → 显示批改分数
 *  - 有模板的题目编辑器预填充模板内容；无模板则为空
 *  - 重做按钮：有模板 → 恢复模板；无模板 → 清空
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// ── Mock Monaco Editor ───────────────────────────────────────────────────
vi.mock('@monaco-editor/react', () => ({
  default: function MockEditor({ value, onChange, language, theme }) {
    return (
      <div data-testid="monaco-editor" data-language={language} data-theme={theme}>
        <textarea
          data-testid="monaco-textarea"
          value={value}
          onChange={(e) => onChange && onChange(e.target.value)}
        />
      </div>
    )
  },
}))

// ── Mock Navbar ──────────────────────────────────────────────────────────
vi.mock('../../../components/Navbar.jsx', () => ({
  default: function MockNavbar({ username, grade, class_num }) {
    return <div data-testid="navbar">{username} {grade} {class_num}</div>
  },
}))

// ── Mock ChatContext ─────────────────────────────────────────────────────
const mockSetContext = vi.fn()
vi.mock('../../../contexts/ChatContext.jsx', () => ({
  useChat: () => ({ setContext: mockSetContext }),
  ChatProvider: ({ children }) => children,
}))

// ── Mock lucide-react icons ──────────────────────────────────────────────
vi.mock('lucide-react', () => ({
  BookOpen: () => <span data-testid="icon-book">BookOpen</span>,
  Send: () => <span data-testid="icon-send">Send</span>,
  ArrowLeft: () => <span data-testid="icon-arrowleft">ArrowLeft</span>,
  Loader: () => <span data-testid="icon-loader">Loader</span>,
  CheckCircle: () => <span data-testid="icon-check">CheckCircle</span>,
  XCircle: () => <span data-testid="icon-x">XCircle</span>,
  Clock: () => <span data-testid="icon-clock">Clock</span>,
  Play: () => <span data-testid="icon-play">Play</span>,
  RotateCcw: () => <span data-testid="icon-rotateccw">RotateCcw</span>,
  ChevronDown: () => <span data-testid="icon-chevron-down">ChevronDown</span>,
  ChevronRight: () => <span data-testid="icon-chevron-right">ChevronRight</span>,
}))

// ── Mock react-router-dom ────────────────────────────────────────────────
const mockNavigate = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', () => ({
  useParams: () => ({ problemId: '456' }),
  useNavigate: () => mockNavigate,
  Link: ({ children, to }) => <a href={to}>{children}</a>,
}))

// ── Mock API ─────────────────────────────────────────────────────────────
const mockGetProblemDetail = vi.fn()
const mockGetSubmissionHistory = vi.fn()
const mockRunCode = vi.fn()
const mockSubmitCode = vi.fn()
const mockGetActiveExecutionTask = vi.fn()
const mockPollExecutionTask = vi.fn()

vi.mock('../../../api/index.js', () => ({
  getProblemDetail: (...args) => mockGetProblemDetail(...args),
  getSubmissionHistory: (...args) => mockGetSubmissionHistory(...args),
  runCode: (...args) => mockRunCode(...args),
  submitCode: (...args) => mockSubmitCode(...args),
  getActiveExecutionTask: (...args) => mockGetActiveExecutionTask(...args),
  pollExecutionTask: (...args) => mockPollExecutionTask(...args),
}))

// ── Mock localStorage ────────────────────────────────────────────────────
const localStorageMock = { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn() }
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

// ── Test fixtures ────────────────────────────────────────────────────────
const mockProblem = {
  id: '456',
  title: '两数之和',
  description: '给定一个整数数组 nums 和一个整数目标值 target，请返回这两个数的下标。',
  difficulty: '简单',
  test_cases: [
    { input: '2 7\n', output: '0 1' },
    { input: '3 2 4\n6', output: '0 1' },
  ],
}

const mockProblemWithTemplate = {
  ...mockProblem,
  template_code: 'def solve():\n    pass\n',
}

import ProblemDetail from './ProblemDetail.jsx'

beforeEach(() => {
  vi.clearAllMocks()
  mockGetActiveExecutionTask.mockResolvedValue(null)
  localStorage.getItem.mockReturnValue(JSON.stringify({
    display_name: '李四',
    grade: '七年级',
    class_num: '2',
  }))
})

describe('ProblemDetail (AI课做题页 - Monaco IDE)', () => {

  // ── 基础渲染 ────────────────────────────────────────────────────────────

  it('AC01: 加载中显示"加载题目中..."', () => {
    mockGetProblemDetail.mockImplementation(() => new Promise(() => {}))
    mockGetSubmissionHistory.mockImplementation(() => new Promise(() => {}))
    render(<ProblemDetail />)
    expect(screen.getByText('加载题目中...')).toBeInTheDocument()
  })

  it('AC02: 题目不存在时显示"题目不存在"', async () => {
    mockGetProblemDetail.mockResolvedValue(null)
    mockGetSubmissionHistory.mockResolvedValue([])
    render(<ProblemDetail />)
    await screen.findByText('题目不存在')
  })

  it('AC03: 显示题目描述', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    render(<ProblemDetail />)
    await screen.findByText(/给定一个整数数组/)
  })

  it('AC04: 显示难度标签', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    render(<ProblemDetail />)
    await screen.findByText('简单')
  })

  it('AC05: 显示测试点数量', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    render(<ProblemDetail />)
    const matches = await screen.findAllByText('2 个测试点')
    expect(matches.length).toBeGreaterThan(0)
  })

  // ── Monaco Editor 渲染 ──────────────────────────────────────────────────

  it('AC06: Monaco Editor 渲染，语言设为 Python', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    render(<ProblemDetail />)
    await screen.findByText('简单')
    const editor = screen.getByTestId('monaco-editor')
    expect(editor).toBeInTheDocument()
    expect(editor.dataset.language).toBe('python')
  })

  // ── 运行代码 ────────────────────────────────────────────────────────────

  it('AC07: 运行 print("hello") 显示 stdout 输出', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    mockRunCode.mockResolvedValue({ output: 'hello\n', error: '' })

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    // Type code into Monaco textarea
    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, 'print("hello")')

    // Click "运行" button
    await user.click(screen.getByRole('button', { name: /运行/ }))

    // Use getAllByText since textarea also contains "hello" from print("hello")
    const stdoutEls = screen.getAllByText(/hello/)
    // The <pre class="run-output-stdout"> has "hello\n"
    const stdoutPre = stdoutEls.find(el => el.tagName === 'PRE')
    expect(stdoutPre).toBeTruthy()
  })

  it('AC08: 运行含 input() 的代码弹出 stdin 对话框', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    // runCode won't be called directly — input dialog intercepts first
    mockRunCode.mockResolvedValue({ output: '你好，小明\n', error: '' })

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, "name = input('你的名字？'); print(f'你好，{name}')")

    // Click run — should open stdin dialog
    await user.click(screen.getByRole('button', { name: /运行/ }))

    // Stdin dialog should appear
    const dialog = await screen.findByText(/您的代码使用了 input/)
    expect(dialog).toBeInTheDocument()

    // Fill in stdin
    const stdinInput = screen.getByPlaceholderText('在此输入...')
    await user.type(stdinInput, '小明')

    // Click "运行" in the dialog
    const runButtons = screen.getAllByRole('button', { name: /运行/ })
    await user.click(runButtons[runButtons.length - 1])

    // Check mock was called with stdin
    await waitFor(() => {
      expect(mockRunCode).toHaveBeenCalledWith(
        expect.stringContaining("input('你的名字？')"),
        '小明'
      )
    })
  })

  it('AC09: stdin 对话框点取消后关闭不执行', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, "name = input()\nprint(name)")

    await user.click(screen.getByRole('button', { name: /运行/ }))
    await screen.findByText(/您的代码使用了 input/)

    // Click cancel
    await user.click(screen.getByText('取消'))

    // Dialog should be closed, runCode should NOT have been called
    await waitFor(() => {
      expect(screen.queryByText(/您的代码使用了 input/)).not.toBeInTheDocument()
    })
    expect(mockRunCode).not.toHaveBeenCalled()
  })

  it('AC10: 运行死循环代码显示超时错误', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    mockRunCode.mockResolvedValue({
      output: '',
      error: 'Execution timed out after 10 seconds',
    })

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, 'while True:\n    pass')

    await user.click(screen.getByRole('button', { name: /运行/ }))

    await screen.findByText(/Execution timed out after 10 seconds/)
  })

  it('AC11: 运行错误代码显示 NameError', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    mockRunCode.mockResolvedValue({
      output: '',
      error: "Traceback (most recent call last):\nNameError: name 'undefined_var' is not defined\n",
    })

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, 'print(undefined_var)')

    await user.click(screen.getByRole('button', { name: /运行/ }))

    await screen.findByText(/NameError/)
  })

  it('AC12: 运行过程中运行按钮显示"运行中..."并禁用', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    // Make runCode take some time
    mockRunCode.mockImplementation(() => new Promise(() => {}))

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, 'print("hi")')

    await user.click(screen.getByRole('button', { name: /运行/ }))

    // 创建请求未返回时，按钮显示排队阶段并禁用。
    const queuedButton = await screen.findByRole('button', { name: /排队中/ })
    expect(queuedButton).toBeDisabled()
  })

  // ── 保存并提交 ──────────────────────────────────────────────────────────

  it('AC13: 保存并提交正确代码显示批改分数', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])
    mockSubmitCode.mockResolvedValue({
      passed: true,
      score: 100,
      output: 'All test cases passed!',
    })

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    // userEvent v14 parses [ ] as keyboard modifiers; use escaped brackets [[ ]]
    await user.type(textarea, 'def two_sum(nums, target):\n    return [[0, 1]]')

    await user.click(screen.getByRole('button', { name: /保存并提交/ }))

    await screen.findByText('✅ 批改完成')
    const scoreEl = await screen.findByText('100')
    expect(scoreEl).toBeInTheDocument()
  })

  it('AC14: 提交失败显示"提交失败"', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])
    mockSubmitCode.mockResolvedValue({
      passed: false,
      score: 0,
      output: 'Wrong Answer: expected [0, 1] but got [0, 2]',
    })

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, 'print("wrong")')

    await user.click(screen.getByRole('button', { name: /保存并提交/ }))

    await screen.findByText('❌ 提交失败')
  })

  it('AC15: 提交后刷新历史记录', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        { id: 1, problem_id: '456', score: 100, submitted_at: '2026-04-24T10:00:00Z', status: 'accepted' },
      ])
    mockSubmitCode.mockResolvedValue({
      passed: true,
      score: 100,
      output: 'OK',
    })

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, 'print("ok")')

    await user.click(screen.getByRole('button', { name: /保存并提交/ }))

    // Text has emoji prefix: "📜 提交历史", need exact match
    await screen.findByText('📜 提交历史')
  })

  // ── 模板与重做 ──────────────────────────────────────────────────────────

  it('AC16: 有模板的题目编辑器预填充模板内容', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblemWithTemplate)
    mockGetSubmissionHistory.mockResolvedValue([])

    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    expect(textarea.value).toContain('def solve()')
    expect(textarea.value).toContain('pass')
  })

  it('AC17: 无模板的题目编辑器为空', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem) // no template_code
    mockGetSubmissionHistory.mockResolvedValue([])

    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    expect(textarea.value).toBe('')
  })

  it('AC18: 重做按钮 — 有模板时恢复模板内容', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblemWithTemplate)
    mockGetSubmissionHistory.mockResolvedValue([])

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    // Initially has template
    expect(textarea.value).toContain('def solve()')

    // User edits the code
    await user.clear(textarea)
    await user.type(textarea, 'print("my version")')
    expect(textarea.value).toContain('my version')

    // Click "重做" button
    await user.click(screen.getByRole('button', { name: /重做/ }))

    // Should restore to template
    await waitFor(() => {
      expect(textarea.value).toContain('def solve()')
      expect(textarea.value).toContain('pass')
    })
  })

  it('AC19: 重做按钮 — 无模板时清空编辑器', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    // Initially empty (no template)
    expect(textarea.value).toBe('')

    // User types code
    await user.clear(textarea)
    await user.type(textarea, 'print("hello")')
    expect(textarea.value).toContain('hello')

    // Click "重做" button
    await user.click(screen.getByRole('button', { name: /重做/ }))

    // Should be cleared
    await waitFor(() => {
      expect(textarea.value).toBe('')
    })
  })

  // ── 边界情况 ────────────────────────────────────────────────────────────

  it('AC20: 空代码时运行按钮禁用', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])

    render(<ProblemDetail />)
    await screen.findByText('简单')

    const runBtn = screen.getByRole('button', { name: /运行/ })
    expect(runBtn).toBeDisabled()
  })

  it('AC21: 空代码时提交按钮禁用', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])

    render(<ProblemDetail />)
    await screen.findByText('简单')

    const submitBtn = screen.getByRole('button', { name: /保存并提交/ })
    expect(submitBtn).toBeDisabled()
  })

  it('AC22: 运行按钮无禁用时点击触发 handleRun', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    mockRunCode.mockResolvedValue({ stdout: 'done\n', stderr: '', error: '' })

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, 'print("hi")')

    await user.click(screen.getByRole('button', { name: /运行/ }))

    await waitFor(() => {
      expect(mockRunCode).toHaveBeenCalledWith('print("hi")', '')
    })
  })

  it('AC23: runCode API reject 后显示错误信息', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    mockRunCode.mockRejectedValue(new Error('Network Error'))

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, 'print("hi")')

    await user.click(screen.getByRole('button', { name: /运行/ }))

    await screen.findByText('Network Error')
  })

  it('AC24: submitCode API reject 后显示错误', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    mockSubmitCode.mockRejectedValue(new Error('Server Error'))

    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')

    const textarea = screen.getByTestId('monaco-textarea')
    await user.clear(textarea)
    await user.type(textarea, 'print("hi")')

    await user.click(screen.getByRole('button', { name: /保存并提交/ }))

    await screen.findByText('❌ 提交失败')
    await screen.findByText('Server Error')
  })

  it('AC25: 无 test_cases 时不渲染测试点区域', async () => {
    const problemNoTC = { ...mockProblem, test_cases: undefined }
    mockGetProblemDetail.mockResolvedValue(problemNoTC)
    mockGetSubmissionHistory.mockResolvedValue([])

    render(<ProblemDetail />)
    await screen.findByText('简单')

    expect(screen.queryByText('测试点')).not.toBeInTheDocument()
  })

  it('AC26: 注册并注销 ChatContext', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])

    const { unmount } = render(<ProblemDetail />)
    await screen.findByText('简单')

    expect(mockSetContext).toHaveBeenCalledWith({
      type: 'ai_problem',
      id: '456',
      title: '两数之和',
      description: expect.any(String),
      last_error: '',
    })

    unmount()
    expect(mockSetContext).toHaveBeenCalledWith(null)
  })

  it('AC27: 异步运行先显示排队，完成后显示输出', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    mockRunCode.mockResolvedValue({ task_id: 'run-task-1', status: 'queued', poll_after_ms: 1 })
    mockPollExecutionTask.mockImplementation(async (_taskId, options) => {
      options.onUpdate({ task_id: 'run-task-1', status: 'running' })
      return { task_id: 'run-task-1', status: 'succeeded', output: 'async hello\n', error: '' }
    })
    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')
    const textarea = screen.getByTestId('monaco-textarea')
    await user.type(textarea, 'print("hello")')
    await user.click(screen.getByRole('button', { name: /运行/ }))
    await screen.findByText(/async hello/)
    expect(mockPollExecutionTask).toHaveBeenCalledWith(
      'run-task-1', expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('AC28: 异步评测完成后显示得分和错题正确输出', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    mockSubmitCode.mockResolvedValue({ task_id: 'grade-task-1', status: 'queued', poll_after_ms: 1 })
    mockPollExecutionTask.mockResolvedValue({
      task_id: 'grade-task-1', status: 'wrong_answer', score: 50,
      detail: { tests: [{
        number: 2, status: 'wrong_answer', expected_output: '4', actual_output: '3', stderr: '',
      }] },
    })
    const user = userEvent.setup()
    render(<ProblemDetail />)
    await screen.findByText('简单')
    await user.type(screen.getByTestId('monaco-textarea'), 'print(3)')
    await user.click(screen.getByRole('button', { name: /保存并提交/ }))
    await screen.findByText('50')
    await screen.findByText(/正确输出：4/)
    await screen.findByText(/你的输出：3/)
  })

  it('AC29: 刷新页面时恢复本题未完成评测', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    mockGetActiveExecutionTask.mockImplementation(({ taskType }) => (
      taskType === 'grade'
        ? Promise.resolve({ task_id: 'restored-grade', status: 'running', poll_after_ms: 1 })
        : Promise.resolve(null)
    ))
    mockPollExecutionTask.mockResolvedValue({
      task_id: 'restored-grade', status: 'succeeded', score: 100, detail: { tests: [] },
    })
    render(<ProblemDetail />)
    await screen.findByText('100')
    expect(mockPollExecutionTask).toHaveBeenCalledWith(
      'restored-grade', expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('AC30: 页面卸载时取消正在轮询的任务', async () => {
    mockGetProblemDetail.mockResolvedValue(mockProblem)
    mockGetSubmissionHistory.mockResolvedValue([])
    mockGetActiveExecutionTask.mockImplementation(({ taskType }) => (
      taskType === 'run'
        ? Promise.resolve({ task_id: 'restored-run', status: 'queued', poll_after_ms: 1 })
        : Promise.resolve(null)
    ))
    let receivedSignal
    mockPollExecutionTask.mockImplementation((_taskId, options) => {
      receivedSignal = options.signal
      return new Promise(() => {})
    })
    const { unmount } = render(<ProblemDetail />)
    await waitFor(() => expect(receivedSignal).toBeDefined())
    unmount()
    expect(receivedSignal.aborted).toBe(true)
  })
})
