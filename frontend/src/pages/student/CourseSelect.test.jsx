import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CourseSelect from './CourseSelect.jsx'
import { typingApi } from '../../api/typing.js'
import { getMyPoints, getPointsLeaderboard, getMyPointsLedger } from '../../api/points.js'

vi.mock('../../api/typing.js', () => ({ typingApi: { bests: vi.fn() } }))
vi.mock('../../api/points.js', () => ({
  getMyPoints: vi.fn(),
  getPointsLeaderboard: vi.fn(),
  getMyPointsLedger: vi.fn(),
}))

// Mock Navbar — must be before component import
vi.mock('../../components/Navbar.jsx', () => ({ default: () => <div data-testid="navbar">Mock Navbar</div> }))

// Mock lucide-react icons（含称号徽章、积分条与风云榜用到的图标）
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
  RefreshCw: () => <span aria-hidden="true" />,
  Check: () => <span aria-hidden="true" />,
  Lock: () => <span aria-hidden="true" />,
  X: () => <span aria-hidden="true" />,
  ChevronRight: () => <span aria-hidden="true" />,
  Receipt: () => <span aria-hidden="true" />,
  Coins: () => <span aria-hidden="true" />,
  Gift: () => <span aria-hidden="true" />,
  Loader2: () => <span aria-hidden="true" />,
  RotateCcw: () => <span aria-hidden="true" />,
  SlidersHorizontal: () => <span aria-hidden="true" />,
  Target: () => <span aria-hidden="true" />,
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
    getPointsLeaderboard.mockReset().mockResolvedValue({
      me: { student_id: 9, rank: 3 },
      entries: [
        {
          student_id: 1, label: '王雨桐', points: '546.2', typing_points: '328.0', quiz_points: '218.2',
          rank: 1, self: false,
          title: { name: '南山执剑', color: '#a855f7', icon: 'sword', path: { label: '双修', color: '#8b5cf6' } },
        },
        {
          student_id: 9, label: '张三', points: '208.7', typing_points: '116.0', quiz_points: '92.7',
          rank: 3, self: true,
          title: { name: '格物修士', color: '#60a5fa', icon: 'compass', path: { label: '疾风', color: '#f97316' } },
        },
      ],
    })
    getMyPointsLedger.mockReset().mockResolvedValue({
      entries: [
        {
          id: 12, delta: '24.5', balance_after: '208.7', reason: 'typing_attempt',
          reason_label: '打字练习', note: '', time: '11-25 15:02',
        },
      ],
      has_more: false,
      next_before: null,
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

  // ── 积分卡：与仪表盘同一套组件，一登录就能看到积分 ──
  it('登录后直接显示积分、称号与班级排名', async () => {
    localStorage.setItem('token', 'test-token')
    renderAsUser()
    const card = await screen.findByLabelText('我的积分')
    expect(card.classList.contains('points-hero')).toBe(true)
    expect(card.querySelector('.points-hero-value').textContent).toContain('208.7')
    expect(within(card).getByText('格物修士')).toBeTruthy()
    expect(within(card).getByText(/第 3 名/)).toBeTruthy()
    expect(within(card).getByText(/共 40 人/)).toBeTruthy()
    expect(within(card).getByText(/距 南山执剑 还差 91.3 分/)).toBeTruthy()
  })

  it('点积分卡上的称号可以打开进阶天梯', async () => {
    localStorage.setItem('token', 'test-token')
    getMyPoints.mockResolvedValue({
      balance: '208.7', earned_total: '208.7', spent_total: '0.0',
      rank: 3, class_size: 40, typing_total: '116.0', quiz_total: '92.7',
      title: {
        name: '格物修士', color: '#60a5fa', icon: 'compass', level: 2,
        path: { label: '疾风', color: '#f97316' },
        next: { name: '南山执剑', remaining: '91.3' },
      },
      ladder: [
        { level: 1, name: '蒙学童生', threshold: '0', reached: true, current: false, was_reached: false },
        { level: 2, name: '格物学徒', threshold: '50', reached: true, current: true, was_reached: false },
        { level: 3, name: '格物修士', threshold: '150', reached: false, current: false, was_reached: false },
      ],
      paths: [],
    })
    renderAsUser()
    const card = await screen.findByLabelText('我的积分')
    fireEvent.click(within(card).getByLabelText('查看进阶天梯'))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getAllByText(/格物修士/).length).toBeGreaterThan(0)
  })

  it('积分接口不可用时积分卡显示占位，选课入口照常可用', async () => {
    localStorage.setItem('token', 'test-token')
    getMyPoints.mockRejectedValue(new Error('网络错误'))
    renderAsUser()
    expect(await screen.findByText('人工智能课')).toBeTruthy()
    const card = screen.getByLabelText('我的积分')
    expect(within(card).getByText('—')).toBeTruthy()
    expect(screen.getByRole('link', { name: '打字训练' })).toBeTruthy()
  })

  // ── 班级风云榜：一登录就能看到本班排名 ──
  it('首页直接显示班级风云榜，并标出本人', async () => {
    localStorage.setItem('token', 'test-token')
    renderAsUser()
    const board = await screen.findByLabelText('班级风云榜')
    expect(within(board).getByText('王雨桐')).toBeTruthy()
    expect(within(board).getByText('546.2')).toBeTruthy()
    expect(within(board).getByText('张三')).toBeTruthy()
    expect(within(board).getByText('我')).toBeTruthy()
    expect(within(board).getByText(/我目前第 3 名/)).toBeTruthy()
  })

  it('风云榜与课程卡片分列左右两栏，积分卡横跨上方', async () => {
    localStorage.setItem('token', 'test-token')
    renderAsUser()
    await screen.findByLabelText('班级风云榜')
    const main = document.querySelector('.select-layout .select-main')
    const aside = document.querySelector('.select-layout .select-aside')
    expect(main.querySelector('.course-card-grid')).toBeTruthy()
    expect(aside.querySelector('.points-board')).toBeTruthy()
    const card = document.querySelector('.points-hero')
    expect(card).toBeTruthy()
    expect(card.closest('.select-layout')).toBeNull()
  })

  it('风云榜接口失败时不影响选课与积分卡', async () => {
    localStorage.setItem('token', 'test-token')
    getPointsLeaderboard.mockRejectedValue(new Error('网络错误'))
    renderAsUser()
    expect(await screen.findByLabelText('我的积分')).toBeTruthy()
    const board = await screen.findByLabelText('班级风云榜')
    expect(within(board).getByText(/还没有人获得积分/)).toBeTruthy()
    expect(screen.getByRole('link', { name: '人工智能课' })).toBeTruthy()
  })

  // ── 积分明细：顶部积分栏的按钮点开流水 ──
  it('顶部积分栏有「积分明细」按钮，点开显示流水', async () => {
    localStorage.setItem('token', 'test-token')
    renderAsUser()
    const card = await screen.findByLabelText('我的积分')
    fireEvent.click(within(card).getByRole('button', { name: /积分明细/ }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('积分明细')).toBeTruthy()
    expect(await within(dialog).findByText('打字练习')).toBeTruthy()
    expect(within(dialog).getByText('+24.5')).toBeTruthy()
    expect(getMyPointsLedger).toHaveBeenCalledTimes(1)
  })

  it('积分明细弹窗关闭后不再占据页面', async () => {
    localStorage.setItem('token', 'test-token')
    renderAsUser()
    const card = await screen.findByLabelText('我的积分')
    fireEvent.click(within(card).getByRole('button', { name: /积分明细/ }))
    await screen.findByRole('dialog')

    fireEvent.click(screen.getByRole('button', { name: /关闭积分明细/ }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('积分明细接口失败时弹窗给出错误提示，不影响选课', async () => {
    localStorage.setItem('token', 'test-token')
    getMyPointsLedger.mockRejectedValue(new Error('请求失败（500）'))
    renderAsUser()
    const card = await screen.findByLabelText('我的积分')
    fireEvent.click(within(card).getByRole('button', { name: /积分明细/ }))

    const dialog = await screen.findByRole('dialog')
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('请求失败（500）')
    expect(screen.getByRole('link', { name: '打字训练' })).toBeTruthy()
  })
})
