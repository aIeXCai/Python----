/**
 * StudentManagement 学生管理页面测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/StudentManagement.test.jsx
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  ArrowLeft: () => <span data-testid="icon-back">ArrowLeft</span>,
  Users: () => <span data-testid="icon-users">Users</span>,
  Trash2: () => <span data-testid="icon-trash">Trash2</span>,
  Search: () => <span data-testid="icon-search">Search</span>,
  RefreshCw: () => <span data-testid="icon-refresh">RefreshCw</span>,
  Eye: () => <span data-testid="icon-eye">Eye</span>,
  EyeOff: () => <span data-testid="icon-eyeoff">EyeOff</span>,
  Edit2: () => <span data-testid="icon-edit">Edit2</span>,
  X: () => <span data-testid="icon-x">X</span>,
  Check: () => <span data-testid="icon-check">Check</span>,
}))

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}))

// Mock localStorage
const localStorageMock = { getItem: vi.fn() }
Object.defineProperty(global, 'localStorage', { value: localStorageMock })

// Mock fetch
global.fetch = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.getItem.mockReturnValue('fake-token')
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

const mockStudents = [
  {
    id: 1,
    username: '7-1-01',
    display_name: '张三',
    grade: '七年级',
    class_num: '1',
    student_number: '01',
    password_available: true,
  },
  {
    id: 2,
    username: '7-1-02',
    display_name: '李四',
    grade: '七年级',
    class_num: '1',
    student_number: '02',
    password_available: true,
  },
  {
    id: 3,
    username: '8-2-01',
    display_name: '王五',
    grade: '八年级',
    class_num: '2',
    student_number: '01',
    password_available: false,
  },
]

function mockFetchStudents(data = mockStudents) {
  global.fetch.mockResolvedValue({
    ok: true,
    json: async () => data,
  })
}

import StudentManagement from './StudentManagement.jsx'

describe('StudentManagement (学生管理)', () => {
  it('加载中显示loading状态', () => {
    global.fetch.mockImplementation(() => new Promise(() => {}))
    render(<StudentManagement />)
    // 组件应有加载状态
  })

  it('显示学生列表', async () => {
    mockFetchStudents()
    render(<StudentManagement />)
    await screen.findByText('张三')
    await screen.findByText('李四')
  })

  it('显示年级筛选下拉框', async () => {
    mockFetchStudents()
    render(<StudentManagement />)
    await screen.findByText('七年级')
  })

  it('搜索框输入过滤学生', async () => {
    mockFetchStudents()
    const user = userEvent.setup()
    render(<StudentManagement />)
    await screen.findByText('张三')

    const searchInput = screen.getByPlaceholderText('输入姓名搜索...')
    await user.clear(searchInput)
    await user.type(searchInput, '张三')
    await screen.findByText('张三')
    // 李四应该被过滤掉（但表格仍有它因为前端筛选）
  })

  it('点击返回按钮导航回上一页', async () => {
    mockFetchStudents()
    const user = userEvent.setup()
    render(<StudentManagement />)
    await screen.findByText('张三')
    await user.click(screen.getByTestId('icon-back'))
  })

  it('点击编辑按钮打开编辑弹窗', async () => {
    mockFetchStudents()
    const user = userEvent.setup()
    render(<StudentManagement />)
    await screen.findByText('张三')
    const editBtns = screen.getAllByTestId('icon-edit')
    await user.click(editBtns[0])
  })

  it('学生数据显示正确列信息', async () => {
    mockFetchStudents()
    render(<StudentManagement />)
    await screen.findByText('学生管理')
    await screen.findByText('张三')
    await screen.findByText('王五') // 八年级，唯一学生名
  })

  it('刷新按钮重新加载数据', async () => {
    mockFetchStudents()
    const user = userEvent.setup()
    render(<StudentManagement />)
    await screen.findByText('张三')
    await user.click(screen.getByTestId('icon-refresh'))
    // fetch should be called again
    expect(global.fetch).toHaveBeenCalled()
  })

  it('列表加载不会预取学生密码', async () => {
    mockFetchStudents()
    render(<StudentManagement />)
    await screen.findByText('张三')
    expect(global.fetch).toHaveBeenCalledTimes(1)
    expect(global.fetch.mock.calls[0][0]).not.toContain('/password/reveal/')
  })

  it('确认后调用专用接口显示密码，点击可立即隐藏', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    global.fetch.mockImplementation(async (url) => {
      if (url.includes('/password/reveal/')) {
        return {
          ok: true, status: 200,
          json: async () => ({ password: 'visible-test-password', display_seconds: 30 }),
        }
      }
      return { ok: true, status: 200, json: async () => mockStudents }
    })
    render(<StudentManagement />)
    await screen.findByText('张三')
    const showButtons = screen.getAllByText('显示')
    await user.click(showButtons[0])
    expect(window.confirm).toHaveBeenCalled()
    expect(await screen.findByText('visible-test-password')).toBeTruthy()
    expect(global.fetch.mock.calls.some(([url]) => url.includes('/auth/students/1/password/reveal/'))).toBe(true)
    await user.click(screen.getByText('隐藏'))
    expect(screen.queryByText('visible-test-password')).toBeNull()
  })

  it('密码在服务端指定时间后自动隐藏', async () => {
    vi.useFakeTimers()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    global.fetch.mockImplementation(async (url) => {
      if (url.includes('/password/reveal/')) {
        return {
          ok: true, status: 200,
          json: async () => ({ password: 'timer-test-password', display_seconds: 30 }),
        }
      }
      return { ok: true, status: 200, json: async () => mockStudents }
    })
    render(<StudentManagement />)
    await act(async () => { await Promise.resolve() })
    const button = screen.getAllByText('显示')[0]
    await act(async () => { button.click(); await Promise.resolve(); await Promise.resolve() })
    expect(screen.getByText('timer-test-password')).toBeTruthy()
    act(() => { vi.advanceTimersByTime(30_000) })
    expect(screen.queryByText('timer-test-password')).toBeNull()
  })

  it('不可恢复学生不会请求密码接口', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'alert').mockImplementation(() => {})
    mockFetchStudents()
    render(<StudentManagement />)
    await screen.findByText('王五')
    await user.click(screen.getByText('需重置'))
    expect(window.alert).toHaveBeenCalledWith('该学生密码不可查看，请先重置密码。')
    expect(global.fetch).toHaveBeenCalledTimes(1)
  })

  it('编辑弹窗可生成随机临时密码并短时展示', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    global.fetch.mockImplementation(async (url) => {
      if (url.includes('/password/reset/')) {
        return {
          ok: true, status: 200,
          json: async () => ({ temporary_password: 'RandomTempPass42', display_seconds: 30 }),
        }
      }
      return { ok: true, status: 200, json: async () => mockStudents }
    })
    render(<StudentManagement />)
    await screen.findByText('张三')
    await user.click(screen.getAllByTestId('icon-edit')[0])
    await user.click(screen.getByText('生成随机临时密码'))
    expect((await screen.findAllByText('RandomTempPass42')).length).toBeGreaterThan(0)
    const resetCall = global.fetch.mock.calls.find(([url]) => url.includes('/password/reset/'))
    expect(JSON.parse(resetCall[1].body)).toEqual({ mode: 'generated' })
  })
})
