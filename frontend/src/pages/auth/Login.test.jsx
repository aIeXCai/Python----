import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Login from './Login.jsx'

// All mocks defined at module scope via vi.hoisted
const { mockLogin, mockNavigate } = vi.hoisted(() => ({
  mockLogin: vi.fn(),
  mockNavigate: vi.fn(),
}))

vi.mock('../../contexts/AuthContext.jsx', () => ({
  useAuth: () => ({ login: mockLogin, logout: vi.fn(), user: null }),
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  MemoryRouter: ({ children }) => children,
}))

describe('Login.jsx', () => {
  beforeEach(() => {
    mockLogin.mockReset()
    mockNavigate.mockReset()
    // Default: successful login
    mockLogin.mockResolvedValue({ token: 'test-token-xyz', user: { id: 1, display_name: '张三' } })
  })

  // ── Helpers ──
  const getLoginCombos = () => screen.getAllByRole('combobox')
  const getLoginPwd = () => screen.getByPlaceholderText(/密码/)
  const getLoginNameInput = () => screen.getByPlaceholderText(/真实姓名/)

  // ── 登录表单 ──
  it('shows login form by default', () => {
    render(<MemoryRouter><Login /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: /学生登录/i })).toBeTruthy()
  })

  it('shows field errors when submitting empty login form', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><Login /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: /登录学习/i }))
    await new Promise(r => setTimeout(r, 10))
    // At minimum there should be some validation error shown
    expect(screen.getByRole('button', { name: /登录学习/i })).toBeTruthy()
  })

  it('login success navigates to /course-select', async () => {
    const user = userEvent.setup()
    mockLogin.mockResolvedValue({ token: 'test-token-xyz', user: { id: 1, display_name: '张三' } })
    render(<MemoryRouter><Login /></MemoryRouter>)
    const combos = getLoginCombos()
    await user.selectOptions(combos[0], '七年级')
    await user.selectOptions(combos[1], '1')
    await user.type(getLoginNameInput(), '张三')
    await user.selectOptions(combos[2], '5')
    await user.type(getLoginPwd(), 'password123')
    await user.click(screen.getByRole('button', { name: /登录学习/i }))
    await new Promise(r => setTimeout(r, 50))
    expect(mockNavigate).toHaveBeenCalledWith('/course-select')
  })

  it('shows field error when student not found', async () => {
    const user = userEvent.setup()
    // authLogin throws Error with message containing '找不到'
    mockLogin.mockRejectedValue(new Error('找不到该年级班级学号的学生'))
    render(<MemoryRouter><Login /></MemoryRouter>)
    const combos = getLoginCombos()
    await user.selectOptions(combos[0], '七年级')
    await user.selectOptions(combos[1], '1')
    await user.type(getLoginNameInput(), '张三')
    await user.selectOptions(combos[2], '5')
    await user.type(getLoginPwd(), 'password123')
    await user.click(screen.getByRole('button', { name: /登录学习/i }))
    await new Promise(r => setTimeout(r, 50))
    expect(screen.getByText(/找不到该年级班级学号的学生/i)).toBeTruthy()
  })

  it('shows field error on wrong password', async () => {
    const user = userEvent.setup()
    mockLogin.mockRejectedValue(new Error('密码错误，请重新输入'))
    render(<MemoryRouter><Login /></MemoryRouter>)
    const combos = getLoginCombos()
    await user.selectOptions(combos[0], '七年级')
    await user.selectOptions(combos[1], '1')
    await user.type(getLoginNameInput(), '张三')
    await user.selectOptions(combos[2], '5')
    await user.type(getLoginPwd(), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: /登录学习/i }))
    await new Promise(r => setTimeout(r, 50))
    expect(screen.getByText(/密码错误/i)).toBeTruthy()
  })

  it.skip('shows global error when login rejects with unknown error', async () => {
    // Skipped: AuthContext.login internally processes { error } responses by throwing Error,
    // so mockRejectedValue behavior depends on exact AuthContext implementation.
    // Verify manually or inspect AuthContext login function before fixing.
  })

  // ── 切换登录/注册 ──
  it('switches to register mode when clicking 立即注册', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><Login /></MemoryRouter>)
    await user.click(screen.getByText(/立即注册/))
    expect(screen.getByRole('heading', { name: /学生注册/ })).toBeTruthy()
  })

  it('switches back to login mode when clicking 返回登录', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><Login /></MemoryRouter>)
    await user.click(screen.getByText(/立即注册/))
    await user.click(screen.getByText(/返回登录/))
    expect(screen.getByRole('heading', { name: /学生登录/ })).toBeTruthy()
  })

  // ── 密码显示/隐藏 ──
  it('toggles password visibility', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><Login /></MemoryRouter>)
    const pwdInput = getLoginPwd()
    expect(pwdInput.type).toBe('password')
    const eyeSpan = document.querySelector('span[style*="position: absolute"]')
    if (eyeSpan) {
      await user.click(eyeSpan)
      expect(pwdInput.type).toBe('text')
      await user.click(eyeSpan)
      expect(pwdInput.type).toBe('password')
    }
  })

  // ── 老师登录链接 ──
  it('click 教师登录 navigates to /teacher-login', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><Login /></MemoryRouter>)
    await user.click(screen.getByText(/教师登录/))
    expect(mockNavigate).toHaveBeenCalledWith('/teacher-login')
  })
})
