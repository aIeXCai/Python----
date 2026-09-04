/**
 * TeacherDashboard 老师仪表盘测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/TeacherDashboard.test.jsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Users: () => <span data-testid="icon-users">Users</span>,
  BookOpen: () => <span data-testid="icon-book">BookOpen</span>,
  BarChart3: () => <span data-testid="icon-chart">BarChart3</span>,
  Upload: () => <span data-testid="icon-upload">Upload</span>,
  LogOut: () => <span data-testid="icon-logout">LogOut</span>,
  Bot: () => <span data-testid="icon-bot">Bot</span>,
  ChevronRight: () => <span data-testid="icon-chevron">ChevronRight</span>,
  GraduationCap: () => <span data-testid="icon-graduation">GraduationCap</span>,
  ListChecks: () => <span data-testid="icon-list">ListChecks</span>,
}))

// Mock react-router-dom
const mockNavigate = vi.fn()
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}))

// Mock AuthContext
const mockLogout = vi.fn()
vi.mock('../../contexts/AuthContext.jsx', () => ({
  useAuth: () => ({ logout: mockLogout }),
}))

// Mock API
const mockGetAdminDashboard = vi.fn()
vi.mock('../../api/index.js', () => ({
  getAdminDashboard: (...args) => mockGetAdminDashboard(...args),
}))

import TeacherDashboard from './TeacherDashboard.jsx'

const mockDashboardData = {
  total_students: 120,
  total_problems: 45,
  today_submissions: 38,
  avg_score: 82.5,
}

describe('TeacherDashboard (老师仪表盘)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetAdminDashboard.mockResolvedValue(mockDashboardData)
  })

  it('显示"老师管理后台"标题', async () => {
    render(<TeacherDashboard />)
    await screen.findByText('教师管理后台')
  })

  it('显示学生总数统计卡片', async () => {
    render(<TeacherDashboard />)
    await screen.findByText('学生总数')
    await screen.findByText('120')
  })

  it('显示题目总数统计卡片', async () => {
    render(<TeacherDashboard />)
    await screen.findByText('题目总数')
    await screen.findByText('45')
  })

  it('显示今日提交统计卡片', async () => {
    render(<TeacherDashboard />)
    await screen.findByText('今日提交')
    await screen.findByText('38')
  })

  it('显示平均成绩（带百分号）', async () => {
    render(<TeacherDashboard />)
    await screen.findByText('平均成绩')
    await screen.findByText('82.5%')
  })

  it('avg_score为0时显示"—"', async () => {
    mockGetAdminDashboard.mockResolvedValue({
      total_students: 0,
      total_problems: 0,
      today_submissions: 0,
      avg_score: 0,
    })
    render(<TeacherDashboard />)
    await screen.findByText('—')
  })

  it('显示AI课管理卡片', async () => {
    render(<TeacherDashboard />)
    await screen.findByText('AI课管理')
    await screen.findByText('题库·成绩统计')
  })

  it('显示信息课管理卡片', async () => {
    render(<TeacherDashboard />)
    await screen.findByText('信息课管理')
    await screen.findByText('题库·小测·成绩统计')
  })

  it('显示学生管理卡片', async () => {
    render(<TeacherDashboard />)
    await screen.findByText('学生管理')
    await screen.findByText('管理学生帐号')
  })

  it('点击AI课管理卡片跳转到/teacher/ai', async () => {
    const user = userEvent.setup()
    render(<TeacherDashboard />)
    await screen.findByText('AI课管理')
    // 找到包含"AI课管理"的按钮
    const cards = screen.getAllByText('AI课管理')
    await user.click(cards[0])
  })

  it('点击信息课管理卡片跳转到/teacher/info', async () => {
    const user = userEvent.setup()
    render(<TeacherDashboard />)
    await screen.findByText('信息课管理')
    const cards = screen.getAllByText('信息课管理')
    await user.click(cards[0])
  })

  it('点击学生管理卡片跳转到/teacher/students', async () => {
    const user = userEvent.setup()
    render(<TeacherDashboard />)
    await screen.findByText('学生管理')
    const cards = screen.getAllByText('学生管理')
    await user.click(cards[0])
  })

  it('显示退出按钮', async () => {
    render(<TeacherDashboard />)
    await screen.findByText('退出')
  })

  it('点击退出按钮调用logout并跳转到/teacher-login', async () => {
    const user = userEvent.setup()
    render(<TeacherDashboard />)
    await user.click(screen.getByText('退出'))
    expect(mockLogout).toHaveBeenCalled()
    expect(mockNavigate).toHaveBeenCalledWith('/teacher-login')
  })

  it('显示"老师账号"标签', async () => {
    render(<TeacherDashboard />)
    await screen.findByText('教师账号')
  })
})
