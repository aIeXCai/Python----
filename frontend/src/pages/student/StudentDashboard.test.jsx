import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import * as apiIndex from '../../api/index.js'
import * as apiInfo from '../../api/info.js'
import * as aiQuizApi from '../../api/aiStudentQuiz.js'
import StudentDashboard from './StudentDashboard.jsx'
import AuthContext from '../../contexts/AuthContext.jsx'

const navigateFn = vi.hoisted(() => vi.fn())
const searchParamsState = vi.hoisted(() => ({ course: null }))
const logoutFn = vi.fn()

vi.mock('../../components/Navbar.jsx', () => ({
  default: ({ username }) => (
    <div data-testid="navbar">
      <div data-testid="navbar-user">{username}</div>
      <button data-testid="logout-btn" onClick={() => { logoutFn(); navigateFn('/login') }}>登出</button>
    </div>
  ),
}))

vi.mock('../../contexts/ChatContext.jsx', () => ({
  useChat: () => ({ setContext: vi.fn() }),
  ChatProvider: ({ children }) => children,
}))

vi.mock('./ai/FreePracticeWorkspace.jsx', () => ({
  default: () => <div data-testid="free-practice-workspace">自由练习工作区</div>,
}))

vi.mock('react-router-dom', () => {
  const Link = ({ to, children }) => <a href={to}>{children}</a>
  const fakeSearchParams = { get: (key) => key === 'course' ? searchParamsState.course : null, [Symbol.iterator]: function* () {} }
  return {
    useNavigate: () => navigateFn,
    useSearchParams: () => [fakeSearchParams, vi.fn()],
    Link,
    MemoryRouter: ({ children }) => children,
  }
})

