import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CourseSelect from './CourseSelect.jsx'
import { typingApi } from '../../api/typing.js'

vi.mock('../../api/typing.js', () => ({ typingApi: { bests: vi.fn() } }))

// Mock Navbar — must be before component import
vi.mock('../../components/Navbar.jsx', () => ({ default: () => <div data-testid="navbar">Mock Navbar</div> }))

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Keyboard: () => <span aria-hidden="true" />,
  Brain: () => <span data-testid="brain-icon">Brain</span>,
  Monitor: () => <span data-testid="monitor-icon">Monitor</span>,
}))

describe('CourseSelect.jsx', () => {
  beforeEach(() => {
    localStorage.clear()
    typingApi.bests.mockReset().mockResolvedValue({ zh: null, en: null })
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
    const alexTexts = screen.getAllByText(/授课教师：Alex/)
    expect(alexTexts.length).toBe(2)
  })

  it('opens typing training from the welcome screen', () => {
    renderAsUser()
    expect(screen.getByRole('link', { name: '打字训练' }).getAttribute('href')).toBe('/student/typing')
  })

  it('uses the same linked card layout for all entries', () => {
    renderAsUser()
    for (const name of ['人工智能课', '信息科技课', '打字训练']) {
      expect(screen.getByRole('link', { name }).classList.contains('course-card')).toBe(true)
    }
  })

  it('reads each language separately and keeps zero as a valid best', async () => {
    localStorage.setItem('token', 'test-token')
    typingApi.bests.mockResolvedValue({ zh: null, en: '0.0' })
    renderAsUser()
    const card = within(screen.getByRole('link', { name: '打字训练' }))
    expect(await card.findByText('0.0 分')).toBeTruthy()
    expect(card.getByText('暂无成绩')).toBeTruthy()
    expect(card.getByText('中文最佳成绩').nextElementSibling.textContent).toBe('暂无成绩')
    expect(card.getByText('英文最佳成绩').nextElementSibling.textContent).toBe('0.0 分')
  })
})
