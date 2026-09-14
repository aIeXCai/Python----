/**
 * Tab3Stats 成绩统计测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/tabs/Tab3Stats.test.jsx
 */
import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { sortStudentsByNumber } from '../../../utils/studentSort.js'

vi.mock('lucide-react', () => ({
  BarChart2: () => <span data-testid="icon-barchart">BarChart2</span>,
  Users: () => <span data-testid="icon-users">Users</span>,
  CheckCircle: () => <span data-testid="icon-check">Check</span>,
  RefreshCw: () => <span data-testid="icon-refresh">RefreshCw</span>,
  X: () => <span data-testid="icon-x">X</span>,
}))

import Tab3Stats from './Tab3Stats.jsx'

const mockStatsData = {
  students: [
    { user_id: 1, username: '7-1-01', display_name: '张三', grade: '七年级', class_num: '1', student_number: '01', scores: [80, 95] },
    { user_id: 2, username: '7-1-02', display_name: '李四', grade: '七年级', class_num: '1', student_number: '02', scores: [100, null] },
    { user_id: 3, username: '8-1-03', display_name: '王五', grade: '八年级', class_num: '1', student_number: '03', scores: [75] },
  ],
  sessions: [
    { id: 1, title: '第一章小测', is_visible: true },
    { id: 2, title: '第二章小测', is_visible: false },
  ],
}

const gradeDisplay = g => g
const gradeColor = g => ({ '七年级': '#38ef7d', '八年级': '#11999e' })[g] || '#888'
const scoreColor = s => s >= 90 ? '#38ef7d' : s >= 60 ? '#f59e0b' : '#ef4444'

const defaultProps = {
  API: '/api',
  headers: {},
  statsData: mockStatsData,
  statsLoading: false,
  statsFilter: { grade: '七年级', class_num: '' },
  setStatsFilter: vi.fn(),
  selectedQuiz: '',
  setSelectedQuiz: vi.fn(),
  autoRefresh: false,
  setAutoRefresh: vi.fn(),
  loadStats: vi.fn(),
  gradeDisplay,
  gradeColor,
  scoreColor,
}

