/**
 * Result AI课成绩页面测试
 * 运行: cd frontend && npx vitest run src/pages/student/ai/Result.test.jsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock sessionStorage — 必须在 import 之前
const sessionStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
}
Object.defineProperty(global, 'sessionStorage', { value: sessionStorageMock })

// Mock react-router-dom（包含 MemoryRouter）
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  Link: ({ children, to }) => <a href={to}>{children}</a>,
  MemoryRouter: ({ children }) => <div>{children}</div>,
}))

import Result from './Result.jsx'

const mockResult = {
  problem_id: 456,
  score: 100,
  success: true,
  status: 'accepted',
  detail: 'All test cases passed!',
}

function renderWithSession(data) {
  sessionStorageMock.getItem.mockReturnValue(data ? JSON.stringify(data) : null)
  return render(<Result />)
}

describe('Result (AI课成绩页)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('空结果时返回null（不渲染）', () => {
    const { container } = renderWithSession(null)
    expect(container.firstChild).toBeNull()
  })

  it('满分显示"批改完成"标题', () => {
    renderWithSession(mockResult)
    expect(screen.getByText('🎉 批改完成')).toBeInTheDocument()
  })

  it('满分显示"全部通过"徽章', () => {
    renderWithSession(mockResult)
    expect(screen.getByText('✅ 全部通过')).toBeInTheDocument()
  })

  it('满分分数为100', () => {
    renderWithSession(mockResult)
    expect(screen.getByText('100')).toBeInTheDocument()
  })

  it('满分分数样式为text-green', () => {
    renderWithSession(mockResult)
    const scoreEl = screen.getByText('100')
    expect(scoreEl.className).toContain('text-green')
  })

  it('显示输出详情', () => {
    renderWithSession(mockResult)
    expect(screen.getByText(/All test cases passed!/)).toBeInTheDocument()
  })

  it('有再次尝试链接', () => {
    renderWithSession(mockResult)
    expect(screen.getByText('再次尝试')).toBeInTheDocument()
  })

  it('有返回主页链接', () => {
    renderWithSession(mockResult)
    expect(screen.getByText('返回主页')).toBeInTheDocument()
  })

  it('再次尝试链接指向题目页', () => {
    renderWithSession(mockResult)
    const link = screen.getByText('再次尝试').closest('a')
    expect(link.getAttribute('href')).toBe('/problem/456')
  })

  it('70分显示蓝色', () => {
    renderWithSession({ ...mockResult, score: 70, success: true, status: 'partial' })
    const scoreEl = screen.getByText('70')
    expect(scoreEl.className).toContain('text-blue')
  })

  it('40分显示黄色', () => {
    renderWithSession({ ...mockResult, score: 40, success: false, status: 'wrong_answer' })
    const scoreEl = screen.getByText('40')
    expect(scoreEl.className).toContain('text-yellow')
  })

  it('不及格显示红色', () => {
    renderWithSession({ ...mockResult, score: 20, success: false, status: 'wrong_answer' })
    const scoreEl = screen.getByText('20')
    expect(scoreEl.className).toContain('text-red')
  })

  it('失败时显示警告标题', () => {
    renderWithSession({ ...mockResult, score: 0, success: false, status: 'wrong_answer' })
    expect(screen.getByText(/⚠️/)).toBeInTheDocument()
  })
})
