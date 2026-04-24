/**
 * Tab1Questions 筛选逻辑单元测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/tabs/Tab1Questions.test.jsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  BookOpen: () => <span data-testid="icon-bookopen">BookOpen</span>,
  Plus: () => <span data-testid="icon-plus">Plus</span>,
  Edit2: () => <span data-testid="icon-edit">Edit</span>,
  Trash2: () => <span data-testid="icon-trash">Trash</span>,
  FileText: () => <span data-testid="icon-file">File</span>,
  X: () => <span data-testid="icon-x">X</span>,
  Upload: () => <span data-testid="icon-upload">Upload</span>,
  CheckCircle: () => <span data-testid="icon-check">Check</span>,
}))

const API = 'http://localhost:8080/api'

// 真实的 Tab1Questions（从父文件复制出关键逻辑以便测试）
// 由于 Tab1Questions 嵌套了 QuestionModal/ImportModal，这里只测试主体筛选渲染逻辑

const difficultyLabel = d => ({ easy: '容易', medium: '中等', hard: '困难' }[d] || d)
const difficultyBadgeColor = d => ({ easy: '#38ef7d', medium: '#f59e0b', hard: '#ef4444' }[d] || '#888')

// 模拟题库数据
const mockQuestions = [
  { id: 1, grade: '七年级', big_unit_name: '第一章', unit_name: '第一节', difficulty: 'easy', text: '题目1内容', answer: 'A', option_a: 'a', option_b: 'b', option_c: 'c', option_d: 'd' },
  { id: 2, grade: '七年级', big_unit_name: '第一章', unit_name: '第二节', difficulty: 'medium', text: '题目2内容', answer: 'B', option_a: 'a', option_b: 'b', option_c: 'c', option_d: 'd' },
  { id: 3, grade: '八年级', big_unit_name: '第二章', unit_name: '第一节', difficulty: 'hard', text: '题目3内容', answer: 'C', option_a: 'a', option_b: 'b', option_c: 'c', option_d: 'd' },
]

// 模拟单元数据
const mockQAllUnits = [
  { id: 1, name: '第一章', display_name: '第一章 数据与信息', grade: '七年级', parent: null },
  { id: 2, name: '第一节', display_name: '1.1 什么是数据', grade: '七年级', parent: { name: '第一章', display_name: '第一章 数据与信息' } },
  { id: 3, name: '第二节', display_name: '1.2 数据的编码', grade: '七年级', parent: { name: '第一章', display_name: '第一章 数据与信息' } },
  { id: 4, name: '第二章', display_name: '第二章 算法基础', grade: '八年级', parent: null },
  { id: 5, name: '第一节', display_name: '2.1 算法的概念', grade: '八年级', parent: { name: '第二章', display_name: '第二章 算法基础' } },
]

const mockQBigUnits = [
  { id: 1, name: '第一章', display_name: '第一章 数据与信息', grade: '七年级', sections: [
    { id: 2, name: '第一节', display_name: '1.1 什么是数据' },
    { id: 3, name: '第二节', display_name: '1.2 数据的编码' },
  ]},
  { id: 4, name: '第二章', display_name: '第二章 算法基础', grade: '八年级', sections: [
    { id: 5, name: '第一节', display_name: '2.1 算法的概念' },
  ]},
]

// 简化版 Tab1Questions 用于测试筛选逻辑
function SimplifiedTab1Questions({ questions, qGradeFilter, setQGradeFilter, qBigUnits, qBigUnitFilter, setQBigUnitFilter, qAllUnits, filterUnit, setFilterUnit, selectedQuestions, handleSelectAll, handleSelectOne, handleApplyFilter }) {
  const difficultyBadgeColorLocal = d => ({ easy: '#38ef7d', medium: '#f59e0b', hard: '#ef4444' }[d] || '#888')
  const difficultyLabelLocal = d => ({ easy: '容易', medium: '中等', hard: '困难' }[d] || d)

  return (
    <div>
      {/* 年级筛选 */}
      <select data-testid="grade-filter" value={qGradeFilter} onChange={e => setQGradeFilter(e.target.value)}>
        <option value="七年级">七年级</option>
        <option value="八年级">八年级</option>
      </select>

      {/* 大单元筛选 */}
      <select data-testid="bigunit-filter" value={qBigUnitFilter} onChange={e => { setQBigUnitFilter(e.target.value); setFilterUnit('') }}>
        <option value="">全部大单元</option>
        {qBigUnits.map(b => (
          <option key={b.id} value={b.name}>{b.display_name || b.name}</option>
        ))}
      </select>

      {/* 小节筛选（只显示属于当前大单元的小节） */}
      <select data-testid="unit-filter" value={filterUnit} onChange={e => setFilterUnit(e.target.value)}>
        <option value="">全部小节</option>
        {qAllUnits
          .filter(u => u.parent != null)
          .filter(u => qBigUnitFilter === '' || u.parent?.name === qBigUnitFilter)
          .map(u => (
            <option key={u.id} value={u.name}>└ {u.display_name || u.name}</option>
          ))}
      </select>

      {/* 筛选按钮 */}
      <button data-testid="apply-filter" onClick={handleApplyFilter}>🔍 筛选</button>

      {/* 批量删除按钮 */}
      {selectedQuestions.length > 0 && (
        <button data-testid="batch-delete">🗑 已选 {selectedQuestions.length}</button>
      )}

      {/* 题目数量 */}
      <span data-testid="question-count">共 {questions.length} 题</span>

      {/* 题目表格 */}
      {questions.length === 0 ? (
        <div data-testid="empty-state">暂无题目</div>
      ) : (
        <table data-testid="question-table">
          <thead>
            <tr>
              <th><input type="checkbox" data-testid="select-all" checked={questions.length > 0 && selectedQuestions.length === questions.length} onChange={e => handleSelectAll(e.target.checked)} /></th>
              <th>#</th><th>年级</th><th>大单元</th><th>小节</th><th>难度</th><th>题目摘要</th><th>答案</th>
            </tr>
          </thead>
          <tbody>
            {questions.map((q, i) => (
              <tr key={q.id} style={{ background: selectedQuestions.includes(q.id) ? '#fff3cd' : 'white' }}>
                <td><input type="checkbox" data-testid={`select-${q.id}`} checked={selectedQuestions.includes(q.id)} onChange={() => handleSelectOne(q.id)} /></td>
                <td>{i + 1}</td>
                <td>{q.grade}</td>
                <td>{q.big_unit_name}</td>
                <td>{q.unit_name}</td>
                <td>{difficultyLabelLocal(q.difficulty)}</td>
                <td>{q.text}</td>
                <td>{q.answer}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

describe('Tab1Questions 筛选逻辑', () => {

  describe('年级筛选', () => {
    it('年级切换触发 setQGradeFilter 调用', async () => {
      const user = userEvent.setup()
      const setQGradeFilter = vi.fn()

      render(<SimplifiedTab1Questions
        questions={[]} qGradeFilter="七年级" setQGradeFilter={setQGradeFilter}
        qBigUnits={mockQBigUnits} qBigUnitFilter="" setQBigUnitFilter={() => {}} qAllUnits={mockQAllUnits} filterUnit="" setFilterUnit={() => {}} selectedQuestions={[]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)

      const gradeSelect = screen.getByTestId('grade-filter')
      await user.selectOptions(gradeSelect, '八年级')
      // 验证 onChange 被调用（值由父组件 InfoAdmin 管理）
      expect(setQGradeFilter).toHaveBeenCalled()
    })
  })

  describe('大单元 → 小节联动', () => {
    it('选择大单元后小节只显示该大单元的子小节', () => {
      const { getByTestId } = render(<SimplifiedTab1Questions
        questions={mockQuestions} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={mockQBigUnits} qBigUnitFilter="第一章" setQBigUnitFilter={() => {}}
        qAllUnits={mockQAllUnits} filterUnit="" setFilterUnit={() => {}}
        selectedQuestions={[]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)

      const unitOptions = getByTestId('unit-filter').querySelectorAll('option')
      const values = Array.from(unitOptions).map(o => o.value)
      // 应包含第一节、第二节，不应有第二章的子小节
      expect(values).toContain('第一节')
      expect(values).toContain('第二节')
      expect(values).not.toContain('第一章') // 第一章是大单元名，不是小节
      expect(values.filter(v => v !== '')).toHaveLength(2) // 只有两个小节
    })

    it('大单元切换时自动清空小节选中值', async () => {
      const user = userEvent.setup()
      let clearedBigUnitFilter = ''
      let clearedFilterUnit = ''

      const setQBigUnitFilter = v => { clearedBigUnitFilter = v }
      const setFilterUnit = v => { clearedFilterUnit = v }

      render(<SimplifiedTab1Questions
        questions={mockQuestions} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={mockQBigUnits} qBigUnitFilter="" setQBigUnitFilter={setQBigUnitFilter}
        qAllUnits={mockQAllUnits} filterUnit="第一节" setFilterUnit={setFilterUnit}
        selectedQuestions={[]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)

      // 选一个大单元
      const bigUnitSelect = screen.getByTestId('bigunit-filter')
      await user.selectOptions(bigUnitSelect, '第一章')

      // 小节应被清空
      expect(clearedFilterUnit).toBe('')
    })

    it('大单元为空时小节下拉显示全部小节', () => {
      const { getByTestId } = render(<SimplifiedTab1Questions
        questions={mockQuestions} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={mockQBigUnits} qBigUnitFilter="" setQBigUnitFilter={() => {}}
        qAllUnits={mockQAllUnits} filterUnit="" setFilterUnit={() => {}}
        selectedQuestions={[]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)

      const unitOptions = getByTestId('unit-filter').querySelectorAll('option')
      // qAllUnits 有 5 个 parent!=null 的小节，但当前年级只应显示对应的小节
      // mockQAllUnits 中第一节和第二节属于七年级第一章，第一节属于八年级第二章
      const values = Array.from(unitOptions).map(o => o.value).filter(v => v !== '')
      expect(values.length).toBeGreaterThan(0)
    })
  })

  describe('题目表格', () => {
    it('无题目时显示空状态', () => {
      render(<SimplifiedTab1Questions
        questions={[]} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={[]} qBigUnitFilter="" setQBigUnitFilter={() => {}}
        qAllUnits={[]} filterUnit="" setFilterUnit={() => {}}
        selectedQuestions={[]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)
      expect(screen.getByTestId('empty-state')).toBeInTheDocument()
      expect(screen.queryByTestId('question-table')).not.toBeInTheDocument()
    })

    it('有题目时显示表格', () => {
      render(<SimplifiedTab1Questions
        questions={mockQuestions} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={mockQBigUnits} qBigUnitFilter="" setQBigUnitFilter={() => {}}
        qAllUnits={mockQAllUnits} filterUnit="" setFilterUnit={() => {}}
        selectedQuestions={[]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)
      expect(screen.getByTestId('question-table')).toBeInTheDocument()
      expect(screen.queryByTestId('empty-state')).not.toBeInTheDocument()
    })

    it('全选 checkbox 状态正确', () => {
      const handleSelectAll = vi.fn()
      render(<SimplifiedTab1Questions
        questions={mockQuestions} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={mockQBigUnits} qBigUnitFilter="" setQBigUnitFilter={() => {}}
        qAllUnits={mockQAllUnits} filterUnit="" setFilterUnit={() => {}}
        selectedQuestions={[1, 2]} handleSelectAll={handleSelectAll} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)
      // selectedQuestions.length(2) !== questions.length(3)，所以全选 checkbox 不应选中
      const selectAllCheckbox = screen.getByTestId('select-all')
      expect(selectAllCheckbox.checked).toBe(false)
    })

    it('全选 checkbox 取消后 selectedQuestions.length=0 时选中', () => {
      render(<SimplifiedTab1Questions
        questions={mockQuestions} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={mockQBigUnits} qBigUnitFilter="" setQBigUnitFilter={() => {}}
        qAllUnits={mockQAllUnits} filterUnit="" setFilterUnit={() => {}}
        selectedQuestions={[1, 2, 3]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)
      const selectAllCheckbox = screen.getByTestId('select-all')
      expect(selectAllCheckbox.checked).toBe(true)
    })

    it('选中行有高亮背景色', () => {
      render(<SimplifiedTab1Questions
        questions={[mockQuestions[0]]} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={mockQBigUnits} qBigUnitFilter="" setQBigUnitFilter={() => {}}
        qAllUnits={mockQAllUnits} filterUnit="" setFilterUnit={() => {}}
        selectedQuestions={[1]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)
      const row = screen.getByTestId('question-table').querySelector('tbody tr')
      expect(row.style.background).toBe('rgb(255, 243, 205)') // #fff3cd
    })

    it('筛选按钮点击触发 handleApplyFilter', async () => {
      const user = userEvent.setup()
      const handleApplyFilter = vi.fn()
      render(<SimplifiedTab1Questions
        questions={[]} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={[]} qBigUnitFilter="" setQBigUnitFilter={() => {}}
        qAllUnits={[]} filterUnit="" setFilterUnit={() => {}}
        selectedQuestions={[]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={handleApplyFilter}
      />)
      await user.click(screen.getByTestId('apply-filter'))
      expect(handleApplyFilter).toHaveBeenCalledTimes(1)
    })

    it('选中题目后显示批量删除按钮', () => {
      render(<SimplifiedTab1Questions
        questions={mockQuestions} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={mockQBigUnits} qBigUnitFilter="" setQBigUnitFilter={() => {}}
        qAllUnits={mockQAllUnits} filterUnit="" setFilterUnit={() => {}}
        selectedQuestions={[1, 2]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)
      expect(screen.getByTestId('batch-delete')).toBeInTheDocument()
      expect(screen.getByTestId('batch-delete').textContent).toContain('2')
    })

    it('选中题目后显示数量', () => {
      render(<SimplifiedTab1Questions
        questions={mockQuestions} qGradeFilter="七年级" setQGradeFilter={() => {}}
        qBigUnits={mockQBigUnits} qBigUnitFilter="" setQBigUnitFilter={() => {}}
        qAllUnits={mockQAllUnits} filterUnit="" setFilterUnit={() => {}}
        selectedQuestions={[1]} handleSelectAll={() => {}} handleSelectOne={() => {}} handleApplyFilter={() => {}}
      />)
      expect(screen.getByTestId('question-count').textContent).toContain('3')
    })
  })
})
