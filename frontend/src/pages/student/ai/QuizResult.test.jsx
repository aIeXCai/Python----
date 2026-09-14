import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

const getResult = vi.hoisted(() => vi.fn())
vi.mock('react-router-dom', () => ({
  useParams: () => ({ sessionId: '12' }),
  Link: ({ to, children }) => <a href={to}>{children}</a>,
}))
vi.mock('../../../api/aiStudentQuiz.js', () => ({ getAIQuizResult: (...args) => getResult(...args) }))
vi.mock('../../../components/Navbar.jsx', () => ({ default: () => <div data-testid="navbar" /> }))

import AIQuizResult from './QuizResult.jsx'

const result = {
  attempt_id: 91, attempt_no: 1, status: 'submitted', final_reason: 'submitted', can_retry: true,
  quiz: { id: 12, title: '代码阅读小测' }, scores: { choice: '20.0', programming: '60.0', total: '80.0' },
  choice_summary: { correct_count: 0, question_count: 1 }, grading_issue_count: 0,
  choice_items: [{ item_id: 'c1', position: 1, text: '输出：\n```python\nprint("<结果>")\n```', options: { A: '`<结果>`', B: '无', C: '错误', D: '其他' }, selected_option: 'B', correct_option: 'A', is_correct: false, explanation: '因为 `print()` 会输出文本。' }],
  programming_items: [{ item_id: 'p1', position: 2, title: '编程题', points: '60.0', best_score: 100, earned_points: '60.0', submission_count: 2, status: 'scored' }],
}

describe('AIQuizResult Step 9', () => {
  beforeEach(() => { vi.clearAllMocks(); localStorage.setItem('user', '{}'); getResult.mockResolvedValue(result) })

  it('展示分项成绩、提交次数和重做入口', async () => {
    render(<AIQuizResult />)
    expect(await screen.findByText('代码阅读小测')).toBeInTheDocument()
    expect(screen.getByText('2 次有效提交')).toBeInTheDocument()
    const back = screen.getByRole('link', { name: '返回小测列表' })
    const retry = screen.getByRole('link', { name: /再做一次/ })
    expect(retry).toHaveAttribute('href', '/student/ai-quiz/12')
    expect(back.parentElement).toHaveClass('aiq-result-actions')
    expect(retry.parentElement).toBe(back.parentElement)
  })

  it('错题页的题干、选项和解析都正确渲染代码', async () => {
    const { container } = render(<AIQuizResult />)
    await screen.findByText('选择题解析')
    expect(container.querySelector('.question-code-block code').textContent).toBe('print("<结果>")')
    expect(container.querySelectorAll('.question-inline-code')).toHaveLength(2)
    expect(container.querySelector('结果')).toBeNull()
  })
})
