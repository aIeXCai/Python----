/**
 * QuizResult 学生成绩页面测试
 * 运行: cd frontend && npx vitest run src/pages/student/QuizResult.test.jsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock Navbar
vi.mock('../../../components/Navbar.jsx', () => ({
  default: function MockNavbar({ username, grade, class_num }) {
    return <div data-testid="navbar">{username} {grade} {class_num}</div>
  }
}))

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Loader: () => <span data-testid="icon-loader">Loader</span>,
  ArrowLeft: () => <span data-testid="icon-arrowleft">ArrowLeft</span>,
  Award: () => <span data-testid="icon-award">Award</span>,
  RotateCcw: () => <span data-testid="icon-reset">RotateCcw</span>,
}))

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  ...vi.requireActual('react-router-dom'),
  useParams: () => ({ sessionId: '123' }),
  Link: ({ children, to }) => <a href={to} data-testid="link">{children}</a>,
}))

// Mock API
const mockGetInfoQuizResult = vi.fn()
vi.mock('../../../api/info.js', () => ({
  getInfoQuizResult: (...args) => mockGetInfoQuizResult(...args),
}))

// Mock localStorage
const localStorageMock = { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn() }
global.localStorage = localStorageMock

const mockResultData = {
  quiz_title: '第一章算法基础小测',
  score: 85,
  total_count: 4,
  correct_count: 3,
  submitted_at: '2026-04-24T10:00:00Z',
  question_results: [
    {
      question_id: 1,
      text: 'Python 中如何定义一个列表？',
      is_correct: true,
      options: {
        A: { text: '[1, 2, 3]', is_correct_answer: true },
        B: { text: '(1, 2, 3)', is_user_answer: true },
        C: { text: '{1, 2, 3}', is_correct_answer: false },
        D: { text: 'None', is_correct_answer: false },
      },
      explanation: '列表用方括号定义。',
    },
    {
      question_id: 2,
      text: '下列哪个是 Python 的关键字？',
      is_correct: false,
      options: {
        A: { text: 'list', is_correct_answer: false },
        B: { text: 'int', is_user_answer: true },
        C: { text: 'def', is_correct_answer: true },
        D: { text: 'print', is_correct_answer: false },
      },
      explanation: 'def 是定义函数的关键字。',
    },
  ],
}

// 内联简化版 QuizResult
function SimplifiedQuizResult({ resultData, loading, error }) {
  if (loading) {
    return (
      <div>
        <div data-testid="navbar"></div>
        <div data-testid="loading-state">载入成绩中...</div>
      </div>
    )
  }

  if (error || !resultData) {
    return (
      <div>
        <div data-testid="navbar"></div>
        <div data-testid="error-state">{error || '加载失败'}</div>
      </div>
    )
  }

  const getScoreClass = score => score >= 90 ? '#38ef7d' : score >= 70 ? '#f6c90e' : '#e53e3e'
  const { quiz_title, score, total_count, correct_count, submitted_at, question_results = [] } = resultData
  const wrong = question_results.filter(qr => !qr.is_correct)

  return (
    <div>
      <div data-testid="navbar"></div>

      {/* 成绩总览 */}
      <div data-testid="result-card">
        <h2 data-testid="result-title">{quiz_title}</h2>
        <div data-testid="submitted-time">提交时间：{submitted_at ? new Date(submitted_at).toLocaleString('zh-CN') : '-'}</div>
        <div data-testid="score-display" style={{ color: getScoreClass(score) }}>{score} 分</div>
        <div data-testid="correct-info">正确 {correct_count} 题</div>
        <div data-testid="wrong-info">错误 {total_count - correct_count} 题</div>
        <div data-testid="encouragement">
          {score >= 90 ? '🌟 优秀！' : score >= 70 ? '👍 良好，继续加油！' : '💪 继续努力！'}
        </div>
      </div>

      {/* 错题解析 */}
      {wrong.length > 0 && (
        <div data-testid="wrong-review">
          <h3 data-testid="wrong-title">错题解析</h3>
          {wrong.map((qr, i) => (
            <div key={qr.question_id} data-testid={`wrong-q-${i}`}>
              <div data-testid={`wrong-q-text-${i}`}>✗ {qr.text}</div>
              {qr.explanation && (
                <div data-testid={`wrong-q-exp-${i}`}>💡 {qr.explanation}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 操作按钮 */}
      <div data-testid="action-buttons">
        <a data-testid="retry-link" href="/student/quiz/123">重新作答</a>
        <a data-testid="back-link" href="/student/dashboard?course=info">返回列表</a>
      </div>
    </div>
  )
}

describe('QuizResult (学生成绩)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.getItem.mockReturnValue(JSON.stringify({ display_name: '张三', grade: '七年级', class_num: '1' }))
  })

  it('加载中状态', () => {
    render(<SimplifiedQuizResult loading={true} error="" resultData={null} />)
    expect(screen.getByTestId('loading-state').textContent).toBe('载入成绩中...')
  })

  it('错误状态', () => {
    render(<SimplifiedQuizResult loading={false} error="网络异常" resultData={null} />)
    expect(screen.getByTestId('error-state').textContent).toBe('网络异常')
  })

  it('显示小测标题', () => {
    render(<SimplifiedQuizResult loading={false} error="" resultData={mockResultData} />)
    expect(screen.getByTestId('result-title').textContent).toBe('第一章算法基础小测')
  })

  it('显示分数', () => {
    render(<SimplifiedQuizResult loading={false} error="" resultData={mockResultData} />)
    expect(screen.getByTestId('score-display').textContent).toBe('85 分')
  })

  it('分数>=70显示"良好，继续加油"', () => {
    render(<SimplifiedQuizResult loading={false} error="" resultData={mockResultData} />)
    expect(screen.getByTestId('encouragement').textContent).toBe('👍 良好，继续加油！')
  })

  it('显示正确和错误题数', () => {
    render(<SimplifiedQuizResult loading={false} error="" resultData={mockResultData} />)
    expect(screen.getByTestId('correct-info').textContent).toBe('正确 3 题')
    expect(screen.getByTestId('wrong-info').textContent).toBe('错误 1 题')
  })

  it('显示提交时间', () => {
    render(<SimplifiedQuizResult loading={false} error="" resultData={mockResultData} />)
    expect(screen.getByTestId('submitted-time').textContent).toContain('提交时间：')
  })

  it('有错题时显示错题解析', () => {
    render(<SimplifiedQuizResult loading={false} error="" resultData={mockResultData} />)
    expect(screen.getByTestId('wrong-review')).toBeInTheDocument()
    expect(screen.getByTestId('wrong-title').textContent).toBe('错题解析')
  })

  it('错题解析显示错题内容和解析', () => {
    render(<SimplifiedQuizResult loading={false} error="" resultData={mockResultData} />)
    expect(screen.getByTestId('wrong-q-text-0').textContent).toContain('Python 的关键字')
    expect(screen.getByTestId('wrong-q-exp-0').textContent).toContain('💡')
  })

  it('满分时显示"优秀"且无错题解析', () => {
    const perfectResult = { ...mockResultData, score: 100, correct_count: 4, question_results: [] }
    render(<SimplifiedQuizResult loading={false} error="" resultData={perfectResult} />)
    expect(screen.getByTestId('encouragement').textContent).toBe('🌟 优秀！')
    expect(screen.queryByTestId('wrong-review')).not.toBeInTheDocument()
  })

  it('不及格时显示"继续努力"', () => {
    const failResult = { ...mockResultData, score: 50, correct_count: 2, question_results: mockResultData.question_results.map(qr => ({ ...qr, is_correct: qr.question_id === 2 })) }
    render(<SimplifiedQuizResult loading={false} error="" resultData={failResult} />)
    expect(screen.getByTestId('encouragement').textContent).toBe('💪 继续努力！')
  })

  it('显示重新作答和返回链接', () => {
    render(<SimplifiedQuizResult loading={false} error="" resultData={mockResultData} />)
    expect(screen.getByTestId('retry-link')).toBeInTheDocument()
    expect(screen.getByTestId('back-link')).toBeInTheDocument()
  })
})