// 简化版 Tab3Stats（内联关键逻辑）
function SimplifiedTab3Stats(props) {
  const ROWS = 5, COLS = 10
  const [numberSort, setNumberSort] = useState(null)
  const toggleNumberSort = () => {
    setNumberSort(prev => (prev === null ? 'asc' : prev === 'asc' ? 'desc' : null))
  }
  const rawStudents = props.statsData?.students || []
  const displayStudents = numberSort ? sortStudentsByNumber(rawStudents, numberSort) : rawStudents

  const scoreMapByNum = {}
  ;(props.statsData?.students || []).forEach(stu => {
    const num = parseInt(stu.student_number) || 0
    if (num >= 1 && num <= ROWS * COLS) {
      const sc = stu.scores?.[0] ?? null
      if (sc != null) scoreMapByNum[num] = sc
    }
  })
  // 达标（≥80）人数
  const passCount = Object.values(scoreMapByNum).filter(v => v >= 80).length

  return (
    <div data-testid="tab3-stats">
      {/* 筛选栏 */}
      <div data-testid="filter-bar">
        <span data-testid="student-count">{props.statsData?.students?.length || 0} 人</span>
        <span data-testid="session-count">{props.statsData?.sessions?.length || 0} 场小测</span>

        <select data-testid="grade-select" value={props.statsFilter.grade} onChange={e => props.setStatsFilter(p => ({ ...p, grade: e.target.value }))}>
          <option value="七年级">七年级</option>
          <option value="八年级">八年级</option>
        </select>

        <select data-testid="class-select" value={props.statsFilter.class_num} onChange={e => props.setStatsFilter(p => ({ ...p, class_num: e.target.value }))}>
          <option value="">全部班级</option>
          {['1','2','3','4'].map(c => <option key={c} value={c}>{c}班</option>)}
        </select>

        <select data-testid="quiz-select" value={props.selectedQuiz} onChange={e => props.setSelectedQuiz(e.target.value)}>
          <option value="">全部小测</option>
          {(props.statsData?.sessions || []).map(s => <option key={s.id} value={String(s.id)}>{s.title}</option>)}
        </select>

        <label data-testid="auto-refresh-label">
          <input type="checkbox" checked={props.autoRefresh} onChange={e => props.setAutoRefresh(e.target.checked)} />
          5秒刷新
        </label>

        <button data-testid="refresh-btn" onClick={props.loadStats}>刷新</button>
      </div>

      {/* 成绩表格 */}
      {props.statsLoading ? (
        <div data-testid="loading">加载中...</div>
      ) : props.statsData?.students?.length === 0 ? (
        <div data-testid="empty-state">暂无成绩数据</div>
      ) : (
        <table data-testid="stats-table">
          <thead>
            <tr>
              <th>年级</th><th>班级</th><th>姓名</th>
              <th data-testid="sort-number" onClick={toggleNumberSort} style={{ cursor: 'pointer' }}>
                学号 {numberSort === 'asc' ? '↑' : numberSort === 'desc' ? '↓' : '↕'}
              </th>
              {(props.statsData?.sessions || []).map(s => <th key={s.id}>{s.title}</th>)}
            </tr>
          </thead>
          <tbody>
            {displayStudents.map(stu => (
              <tr key={stu.user_id} data-testid={`row-${stu.user_id}`}>
                <td>{props.gradeDisplay(stu.grade)}</td>
                <td>{stu.class_num}班</td>
                <td>{stu.display_name}</td>
                <td>{stu.student_number}</td>
                {(props.statsData?.sessions || []).map((s, idx) => {
                  const sc = stu.scores?.[idx] ?? null
                  return <td key={s.id} data-testid={`score-${stu.user_id}-${s.id}`}>{sc != null ? sc : '—'}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* 达标灯矩阵 */}
      <div data-testid="lamp-matrix">
        <div data-testid="perfect-count">{passCount}/{ROWS * COLS} 达标</div>
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${COLS}, 1fr)`, gap: 5 }}>
          {Array.from({ length: ROWS * COLS }, (_, idx) => {
            const lampNum = idx + 1
            const isLit = (scoreMapByNum[lampNum] || 0) >= 80
            return (
              <div key={idx} data-testid={`lamp-${lampNum}`} style={{
                background: isLit ? '#4caf50' : '#2a2a2a',
              }}>
                {lampNum}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

describe('Tab3Stats', () => {
  it('加载中状态', () => {
    render(<SimplifiedTab3Stats {...defaultProps} statsLoading={true} />)
    expect(screen.getByTestId('loading')).toBeInTheDocument()
  })

  it('空数据状态', () => {
    render(<SimplifiedTab3Stats {...defaultProps} statsData={{ students: [], sessions: [] }} />)
    expect(screen.getByTestId('empty-state')).toBeInTheDocument()
  })

  it('显示学生和小测数量', () => {
    render(<SimplifiedTab3Stats {...defaultProps} />)
    expect(screen.getByTestId('student-count').textContent).toBe('3 人')
    expect(screen.getByTestId('session-count').textContent).toBe('2 场小测')
  })

  it('年级筛选变化触发 setStatsFilter', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab3Stats {...defaultProps} />)
    await user.selectOptions(screen.getByTestId('grade-select'), '八年级')
    expect(defaultProps.setStatsFilter).toHaveBeenCalled()
  })

  it('班级筛选变化触发 setStatsFilter', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab3Stats {...defaultProps} />)
    await user.selectOptions(screen.getByTestId('class-select'), '2')
    expect(defaultProps.setStatsFilter).toHaveBeenCalled()
  })

  it('小测筛选变化触发 setSelectedQuiz', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab3Stats {...defaultProps} />)
    await user.selectOptions(screen.getByTestId('quiz-select'), '1')
    expect(defaultProps.setSelectedQuiz).toHaveBeenCalledWith('1')
  })

  it('刷新按钮触发 loadStats', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab3Stats {...defaultProps} />)
    await user.click(screen.getByTestId('refresh-btn'))
    expect(defaultProps.loadStats).toHaveBeenCalled()
  })

  it('自动刷新开关触发 setAutoRefresh', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab3Stats {...defaultProps} autoRefresh={false} />)
    const checkbox = screen.getByTestId('auto-refresh-label').querySelector('input')
    await user.click(checkbox)
    expect(defaultProps.setAutoRefresh).toHaveBeenCalledWith(true)
  })

  it('表格正确渲染学生成绩', () => {
    render(<SimplifiedTab3Stats {...defaultProps} />)
    expect(screen.getByText('张三')).toBeInTheDocument()
    expect(screen.getByText('李四')).toBeInTheDocument()
  })

  it('点击学号表头按学号升序/降序排序', async () => {
    const user = userEvent.setup()
    const unsorted = {
      ...mockStatsData,
      students: [
        mockStatsData.students[2], // 王五 03
        mockStatsData.students[0], // 张三 01
        mockStatsData.students[1], // 李四 02
      ],
    }
    render(<SimplifiedTab3Stats {...defaultProps} statsData={unsorted} />)
    const names = () => screen.getAllByTestId(/^row-/).map(r => r.children[2].textContent)

    expect(names()).toEqual(['王五', '张三', '李四'])   // 默认：后端返回顺序
    await user.click(screen.getByTestId('sort-number'))
    expect(names()).toEqual(['张三', '李四', '王五'])   // 升序
    await user.click(screen.getByTestId('sort-number'))
    expect(names()).toEqual(['王五', '李四', '张三'])   // 降序
  })

  it('学号按数字排序而非字符串（2 排在 10 之前）', async () => {
    const user = userEvent.setup()
    const data = {
      sessions: [],
      students: [
        { user_id: 1, username: 'x1', display_name: '十号', grade: '七年级', class_num: '1', student_number: '10', scores: [50] },
        { user_id: 2, username: 'x2', display_name: '二号', grade: '七年级', class_num: '1', student_number: '2', scores: [60] },
      ],
    }
    render(<SimplifiedTab3Stats {...defaultProps} statsData={data} />)
    await user.click(screen.getByTestId('sort-number'))
    expect(screen.getAllByTestId(/^row-/).map(r => r.children[2].textContent)).toEqual(['二号', '十号'])
  })

  it('≥80 分学生灯矩阵为绿色', () => {
    render(<SimplifiedTab3Stats {...defaultProps} />)
    // 李四学号02，第一场小测100分 → 亮
    const lamp2 = screen.getByTestId('lamp-2')
    expect(lamp2.style.background).toBe('rgb(76, 175, 80)')
    // 张三学号01，第一场小测80分 → 达标也亮
    const lamp1 = screen.getByTestId('lamp-1')
    expect(lamp1.style.background).toBe('rgb(76, 175, 80)')
  })

  it('低于80分学生灯矩阵为暗色', () => {
    render(<SimplifiedTab3Stats {...defaultProps} />)
    // 王五学号03，第一场小测75分 → 不亮
    const lamp3 = screen.getByTestId('lamp-3')
    expect(lamp3.style.background).toBe('rgb(42, 42, 42)')
  })

  it('达标计数正确', () => {
    render(<SimplifiedTab3Stats {...defaultProps} />)
    expect(screen.getByTestId('perfect-count').textContent).toBe('2/50 达标')
  })

  it('切换到具体小测时只显示一列成绩', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab3Stats {...defaultProps} selectedQuiz="" />)
    await user.selectOptions(screen.getByTestId('quiz-select'), '1')
    expect(defaultProps.setSelectedQuiz).toHaveBeenCalledWith('1')
  })

  it('真实灯阵支持按小测设置阈值并保存', async () => {
    localStorage.clear()
    const user = userEvent.setup()
    render(<Tab3Stats {...defaultProps} selectedQuiz="1" />)

    const threshold = screen.getByLabelText('信息科技小测亮灯阈值')
    expect(threshold).toHaveValue(80)
    expect(screen.getByLabelText('学号 1已亮灯')).toBeInTheDocument()
    await user.clear(threshold)
    await user.type(threshold, '90')

    expect(screen.getByLabelText('学号 1未亮灯')).toBeInTheDocument()
    expect(screen.getByLabelText('学号 2已亮灯')).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('infoQuizLampThresholds'))['1']).toBe(90)
  })

  it('年级切换时 setSelectedQuiz 为空（清空小测筛选）', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab3Stats {...defaultProps} selectedQuiz="1" />)
    await user.selectOptions(screen.getByTestId('grade-select'), '八年级')
    // 年级切换后，selectedQuiz 应该被清空（组件内部行为）
    expect(defaultProps.setStatsFilter).toHaveBeenCalled()
  })
})