describe('StudentDashboard.jsx', () => {
  beforeEach(() => {
    navigateFn.mockReset()
    searchParamsState.course = null
    logoutFn.mockReset().mockImplementation(() => localStorage.removeItem('user'))
    localStorage.clear()
    localStorage.setItem('user', JSON.stringify({ display_name: '张三', grade: '七年级', class_num: '1' }))
    vi.spyOn(apiIndex, 'getProblems').mockResolvedValue([])
    vi.spyOn(apiIndex, 'getScores').mockResolvedValue([])
    vi.spyOn(apiIndex, 'getStudentStats').mockResolvedValue({
      total_problems: 10, completed_problems: 3, average_score: 82.5, rank: 5,
    })
    vi.spyOn(apiInfo, 'getInfoQuizzes').mockResolvedValue([])
    vi.spyOn(aiQuizApi, 'getStudentAIQuizzes').mockResolvedValue([])
  })

  const renderDashboard = () =>
    render(<MemoryRouter><StudentDashboard /></MemoryRouter>)

  it('renders Navbar', () => {
    renderDashboard()
    expect(screen.getByTestId('navbar')).toBeInTheDocument()
  })

  it('renders welcome message with username', () => {
    renderDashboard()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/张三/)
  })

  it('renders stats cards with correct labels', async () => {
    renderDashboard()
    await waitFor(() => {
      expect(screen.getByText('总题目数')).toBeInTheDocument()
      expect(screen.getByText('已完成题目')).toBeInTheDocument()
      expect(screen.getByText('平均成绩')).toBeInTheDocument()
      expect(screen.getByText('班级排名')).toBeInTheDocument()
    })
  })

  it('renders AI course badge by default (no course param)', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.getByText('人工智能课')).toBeInTheDocument())
  })

  it('renders AI course prompt text by default', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.getByText(/先完成老师发布的小测/)).toBeInTheDocument())
  })

  it('默认显示小测 Tab，并可在三个 AI 学习 Tab 间切换', async () => {
    renderDashboard()
    const quizTab = await screen.findByRole('tab', { name: '我的小测' })
    const practiceTab = screen.getByRole('tab', { name: '题库练习' })
    const freePracticeTab = screen.getByRole('tab', { name: '自由练习' })
    expect(quizTab).toHaveAttribute('aria-selected', 'true')
    expect(practiceTab).toHaveAttribute('aria-selected', 'false')
    expect(freePracticeTab).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByRole('heading', { level: 2, name: '我的小测' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '🔄 切换课程' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 2, name: '题库练习' })).not.toBeInTheDocument()

    fireEvent.click(practiceTab)
    expect(practiceTab).toHaveAttribute('aria-selected', 'true')
    expect(quizTab).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByRole('heading', { level: 2, name: '题库练习' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 2, name: '我的小测' })).not.toBeInTheDocument()

    fireEvent.click(freePracticeTab)
    expect(freePracticeTab).toHaveAttribute('aria-selected', 'true')
    expect(quizTab).toHaveAttribute('aria-selected', 'false')
    expect(practiceTab).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByTestId('free-practice-workspace')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 2, name: '题库练习' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 2, name: '我的小测' })).not.toBeInTheDocument()
  })

  it('信息科技课不显示自由练习 Tab', async () => {
    searchParamsState.course = 'info'
    renderDashboard()

    expect(await screen.findByText('信息科技课')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: '自由练习' })).not.toBeInTheDocument()
  })

  it('shows empty state when no problems', async () => {
    renderDashboard()
    fireEvent.click(await screen.findByRole('tab', { name: '题库练习' }))
    await waitFor(() => expect(screen.getByText('暂无题目')).toBeInTheDocument())
  })

  it('将 AI 正式小测和题库练习按 Tab 隔离展示', async () => {
    aiQuizApi.getStudentAIQuizzes.mockResolvedValue([{
      id: 18, title: '人工智能单元测试', choice_count: 3, programming_count: 2,
      time_limit: 45, action: 'continue', latest_score: null, best_score: null,
    }])
    renderDashboard()
    expect(await screen.findByRole('heading', { name: '我的小测' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '题库练习' })).not.toBeInTheDocument()
    expect(screen.getByText('人工智能单元测试')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '继续作答' })).toHaveAttribute('href', '/student/ai-quiz/18')

    fireEvent.click(screen.getByRole('tab', { name: '题库练习' }))
    expect(screen.getByRole('heading', { name: '题库练习' })).toBeInTheDocument()
    expect(screen.queryByText('人工智能单元测试')).not.toBeInTheDocument()
  })

  it('AI 小测完成后同时提供查看结果和再次作答入口', async () => {
    aiQuizApi.getStudentAIQuizzes.mockResolvedValue([{
      id: 19, title: 'AI 已完成小测', choice_count: 4, programming_count: 1,
      time_limit: 30, action: 'result', latest_score: 86, best_score: 92,
    }])

    renderDashboard()

    expect(await screen.findByText('AI 已完成小测')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看结果' })).toHaveAttribute('href', '/student/ai-quiz-result/19')
    expect(screen.getByRole('link', { name: '再做一次' })).toHaveAttribute('href', '/student/ai-quiz/19')
  })

  it('在题库练习中按单元和难度筛选', async () => {
    apiIndex.getProblems.mockResolvedValue([
      { problem_id: 'p1', title: '顺序简单题', unit_name: '输入输出', difficulty: 'easy' },
      { problem_id: 'p2', title: '循环难题', unit_name: '循环', difficulty: 'hard' },
    ])
    renderDashboard()
    fireEvent.click(await screen.findByRole('tab', { name: '题库练习' }))
    await screen.findByText('顺序简单题')
    fireEvent.change(screen.getByRole('combobox', { name: '练习单元筛选' }), { target: { value: '循环' } })
    fireEvent.change(screen.getByRole('combobox', { name: '练习难度筛选' }), { target: { value: 'hard' } })
    expect(screen.queryByText('顺序简单题')).not.toBeInTheDocument()
    expect(screen.getByText('循环难题')).toBeInTheDocument()
  })

  it('keeps legacy practice completion at full score', async () => {
    apiIndex.getProblems.mockResolvedValue([
      { problem_id: 'p80', title: '部分通过题' },
      { problem_id: 'p100', title: '满分题' },
    ])
    apiIndex.getScores.mockResolvedValue([
      { problem_id: 'p80', best_score: 80, status: 'attempted' },
      { problem_id: 'p100', best_score: 100, status: 'completed' },
    ])

    renderDashboard()

    fireEvent.click(await screen.findByRole('tab', { name: '题库练习' }))

    const partialCard = (await screen.findByText('部分通过题')).closest('.problem-card')
    const completedCard = screen.getByText('满分题').closest('.problem-card')
    expect(partialCard).toHaveTextContent('作答中')
    expect(completedCard).toHaveTextContent('已通过')
  })

  it('logout button clears localStorage and navigates to /login', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.getByText('人工智能课')).toBeInTheDocument())
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /登出/ }))
    expect(localStorage.getItem('user')).toBeNull()
    expect(navigateFn).toHaveBeenCalledWith('/login')
  })

  it('shows latest score and both result/retry actions for a completed open quiz', async () => {
    searchParamsState.course = 'info'
    apiInfo.getInfoQuizzes.mockResolvedValue([{
      id: 7,
      title: '循环小测',
      num_questions: 5,
      time_limit: 20,
      action: 'restart',
      score: 80,
      best_score: 80,
      submitted: true,
      unit_names: ['循环结构'],
    }])

    renderDashboard()

    expect(await screen.findByText('80分')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看成绩' })).toHaveAttribute('href', '/student/quiz-result/7')
    expect(screen.getByRole('link', { name: '再做一次' })).toHaveAttribute('href', '/student/quiz/7')
  })
})
