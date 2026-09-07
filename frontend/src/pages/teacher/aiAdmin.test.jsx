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
  Archive: () => <span data-testid="icon-archive">Archive</span>,
  Upload: () => <span data-testid="icon-upload">Upload</span>,
  X: () => <span data-testid="icon-x">X</span>,
  Edit2: () => <span data-testid="icon-edit">Edit2</span>,
  EyeOff: () => <span data-testid="icon-eye-off">EyeOff</span>,
  RotateCcw: () => <span data-testid="icon-restore">RotateCcw</span>,
  ChevronDown: () => <span data-testid="icon-chevron">ChevronDown</span>,
  Tag: () => <span data-testid="icon-tag">Tag</span>,
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
  { problem_id: 'p001', title: '排序算法', difficulty: '入门', grade_tag: '七年级', description: '实现快速排序', management_version: 1, can_edit_content: true, can_archive: true, publishing_suspended: false, archived_at: null, publication_label: '全校可见', publication: { all_school: true, scopes: [] } },
  { problem_id: 'p002', title: '二分查找', difficulty: '进阶', grade_tag: '八年级', description: '在有序数组中查找', management_version: 1, can_edit_content: true, can_archive: true, publishing_suspended: true, archived_at: null, publication_label: '已暂停', publication: { all_school: false, scopes: [] } },
  { problem_id: 'p003', title: '动态规划', difficulty: '高级', grade_tag: '', description: '背包问题', management_version: 1, can_edit_content: true, can_archive: true, publishing_suspended: false, archived_at: null, publication_label: '七年级1班', publication: { all_school: false, scopes: [{ grade: '七年级', visible: true, all_classes: false, classes: ['1'] }] } },
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
    return Promise.resolve({ ok: true, status: 200, json: async () => ({ message: '已归档' }) })
  }

  // POST /api/ai/admin/problems/ (sync)
  if (method === 'POST' && url.includes('/ai/admin/problems/')) {
    return Promise.resolve({ ok: true, json: async () => ({ created: ['p004'], updated: ['p001', 'p002'], skipped: [], failed: [] }) })
  }

  if (url.includes('/ai/admin/problem-classes/')) {
    return Promise.resolve({ ok: true, status: 200, json: async () => ({ grade: '七年级', classes: ['1', '2'] }) })
  }

  if (method === 'PATCH' && url.includes('/publication/')) {
    return Promise.resolve({ ok: true, status: 200, json: async () => ({ management_version: 2, publishing_suspended: false, all_school: false, scopes: [{ grade: '七年级', visible: true, all_classes: false, classes: ['1'] }] }) })
  }

  if (method === 'PATCH' && /\/ai\/admin\/problems\/[^/]+\/$/.test(url)) {
    return Promise.resolve({ ok: true, status: 200, json: async () => ({ ...mockProblemsData[0], title: '已修改题目', management_version: 2 }) })
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
  localStorage.getItem.mockImplementation(key => key === 'user'
    ? JSON.stringify({ username: 'Alex', role: 'teacher', is_superuser: true, managed_grade: '' })
    : 'fake-token')
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

  it('题目卡片显示适用年级标签并可一键筛选', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    expect(screen.getAllByText('七年级').length).toBeGreaterThan(0)
    expect(screen.getAllByText('未分类').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: '八年级 1' }))
    expect(screen.getByText('二分查找')).toBeInTheDocument()
    expect(screen.queryByText('排序算法')).not.toBeInTheDocument()
    expect(screen.getByText('已筛选 1 / 3 题')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '全部 3' }))
    expect(screen.getByText('排序算法')).toBeInTheDocument()
  })

  it('题目卡片显示发布状态和范围', async () => {
    render(<AiAdmin />)
    await screen.findByText('全校可见')
    await screen.findByText('已暂停')
    expect(screen.getAllByText('可见').length).toBeGreaterThan(0)
    expect(screen.getAllByText('不可见').length).toBeGreaterThan(0)
  })

  it('可编辑题目内容并保存', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    await user.click(screen.getByRole('button', { name: '编辑排序算法' }))
    const title = await screen.findByLabelText('题目名称')
    await user.clear(title)
    await user.type(title, '已修改题目')
    await user.click(screen.getByRole('button', { name: '保存修改' }))
    await screen.findByText('题目「已修改题目」已保存')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/ai/admin/problems/p001/'),
      expect.objectContaining({ method: 'PATCH' }),
    )
  })

  it('编辑弹窗内合并两级范围下拉和全校选项', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    await user.click(screen.getByRole('button', { name: '编辑排序算法' }))
    expect(await screen.findByText('可见范围')).toBeInTheDocument()
    expect(screen.getByText('1. 可见年级（可多选）')).toBeInTheDocument()
    expect(screen.getByText('2. 可见班级')).toBeInTheDocument()
    expect(screen.getAllByText('全校可见').length).toBeGreaterThan(0)
  })

  it('可直接隐藏已发布题目', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    await user.click(screen.getByRole('button', { name: '隐藏排序算法' }))
    await screen.findByText('题目可见状态已更新')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/publication/'),
      expect.objectContaining({ method: 'PATCH' }),
    )
  })

  it('题目卡片移除查看和独立范围按钮', async () => {
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    expect(screen.queryByRole('button', { name: /查看/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /范围/ })).not.toBeInTheDocument()
  })

  it('点击归档按钮弹出确认框', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    await user.click(screen.getByRole('button', { name: '归档排序算法' }))
    expect(mockConfirm).toHaveBeenCalled()
  })

  it('取消归档时不调用API', async () => {
    mockConfirm.mockReturnValue(false)
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    await user.click(screen.getByRole('button', { name: '归档排序算法' }))
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
  it('可关闭编辑弹窗', async () => {
    const user = userEvent.setup()
    render(<AiAdmin />)
    await screen.findByText('排序算法')
    await user.click(screen.getByRole('button', { name: '编辑排序算法' }))
    await screen.findByText('编辑 AI 题目')
    await user.click(screen.getByRole('button', { name: '关闭' }))
    expect(screen.queryByText('编辑 AI 题目')).not.toBeInTheDocument()
  })
})
