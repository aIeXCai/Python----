import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

const mockGetResult = vi.fn()

vi.mock('react-router-dom', () => ({
  useParams: () => ({ sessionId: '123' }),
  Link: ({ children, to }) => <a href={to}>{children}</a>,
}))
vi.mock('../../../components/Navbar.jsx', () => ({ default: () => <div data-testid="navbar" /> }))
vi.mock('../../../api/info.js', () => ({ getInfoQuizResult: (...args) => mockGetResult(...args) }))
vi.mock('lucide-react', () => ({
  Loader: () => <span>loading</span>,
  ArrowLeft: () => <span>back</span>,
  Award: () => <span>award</span>,
}))

import QuizResult from './QuizResult.jsx'

const result = {
  quiz_title: '第一章小测',
  score: 50,
  correct_count: 1,
  total_count: 2,
  submitted_at: '2026-09-02T08:00:00Z',
  can_retry: true,
  legacy_record: false,
  analysis_available: true,
  question_results: [{
    item_id: 'wrong-1',
    question_id: 'wrong-1',
    text: '错误题目',
    user_answer: 'B',
    correct_answer: 'C',
    is_correct: false,
    explanation: '这里是错题解析',
    options: {
      A: { text: '选项A', is_user_answer: false, is_correct_answer: false },
      B: { text: '选项B', is_user_answer: true, is_correct_answer: false },
      C: { text: '选项C', is_user_answer: false, is_correct_answer: true },
      D: { text: '选项D', is_user_answer: false, is_correct_answer: false },
    },
  }],
}

describe('QuizResult immediate score and wrong-answer analysis', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('user', JSON.stringify({ display_name: '学生' }))
    mockGetResult.mockResolvedValue(result)
  })

  it('shows score, correct count and wrong-answer explanation immediately', async () => {
    render(<QuizResult />)
    expect(await screen.findByText('第一章小测')).toBeInTheDocument()
    expect(screen.getByText('50')).toBeInTheDocument()
    expect(screen.getByText(/正确 1 题/)).toBeInTheDocument()
    expect(screen.getByText('错题解析')).toBeInTheDocument()
    expect(screen.getByText(/选项C.*正确答案/)).toBeInTheDocument()
    expect(screen.getByText(/选项B.*你的选择/)).toBeInTheDocument()
    expect(screen.getByText(/这里是错题解析/)).toBeInTheDocument()
  })

  it('offers another attempt while the quiz remains open', async () => {
    render(<QuizResult />)
    await screen.findByText('第一章小测')
    expect(screen.getByRole('link', { name: '再做一次' })).toHaveAttribute('href', '/student/quiz/123')
    expect(screen.getByText('返回列表')).toBeInTheDocument()
  })

  it('does not offer another attempt after the quiz is closed', async () => {
    mockGetResult.mockResolvedValue({ ...result, can_retry: false })
    render(<QuizResult />)
    await screen.findByText('第一章小测')
    expect(screen.queryByRole('link', { name: '再做一次' })).not.toBeInTheDocument()
  })

  it('explains when a legacy result cannot reconstruct analysis', async () => {
    mockGetResult.mockResolvedValue({ ...result, legacy_record: true, analysis_available: false, question_results: [] })
    render(<QuizResult />)
    expect(await screen.findByText(/逐题解析无法可靠还原/)).toBeInTheDocument()
  })
})
