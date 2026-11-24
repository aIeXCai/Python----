/**
 * PointsAdmin 教师积分管理页测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/PointsAdmin.test.jsx
 *
 * 重点覆盖 2026-11-24 的回归：StrictMode 下 effect 会「挂载 → 清理 → 再挂载」，
 * 若 mountedRef 只被置 false 不复位，页面会永远停在「加载中…」。
 */
import { StrictMode } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('lucide-react', () => ({
  ArrowLeft: () => <span />,
  Coins: () => <span data-testid="icon-coins" />,
  Minus: () => <span />,
  Plus: () => <span />,
  RefreshCw: () => <span />,
  RotateCcw: () => <span />,
  Search: () => <span />,
  X: () => <span />,
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}))

const mockGetAdminPointsStudents = vi.fn()
vi.mock('../../api/points.js', () => ({
  getAdminPointsStudents: (...args) => mockGetAdminPointsStudents(...args),
  adjustStudentPoints: vi.fn(),
  resetPoints: vi.fn(),
}))

import PointsAdmin from './PointsAdmin.jsx'

const STUDENTS = [
  {
    student_id: 1, name: '王雨桐', username: 'demo8103', grade: '八年级',
    class_num: '1', student_number: '4', points: '729.0',
  },
  {
    student_id: 2, name: '陈嘉禾', username: 'demo8101', grade: '八年级',
    class_num: '1', student_number: '2', points: '286.1',
  },
]

describe('PointsAdmin 教师积分管理页', () => {
  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('user', JSON.stringify({ role: 'teacher', managed_grade: '八年级' }))
    mockGetAdminPointsStudents.mockResolvedValue({
      grade: '八年级', students: STUDENTS, summary: {},
    })
    // 班级下拉的独立请求（接口返回的是字符串数组，如 ["1","2"]）
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ classes: ['1', '2'] }),
    }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('StrictMode 下加载结束后展示学生列表，不会停在「加载中」', async () => {
    render(
      <StrictMode>
        <PointsAdmin />
      </StrictMode>,
    )

    await waitFor(() => {
      expect(screen.queryByText('加载中…')).toBeNull()
    })
    expect(screen.getByText('王雨桐')).toBeInTheDocument()
    expect(screen.getByText('陈嘉禾')).toBeInTheDocument()
  })

  it('接口失败时给出错误提示而不是一直空白', async () => {
    mockGetAdminPointsStudents.mockRejectedValue(new Error('请求失败（500）'))

    render(
      <StrictMode>
        <PointsAdmin />
      </StrictMode>,
    )

    await waitFor(() => {
      expect(screen.queryByText('加载中…')).toBeNull()
    })
    expect(screen.getByText('请求失败（500）')).toBeInTheDocument()
  })
})
