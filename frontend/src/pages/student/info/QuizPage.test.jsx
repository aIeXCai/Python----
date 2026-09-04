import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

const mockNavigate = vi.fn()
const mockStart = vi.fn()
const mockSave = vi.fn()
const mockSubmit = vi.fn()
const mockSetContext = vi.fn()
const mockSetDisabled = vi.fn()
const mockClose = vi.fn()

vi.mock('react-router-dom', () => ({
  useParams: () => ({ sessionId: '123' }),
  useNavigate: () => mockNavigate,
  Link: ({ children, to }) => <a href={to}>{children}</a>,
}))

vi.mock('../../../api/info.js', () => ({
  startInfoQuizAttempt: (...args) => mockStart(...args),
  saveInfoQuizAnswers: (...args) => mockSave(...args),
  submitInfoQuizAttempt: (...args) => mockSubmit(...args),
}))

vi.mock('../../../contexts/ChatContext.jsx', () => ({
  useChat: () => ({ setContext: mockSetContext, setDisabled: mockSetDisabled, close: mockClose }),
}))

vi.mock('../../../components/Navbar.jsx', () => ({ default: () => <div data-testid="navbar" /> }))
vi.mock('lucide-react', () => ({
  Loader: () => <span>loading</span>,
  Clock: () => <span>clock</span>,
  ChevronLeft: () => <span>left</span>,
  ChevronRight: () => <span>right</span>,
}))

import QuizPage from './QuizPage.jsx'

const attemptData = {
  attempt_id: 9,
  status: 'in_progress',
  revision: 2,
  server_time: '2026-09-02T08:00:00Z',
  deadline_at: '2099-09-02T08:20:00Z',
  remaining_seconds: 1200,
  saved_answers: { 'item-1': 'B' },
  quiz: { id: 123, title: '可信小测', num_questions: 2, time_limit: 20 },
  questions: [
    { item_id: 'item-1', position: 1, text: '第一题', options: { A: '选项A1', B: '选项B1', C: '选项C1', D: '选项D1' } },
    { item_id: 'item-2', position: 2, text: '第二题', options: { A: '选项A2', B: '选项B2', C: '选项C2', D: '选项D2' } },
  ],
}

describe('QuizPage stage 4 attempt flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('user', JSON.stringify({ display_name: '学生', grade: '七年级', class_num: '1' }))
    mockStart.mockResolvedValue(attemptData)
    mockSave.mockResolvedValue({ revision: 3, saved_answers: { 'item-1': 'A' } })
    mockSubmit.mockResolvedValue({ score: 50, total_count: 2, correct_count: 1 })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('starts/resumes a server attempt and restores saved answers', async () => {
    render(<QuizPage />)
    expect(await screen.findByText('可信小测')).toBeInTheDocument()
    expect(mockStart).toHaveBeenCalledWith('123')
    const optionB = screen.getByRole('button', { name: /B.*选项B1/ })
    expect(optionB.style.background).not.toBe('rgb(255, 255, 255)')
  })

  it('autosaves display letters without sending answer mappings', async () => {
    render(<QuizPage />)
    await screen.findByText('可信小测')
    fireEvent.click(screen.getByRole('button', { name: /A.*选项A1/ }))
    await waitFor(() => expect(mockSave).toHaveBeenCalled(), { timeout: 1500 })
    const [, payload] = mockSave.mock.calls[0]
    expect(payload).toEqual(expect.objectContaining({ attempt_id: 9, revision: 2 }))
    expect(payload.answers['item-1']).toBe('A')
    expect(payload).not.toHaveProperty('shuffled_orders')
    expect(payload).not.toHaveProperty('correct_answer')
  })

  it('submits the fixed attempt then immediately navigates to the existing result page', async () => {
    render(<QuizPage />)
    await screen.findByText('可信小测')
    fireEvent.click(screen.getByRole('button', { name: /下一题/ }))
    fireEvent.click(screen.getByRole('button', { name: /C.*选项C2/ }))
    fireEvent.click(screen.getByRole('button', { name: '提交小测' }))
    await waitFor(() => expect(mockSubmit).toHaveBeenCalled())
    const [, payload] = mockSubmit.mock.calls[0]
    expect(payload.attempt_id).toBe(9)
    expect(payload.answers).toEqual(expect.objectContaining({ 'item-1': 'B', 'item-2': 'C' }))
    expect(mockNavigate).toHaveBeenCalledWith('/student/quiz-result/123')
  })

  it('uses a keepalive save when the page is being left', async () => {
    render(<QuizPage />)
    await screen.findByText('可信小测')
    fireEvent.click(screen.getByRole('button', { name: /A.*选项A1/ }))
    window.dispatchEvent(new Event('pagehide'))
    await waitFor(() => expect(mockSave).toHaveBeenCalled())
    expect(mockSave.mock.calls[0][2]).toEqual({ keepalive: true })
  })

  it('disables the in-platform AI while mounted and restores it on unmount', async () => {
    const { unmount } = render(<QuizPage />)
    await screen.findByText('可信小测')
    expect(mockSetContext).toHaveBeenCalledWith(null)
    expect(mockSetDisabled).toHaveBeenCalledWith(true, expect.stringContaining('正式小测'))
    expect(mockClose).toHaveBeenCalled()
    unmount()
    expect(mockSetDisabled).toHaveBeenLastCalledWith(false)
  })

  it('redirects completed attempts to the result page', async () => {
    const error = Object.assign(new Error('已完成'), {
      code: 'attempt_completed', data: { result_available: true },
    })
    mockStart.mockRejectedValue(error)
    render(<QuizPage />)
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/student/quiz-result/123', { replace: true }))
  })
})
