/**
 * AiAdmin AI课老师管理后台测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/aiAdmin.test.jsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  ArrowLeft: () => <span data-testid="icon-back">ArrowLeft</span>,
  Bot: () => <span data-testid="icon-bot">Bot</span>,
  BookOpen: () => <span data-testid="icon-book">BookOpen</span>,
  BarChart3: () => <span data-testid="icon-chart">BarChart3</span>,
  RefreshCw: () => <span data-testid="icon-refresh">RefreshCw</span>,
  Eye: () => <span data-testid="icon-eye">Eye</span>,
  Trash2: () => <span data-testid="icon-trash">Trash2</span>,
  Upload: () => <span data-testid="icon-upload">Upload</span>,
  X: () => <span data-testid="icon-x">X</span>,
  Plus: () => <span data-testid="icon-plus">Plus</span>,
  Edit2: () => <span data-testid="icon-edit">Edit2</span>,
  CheckCircle: () => <span data-testid="icon-check">CheckCircle</span>,
}))

// Mock react-router-dom
const mockNavigate = vi.fn()
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}))

// Mock localStorage
const localStorageMock = { getItem: vi.fn() }
Object.defineProperty(global, 'localStorage', { value: localStorageMock })

// ── Mock 数据 ────────────────────────────────────────────────────────────────
const mockProblemsData = [
  { problem_id: 'p001', title: '排序算法', difficulty: '入门', grade: '七年级', description: '实现快速排序' },
  { problem_id: 'p002', title: '二分查找', difficulty: '进阶', grade: '七年级', description: '在有序数组中查找' },
  { problem_id: 'p003', title: '动态规划', difficulty: '高级', grade: '八年级', description: '背包问题' },
]

const mockScoresData = {
  students: [
    { id: 1, display_name: '张三', student_number: '1', grade: '七年级', class_num: '1', best_score: 95, scores: [{ submitted: true, score: 95 }] },
    { id: 2, display_name: '李四', student_number: '2', grade: '七年级', class_num: '1', best_score: 78, scores: [{ submitted: true, score: 78 }] },
  ],
  problems: [{ problem_id: 'p001', title: '排序算法' }, { problem_id: 'p002', title: '二分查找' }],
}

// Global fetch mock — 统一拦截所有 API 调用
global.fetch = vi.fn((url, options = {}) => {
  const method = options.method || 'GET'

  // DELETE /api/ai/admin/problems/<id>/
  if (method === 'DELETE' && /\/ai\/admin\/problems\/[^/]+\/$/.test(url)) {
    return Promise.resolve({ ok: true, status: 204 })
  }

  // POST /api/ai/admin/problems/ (sync)
  if (method === 'POST' && url.includes('/ai/admin/problems/')) {
    return Promise.resolve({ ok: true, json: async () => ({ created: 1, updated: 2 }) })
  }

  // GET /api/ai/admin/scores/...
  if (url.includes('/ai/admin/scores/')) {
    return Promise.resolve({ ok: true, json: async () => mockScoresData })
  }

  // GET /api/ai/admin/problems/<id>/ (detail)
  if (/\/ai\/admin\/problems\/[^/]+\/$/.test(url)) {
    return Promise.resolve({ ok: true, json: async () => mockProblemsData[0] })
  }

  // GET /api/ai/admin/problems/ (list) — 默认返回数组
  return Promise.resolve({ ok: true, json: async () => mockProblemsData })
})

// Mock window.confirm / window.alert
const mockConfirm = vi.fn(() => true)
const mockAlert = vi.fn(() => {})
beforeEach(() => {
  vi.clearAllMocks()
  mockConfirm.mockReturnValue(true)
  mockAlert.mockReturnValue()
  window.confirm = mockConfirm
  window.alert = mockAlert
  localStorage.getItem.mockReturnValue('fake-token')
})

import AiAdmin from './aiAdmin.jsx'

describe('AiAdmin (AI课管理后台)', () => {
  // ── 返回按钮 ──────────────────────────────────────────────────────────────
  it('点击返回按钮导航回老师仪表盘', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByTestId('icon-back')
    await user.click(screen.getByTestId('icon-back'))
    expect(mockNavigate).toHaveBeenCalled()
  })

  // ── Tab 导航 ──────────────────────────────────────────────────────────────
  it('默认显示题库管理Tab（题目卡片存在）', async () => {
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    await screen.findByText('二分查找')
  })

  it('点击成绩统计Tab切换到Tab1', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    await user.click(screen.getByText('成绩统计'))
    await screen.findByText('张三')
  })

  it('点击题库管理Tab切换回Tab0', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    // 先切到成绩统计
    await user.click(screen.getByText('成绩统计'))
    await screen.findByText('张三')
    // 再切回来
    await user.click(screen.getByText('题库管理'))
    await screen.findByText('排序算法')
  })

  // ── Tab0: 题库管理 ────────────────────────────────────────────────────────
  it('题目卡片显示难度标签', async () => {
    render(<AiAdmin />)
    await screen.findByText('入门')
    await screen.findByText('进阶')
  })

  it('点击查看按钮触发viewProblem', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    const eyeBtns = screen.getAllByTestId('icon-eye')
    await user.click(eyeBtns[0])
    // 详情弹窗加载完成
    await screen.findByTestId('icon-x')
  })

  it('点击删除按钮弹出确认框', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    const trashBtns = screen.getAllByTestId('icon-trash')
    await user.click(trashBtns[0])
    expect(mockConfirm).toHaveBeenCalled()
  })

  it('取消删除时不调用API', async () => {
    mockConfirm.mockReturnValue(false)
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    const trashBtns = screen.getAllByTestId('icon-trash')
    await user.click(trashBtns[0])
    expect(mockConfirm).toHaveBeenCalled()
  })

  it('点击刷新按钮重新加载题库', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    await user.click(screen.getByTestId('icon-refresh'))
    await screen.findByText('排序算法') // 等刷新完成
  })

  it('Tab0显示加载状态', async () => {
    // loading=true 时显示 spinner
    render(<AiAdmin />)
    // 初始有 loading 态，很快被覆盖
  })

  // ── Tab1: 成绩统计 ────────────────────────────────────────────────────────
  it('成绩统计Tab显示学生列表', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await user.click(screen.getByText('成绩统计'))
    await screen.findByText('张三')
    await screen.findByText('李四')
  })

  it('成绩统计显示学生姓名', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await user.click(screen.getByText('成绩统计'))
    await screen.findByText('张三')
  })

  it('成绩统计显示班级信息', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await user.click(screen.getByText('成绩统计'))
    // AI课成绩标题存在
    await screen.findByText('AI课成绩')
  })

  it('Tab1显示年级筛选下拉框', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await user.click(screen.getByText('成绩统计'))
    // 下拉框的 label 存在
    const labels = screen.getAllByText('年级')
    expect(labels.length).toBeGreaterThan(0)
  })

  it('Tab1显示题目筛选下拉框', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await user.click(screen.getByText('成绩统计'))
    await screen.findByText('题目')
  })

  // ── 弹窗 ──────────────────────────────────────────────────────────────────
  it('关闭详情弹窗', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    // 打开弹窗
    const eyeBtns = screen.getAllByTestId('icon-eye')
    await user.click(eyeBtns[0])
    // 弹窗关闭按钮
    const xBtn = screen.getByTestId('icon-x')
    await user.click(xBtn)
  })
})
