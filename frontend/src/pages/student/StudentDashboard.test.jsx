import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import * as apiIndex from '../../api/index.js'
import * as apiInfo from '../../api/info.js'
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
    await waitFor(() => expect(screen.getByText(/准备好挑战今天的题目了吗/)).toBeInTheDocument())
  })

  it('renders practice problems section heading (AI mode)', async () => {
    renderDashboard()
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(/练习题目/)
    })
  })

  it('shows empty state when no problems', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.getByText('暂无题目')).toBeInTheDocument())
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
