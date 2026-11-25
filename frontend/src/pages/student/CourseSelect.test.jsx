import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CourseSelect from './CourseSelect.jsx'
import { typingApi } from '../../api/typing.js'
import { getMyPoints } from '../../api/points.js'

vi.mock('../../api/typing.js', () => ({ typingApi: { bests: vi.fn() } }))
vi.mock('../../api/points.js', () => ({ getMyPoints: vi.fn() }))

// Mock Navbar — must be before component import
vi.mock('../../components/Navbar.jsx', () => ({ default: () => <div data-testid="navbar">Mock Navbar</div> }))

// Mock lucide-react icons（含称号徽章与积分条用到的图标）
vi.mock('lucide-react', () => ({
  Keyboard: () => <span aria-hidden="true" />,
  Brain: () => <span data-testid="brain-icon">Brain</span>,
  Monitor: () => <span data-testid="monitor-icon">Monitor</span>,
  Sparkles: () => <span aria-hidden="true" />,
  Trophy: () => <span aria-hidden="true" />,
  Star: () => <span aria-hidden="true" />,
  Compass: () => <span aria-hidden="true" />,
  Crown: () => <span aria-hidden="true" />,
  Flame: () => <span aria-hidden="true" />,
  Gem: () => <span aria-hidden="true" />,
  Sword: () => <span aria-hidden="true" />,
  Wand2: () => <span aria-hidden="true" />,
}))

describe('CourseSelect.jsx', () => {
  beforeEach(() => {
    localStorage.clear()
    typingApi.bests.mockReset().mockResolvedValue({ zh: null, en: null })
    getMyPoints.mockReset().mockResolvedValue({
      balance: '208.7', earned_total: '208.7', spent_total: '0.0',
      rank: 3, class_size: 40, typing_total: '116.0', quiz_total: '92.7',
      title: {
        name: '格物修士', color: '#60a5fa', icon: 'compass',
        path: { label: '疾风', color: '#f97316' },
        next: { name: '南山执剑', remaining: '91.3' },
      },
      ladder: [], paths: [],
    })
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

  // ── 积分条：一登录就能看到积分 ──
  it('登录后直接显示积分、称号与班级排名', async () => {
    localStorage.setItem('token', 'test-token')
    renderAsUser()
    const strip = await screen.findByLabelText('我的积分')
    expect(within(strip).getByText('208.7')).toBeTruthy()
    expect(within(strip).getByText('格物修士')).toBeTruthy()
    expect(within(strip).getByText(/班级第 3 名/)).toBeTruthy()
    expect(within(strip).getByText(/共 40 人/)).toBeTruthy()
    expect(within(strip).getByText(/距 南山执剑 还差 91.3 分/)).toBeTruthy()
  })

  it('积分接口不可用时不显示积分条，选课入口照常可用', async () => {
    localStorage.setItem('token', 'test-token')
    getMyPoints.mockRejectedValue(new Error('网络错误'))
    renderAsUser()
    expect(await screen.findByText('人工智能课')).toBeTruthy()
    expect(screen.queryByLabelText('我的积分')).toBeNull()
    expect(screen.getByRole('link', { name: '打字训练' })).toBeTruthy()
  })
})
