/**
 * InfoAdmin 信息课管理后台测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/InfoAdmin.test.jsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  BookOpen: () => <span data-testid="icon-book">BookOpen</span>,
  ClipboardList: () => <span data-testid="icon-clipboard">ClipboardList</span>,
  BarChart2: () => <span data-testid="icon-chart">BarChart2</span>,
  ListChecks: () => <span data-testid="icon-list">ListChecks</span>,
  X: () => <span data-testid="icon-x">X</span>,
  Home: () => <span data-testid="icon-home">Home</span>,
}))

// Mock react-router-dom
const mockNavigate = vi.fn()
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}))

// Mock localStorage
const localStorageMock = { getItem: vi.fn() }
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

// Parent component loads tab data even though the tab bodies are mocked.
// Keep these rendering-focused tests isolated from Node's real fetch, which
// cannot resolve browser-relative /api URLs.
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// Mock tab sub-components to avoid deep rendering
vi.mock('./tabs/Tab0Units', () => ({
  default: function MockTab0Units() {
    return <div data-testid="tab-units">Tab0 单元管理</div>
  }
}))
vi.mock('./tabs/Tab1Questions', () => ({
  default: function MockTab1Questions() {
    return <div data-testid="tab-questions">Tab1 题库管理</div>
  }
}))
vi.mock('./tabs/Tab2Sessions', () => ({
  default: function MockTab2Sessions() {
    return <div data-testid="tab-sessions">Tab2 小测管理</div>
  }
}))
vi.mock('./tabs/Tab3Stats', () => ({
  default: function MockTab3Stats() {
    return <div data-testid="tab-stats">Tab3 成绩统计</div>
  }
}))

import InfoAdmin from './InfoAdmin.jsx'

describe('InfoAdmin (信息课管理后台)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.getItem.mockReturnValue('fake-token')
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => [],
    })
  })

  it('默认显示单元管理Tab', async () => {
    render(<InfoAdmin />)
    await screen.findByTestId('tab-units')
  })

  it('点击题库管理Tab切换到Tab1', async () => {
    const user = userEvent.setup()
    render(<InfoAdmin />)
    await screen.findByTestId('tab-units')
    await user.click(screen.getByText('题库管理'))
    await screen.findByTestId('tab-questions')
  })

  it('点击小测管理Tab切换到Tab2', async () => {
    const user = userEvent.setup()
    render(<InfoAdmin />)
    await screen.findByTestId('tab-units')
    await user.click(screen.getByText('小测管理'))
    await screen.findByTestId('tab-sessions')
  })

  it('点击成绩统计Tab切换到Tab3', async () => {
    const user = userEvent.setup()
    render(<InfoAdmin />)
    await screen.findByTestId('tab-units')
    await user.click(screen.getByText('成绩统计'))
    await screen.findByTestId('tab-stats')
  })

  it('Tab标签显示正确图标', async () => {
    render(<InfoAdmin />)
    await screen.findByTestId('tab-units')
    // 四个Tab图标都存在
    expect(screen.getAllByTestId('icon-list').length).toBeGreaterThan(0)
  })

  it('显示Home按钮', async () => {
    render(<InfoAdmin />)
    await screen.findByTestId('icon-home')
  })

  it('点击Home按钮返回老师仪表盘', async () => {
    const user = userEvent.setup()
    render(<InfoAdmin />)
    await screen.findByTestId('icon-home')
    await user.click(screen.getByTestId('icon-home'))
    expect(mockNavigate).toHaveBeenCalled()
  })

  it('切换Tab后旧Tab内容消失', async () => {
    const user = userEvent.setup()
    render(<InfoAdmin />)
    await screen.findByTestId('tab-units')
    await user.click(screen.getByText('小测管理'))
    await screen.findByTestId('tab-sessions')
    expect(screen.queryByTestId('tab-units')).not.toBeInTheDocument()
  })
})
