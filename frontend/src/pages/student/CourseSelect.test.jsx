import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CourseSelect from './CourseSelect.jsx'

// Mock Navbar — must be before component import
vi.mock('../../components/Navbar.jsx', () => ({ default: () => <div data-testid="navbar">Mock Navbar</div> }))

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Brain: () => <span data-testid="brain-icon">Brain</span>,
  Monitor: () => <span data-testid="monitor-icon">Monitor</span>,
}))

describe('CourseSelect.jsx', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  // Helper to render with user in localStorage
  const renderAsUser = (username = '张三') => {
    localStorage.setItem('user', JSON.stringify({ display_name: username, grade: '七年级', class_num: '1' }))
    return render(<MemoryRouter><CourseSelect /></MemoryRouter>)
  }

  // ── 正常渲染 ──
  it('renders welcome message with username', () => {
    renderAsUser()
    expect(screen.getByText(/欢迎回来.*张三/)).toBeTruthy()
  })

  it('renders 请选择你要进入的课程 text', () => {
    renderAsUser()
    expect(screen.getByText('请选择你要进入的课程')).toBeTruthy()
  })

  it('renders Navbar', () => {
    renderAsUser()
    expect(screen.getByTestId('navbar')).toBeTruthy()
  })

  // ── 课程卡片 ──
  it('renders AI course card with Brain icon', () => {
    renderAsUser()
    expect(screen.getByText('人工智能课')).toBeTruthy()
    expect(screen.getByTestId('brain-icon')).toBeTruthy()
  })

  it('renders Info course card with Monitor icon', () => {
    renderAsUser()
    expect(screen.getByText('信息科技课')).toBeTruthy()
    expect(screen.getByTestId('monitor-icon')).toBeTruthy()
  })

  it('renders both course cards', () => {
    renderAsUser()
    expect(screen.getByText('人工智能课')).toBeTruthy()
    expect(screen.getByText('信息科技课')).toBeTruthy()
  })

  it('shows Alex as teacher on both cards', () => {
    renderAsUser()
    const alexTexts = screen.getAllByText(/授课老师：Alex/)
    expect(alexTexts.length).toBe(2)
  })

  // ── 课程卡片悬停样式 ──
  it('has hover style for course cards', () => {
    renderAsUser()
    const style = document.querySelector('style')
    expect(style.textContent).toContain('.course-card:hover')
  })

  // ── 课程点击导航 ──
  it('has two course cards that are clickable', () => {
    renderAsUser()
    const cards = screen.getAllByText(/授课老师：Alex/)
    expect(cards.length).toBe(2)
  })
})
