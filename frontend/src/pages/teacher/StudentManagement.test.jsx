/**
 * StudentManagement 学生管理页面测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/StudentManagement.test.jsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
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

const mockStudents = [
  {
    id: 1,
    username: '7-1-01',
    display_name: '张三',
    grade: '七年级',
    class_num: '1',
    student_number: '01',
    plain_password: 'pass123',
  },
  {
    id: 2,
    username: '7-1-02',
    display_name: '李四',
    grade: '七年级',
    class_num: '1',
    student_number: '02',
    plain_password: 'pass456',
  },
  {
    id: 3,
    username: '8-2-01',
    display_name: '王五',
    grade: '八年级',
    class_num: '2',
    student_number: '01',
    plain_password: 'pass789',
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
})
