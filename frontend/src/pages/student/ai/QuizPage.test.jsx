import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(), start: vi.fn(), save: vi.fn(), submit: vi.fn(),
  setContext: vi.fn(), setDisabled: vi.fn(), close: vi.fn(),
}))

vi.mock('react-router-dom', () => ({
  useParams: () => ({ sessionId: '12' }), useNavigate: () => mocks.navigate,
  Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
}))
vi.mock('../../../api/aiStudentQuiz.js', () => ({
  startAIQuizAttempt: (...args) => mocks.start(...args),
  saveAIQuizAnswers: (...args) => mocks.save(...args),
  submitAIQuizAttempt: (...args) => mocks.submit(...args),
}))
vi.mock('../../../contexts/ChatContext.jsx', () => ({
  useChat: () => ({ setContext: mocks.setContext, setDisabled: mocks.setDisabled, close: mocks.close }),
}))
vi.mock('../../../components/Navbar.jsx', () => ({ default: () => <div data-testid="navbar" /> }))
vi.mock('./ProgrammingWorkspace.jsx', () => ({ default: ({ item }) => <div>编程工作区：{item.title}</div> }))

import AIQuizPage from './QuizPage.jsx'

const attempt = {
  attempt_id: 91, revision: 2, server_time: new Date().toISOString(), deadline_at: null, remaining_seconds: null,
  saved_answers: {}, quiz: { id: 12, title: '代码阅读小测', choice_count: 1, programming_count: 1, total_points: '100.0' },
  items: [
    { item_id: 'choice-1', type: 'choice', position: 1, text: '运行代码：\n```python\nif x < 3:\n    print("<ok>")\n```', options: { A: '`print("<A>")`', B: '不输出', C: '报错', D: '无限循环' } },
    { item_id: 'program-1', type: 'programming', position: 2, title: '输入输出', points: '60.0' },
  ],
}

describe('AIQuizPage Step 9', () => {
  beforeEach(() => {
    vi.clearAllMocks(); localStorage.clear()
    localStorage.setItem('user', JSON.stringify({ display_name: '学生', grade: '七年级', class_num: '1' }))
    mocks.start.mockResolvedValue(attempt)
    mocks.save.mockResolvedValue({ revision: 3, saved_answers: { 'choice-1': 'A' } })
    mocks.submit.mockResolvedValue({ status: 'submitted' })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })
  afterEach(() => vi.restoreAllMocks())

  it('在题干和选项中安全、完整地显示代码', async () => {
    const { container } = render(<AIQuizPage />)
    expect(await screen.findByText('代码阅读小测')).toBeInTheDocument()
    const block = container.querySelector('.question-code-block code')
    expect(block.textContent).toBe('if x < 3:\n    print("<ok>")')
    expect(container.querySelector('.question-inline-code')).toHaveTextContent('print("<A>")')
    expect(container.querySelector('ok')).toBeNull()
    expect(container.querySelector('a')).not.toHaveTextContent('<A>')
  })

  it('保存展示字母并在换到编程题时重新启用助手', async () => {
    render(<AIQuizPage />)
    await screen.findByText('代码阅读小测')
    expect(mocks.setDisabled).toHaveBeenCalledWith(true, expect.stringContaining('选择题'))
    fireEvent.click(screen.getByRole('button', { name: /A.*print/ }))
    fireEvent.click(screen.getByRole('button', { name: /编程题.*尚未提交/ }))
    expect(await screen.findByText('编程工作区：输入输出')).toBeInTheDocument()
    expect(mocks.setDisabled).toHaveBeenCalledWith(false)
    window.dispatchEvent(new Event('pagehide'))
    await waitFor(() => expect(mocks.save).toHaveBeenCalled())
    expect(mocks.save.mock.calls[0][1].answers).toEqual({ 'choice-1': 'A' })
    expect(mocks.save.mock.calls[0][2]).toEqual({ keepalive: true })
  })

  it('交卷前同时提示未答选择题和未提交编程题', async () => {
    render(<AIQuizPage />)
    await screen.findByText('代码阅读小测')
    fireEvent.click(screen.getByRole('button', { name: '交卷' }))
    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/1 道选择题未答.*1 道编程题尚无有效提交/))
    await waitFor(() => expect(mocks.submit).toHaveBeenCalled())
    expect(mocks.navigate).toHaveBeenCalledWith('/student/ai-quiz-result/12', { replace: true })
  })

  it('上一题和下一题按钮使用相同宽度', async () => {
    render(<AIQuizPage />)
    await screen.findByText('代码阅读小测')

    const previous = screen.getByRole('button', { name: '上一题' })
    const next = screen.getByRole('button', { name: '下一题' })
    expect(previous.parentElement).toHaveClass('aiq-prev-next')
    expect(next.parentElement).toBe(previous.parentElement)
  })
})
