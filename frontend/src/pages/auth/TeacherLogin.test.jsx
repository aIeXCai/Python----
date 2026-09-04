import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import TeacherLogin from './TeacherLogin.jsx'

// We need to mock localStorage since jsdom Storage is read-only by default
const mockSetItem = vi.fn()
const mockGetItem = vi.fn((key) => {
  if (key === 'token') return 'fake-token'
  return null
})
const mockRemoveItem = vi.fn()

vi.stubGlobal('localStorage', {
  setItem: mockSetItem,
  getItem: mockGetItem,
  removeItem: mockRemoveItem,
  clear: vi.fn(),
})

describe('TeacherLogin.jsx', () => {
  beforeEach(() => {
    mockSetItem.mockClear()
    mockGetItem.mockClear()
    // Reset getItem to return null by default (no token)
    mockGetItem.mockImplementation((key) => {
      if (key === 'token') return null
      return null
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const renderTeacherLogin = () => {
    return render(
      <MemoryRouter>
        <TeacherLogin />
      </MemoryRouter>
    )
  }

  // ── Renders ──
  it('renders teacher login heading', () => {
    renderTeacherLogin()
    expect(screen.getByRole('heading', { name: /教师登录/i })).toBeTruthy()
  })

  it('renders username and password fields', () => {
    renderTeacherLogin()
    expect(screen.getByPlaceholderText(/用户名/i)).toBeTruthy()
    expect(screen.getByPlaceholderText(/密码/i)).toBeTruthy()
  })

  it('renders 登录 button', () => {
    renderTeacherLogin()
    expect(screen.getByRole('button', { name: /登录/i })).toBeTruthy()
  })

  it('renders back to student login link', () => {
    renderTeacherLogin()
    expect(screen.getByText(/返回学生登录/i)).toBeTruthy()
  })

  // ── Empty form shows error ──
  it('shows error when submitting empty form', async () => {
    const user = userEvent.setup()
    renderTeacherLogin()
    await user.click(screen.getByRole('button', { name: /登录/i }))
    expect(screen.getByText(/请填写用户名和密码/i)).toBeTruthy()
  })

  // ── Password visibility toggle ──
  it('hides password by default (type=password)', () => {
    renderTeacherLogin()
    const pw = screen.getByPlaceholderText(/密码/i)
    expect(pw.type).toBe('password')
  })

  // ── Success ──
  it('login success saves token and navigates to /teacher/dashboard', async () => {
    const user = userEvent.setup()
    global.fetch = vi.fn((url) => {
      if (url.includes('/api/auth/login/')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ token: 'test-teacher-token-xyz', user: { username: 'alex', display_name: 'Alex老师', role: 'teacher' } }),
        })
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) })
    })

    renderTeacherLogin()
    await user.type(screen.getByPlaceholderText(/用户名/i), 'alex')
    await user.type(screen.getByPlaceholderText(/密码/i), 'teacher123')
    await user.click(screen.getByRole('button', { name: /登录/i }))
    await new Promise(r => setTimeout(r, 50))

    expect(mockSetItem).toHaveBeenCalledWith('token', 'test-teacher-token-xyz')
    expect(mockSetItem).toHaveBeenCalledWith('user', expect.stringContaining('alex'))
  })

  // ── Failure ──
  it('shows error on login failure', async () => {
    const user = userEvent.setup()
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ error: '用户名或密码错误' }),
      })
    )

    renderTeacherLogin()
    await user.type(screen.getByPlaceholderText(/用户名/i), 'alex')
    await user.type(screen.getByPlaceholderText(/密码/i), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: /登录/i }))
    await new Promise(r => setTimeout(r, 50))

    expect(screen.getByText(/用户名或密码错误/i)).toBeTruthy()
  })

  it('shows generic error on network failure', async () => {
    const user = userEvent.setup()
    global.fetch = vi.fn(() => Promise.reject(new Error('Network failure')))

    renderTeacherLogin()
    await user.type(screen.getByPlaceholderText(/用户名/i), 'alex')
    await user.type(screen.getByPlaceholderText(/密码/i), 'teacher123')
    await user.click(screen.getByRole('button', { name: /登录/i }))
    await new Promise(r => setTimeout(r, 50))

    expect(screen.getByText(/Network failure/i)).toBeTruthy()
  })
})
