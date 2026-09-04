/**
 * Tab2Sessions 小测列表测试
 * 运行: cd frontend && npx vitest run src/pages/teacher/tabs/Tab2Sessions.test.jsx
 */
import { beforeEach, describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('lucide-react', () => ({
  ClipboardList: () => <span data-testid="icon-clipboard">ClipboardList</span>,
  Plus: () => <span data-testid="icon-plus">Plus</span>,
  Edit2: () => <span data-testid="icon-edit">Edit</span>,
  Trash2: () => <span data-testid="icon-trash">Trash</span>,
  Play: () => <span data-testid="icon-play">Play</span>,
  X: () => <span data-testid="icon-x">X</span>,
  ChevronDown: () => <span data-testid="icon-chevron-down">ChevronDown</span>,
  Save: () => <span data-testid="icon-save">Save</span>,
}))

import Tab2Sessions from './Tab2Sessions.jsx'

const mockSessions = [
  { id: 1, title: '第一章小测', grade: '七年级', visible_classes: [], status: 'open', submission_count: 0, time_limit: 30, num_questions: 5, big_unit_names: ['第一章'], section_names: ['第一节'] },
  { id: 2, title: '第二章小测', grade: '七年级', visible_classes: ['1', '3'], status: 'closed', submission_count: 3, time_limit: 45, num_questions: 8, big_unit_names: ['第二章'], section_names: ['第一节'] },
]

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

const defaultProps = {
  sessions: mockSessions,
  sLoading: false,
  unitGradeFilter: '七年级',
  openNewSession: vi.fn(),
  openEditSession: vi.fn(),
  deleteSession: vi.fn(),
  handleStartSession: vi.fn(),
  handleEndSession: vi.fn(),
  sModal: { open: false, mode: 'create', data: null },
  setSModal: vi.fn(),
  sForm: { name: '', grade: '七年级', duration: 30, units: [], question_count: 5 },
  setSForm: vi.fn(),
  sMsg: { type: '', text: '' },
  handleSaveSession: vi.fn(),
  sSaving: false,
}

// 简化版 SessionModal
function SessionModal({ sModal, setSModal, sForm, setSForm, sMsg, handleSaveSession, sSaving }) {
  return (
    <div data-testid="session-modal">
      <h2>{sModal.mode === 'edit' ? '编辑小测' : '新建小测'}</h2>
      {sMsg.text && <div data-testid="s-msg">{sMsg.text}</div>}
      <form onSubmit={handleSaveSession}>
        <input
          data-testid="name-input"
          value={sForm.name}
          onChange={e => setSForm(p => ({ ...p, name: e.target.value }))}
          placeholder="小测名称"
        />
        <select
          data-testid="grade-select"
          value={sForm.grade}
          onChange={e => setSForm(p => ({ ...p, grade: e.target.value }))}
        >
          <option value="七年级">七年级</option>
          <option value="八年级">八年级</option>
        </select>
        <input
          data-testid="duration-input"
          type="number"
          value={sForm.duration}
          onChange={e => setSForm(p => ({ ...p, duration: parseInt(e.target.value) }))}
        />
        <input
          data-testid="count-input"
          type="number"
          value={sForm.question_count}
          onChange={e => setSForm(p => ({ ...p, question_count: parseInt(e.target.value) }))}
        />
        <button type="submit" disabled={sSaving || !sForm.units?.length} data-testid="submit-btn">
          {sSaving ? '保存中...' : '保存'}
        </button>
        <button type="button" onClick={() => setSModal({ open: false })} data-testid="cancel-btn">取消</button>
      </form>
    </div>
  )
}

// 简化版 Tab2Sessions（内联关键逻辑）
function SimplifiedTab2Sessions(props) {
  const sessions = props.sessions
  const sLoading = props.sLoading

  return (
    <div data-testid="tab2-sessions">
      <div data-testid="session-count">共 {sessions.length} 场小测</div>
      <button data-testid="new-session-btn" onClick={props.openNewSession}>+ 新建小测</button>

      {sLoading ? (
        <div data-testid="loading">加载中...</div>
      ) : sessions.length === 0 ? (
        <div data-testid="empty-state">暂无小测</div>
      ) : (
        <table data-testid="session-table">
          <thead>
            <tr>
              <th>#</th><th>名称</th><th>年级</th><th>状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s, i) => {
              const status = s.status === 'open'
                ? { label: '进行中', color: '#38ef7d' }
                : s.status === 'closed'
                  ? { label: `已关闭(${s.submission_count})`, color: '#667eea' }
                  : { label: '未发布', color: '#888' }
              return (
                <tr key={s.id} data-testid={`row-${s.id}`}>
                  <td>{i + 1}</td>
                  <td>{s.title}</td>
                  <td>{s.grade}</td>
                  <td data-testid={`status-${s.id}`} style={{ color: status.color }}>{status.label}</td>
                  <td>
                    {s.status === 'open' ? (
                      <button data-testid={`end-btn-${s.id}`} onClick={() => props.handleEndSession(s.id)}>结束</button>
                    ) : (
                      <button data-testid={`start-btn-${s.id}`} onClick={() => props.handleStartSession(s.id)}>
                        {s.status === 'closed' ? '重新开放' : '开始'}
                      </button>
                    )}
                    <button data-testid={`edit-btn-${s.id}`} onClick={() => props.openEditSession(s)}>编辑</button>
                    <button data-testid={`delete-btn-${s.id}`} onClick={() => props.deleteSession(s)}>删除</button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      {props.sModal.open && (
        <SessionModal
          sModal={props.sModal} setSModal={props.setSModal}
          sForm={props.sForm} setSForm={props.setSForm}
          sMsg={props.sMsg} handleSaveSession={props.handleSaveSession}
          sSaving={props.sSaving}
        />
      )}
    </div>
  )
}

describe('Tab2Sessions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetch.mockImplementation(async (url) => ({
      ok: true,
      json: async () => String(url).includes('/classes/')
        ? { grade: '七年级', classes: ['1', '2', '3'] }
        : [],
    }))
  })

  it('真实列表显示全年级或指定的多个班级', () => {
    render(<Tab2Sessions {...defaultProps} />)
    expect(screen.getByText('全年级')).toBeInTheDocument()
    expect(screen.getByText('1班、3班')).toBeInTheDocument()
  })

  it('真实弹窗支持班级多选和全年级全选', async () => {
    function Harness() {
      const [form, setForm] = useState({
        name: '班级范围测试', grade: '七年级', units: [1], duration: 30,
        question_count: 5, difficulty_ratio: { easy: 5 }, visible_classes: [],
      })
      return <Tab2Sessions {...defaultProps} sessions={[]} sModal={{ open: true, mode: 'create', data: null }} sForm={form} setSForm={setForm} />
    }

    const user = userEvent.setup()
    render(<Harness />)
    const dropdown = screen.getByRole('button', { name: '选择可见班级' })
    expect(dropdown).toHaveTextContent('全年级（全选）')
    expect(dropdown).toHaveAttribute('aria-expanded', 'false')

    await user.click(dropdown)
    expect(dropdown).toHaveAttribute('aria-expanded', 'true')
    const classOne = await screen.findByRole('checkbox', { name: '1班' })
    const classTwo = screen.getByRole('checkbox', { name: '2班' })
    const allGrades = screen.getByRole('checkbox', { name: '全年级' })
    expect(allGrades).toBeChecked()

    await user.click(classOne)
    await user.click(classTwo)
    expect(classOne).toBeChecked()
    expect(classTwo).toBeChecked()
    expect(allGrades).not.toBeChecked()
    expect(dropdown).toHaveTextContent('1班、2班')

    await user.click(allGrades)
    await waitFor(() => expect(allGrades).toBeChecked())
    expect(classOne).not.toBeChecked()
    expect(classTwo).not.toBeChecked()
    expect(dropdown).toHaveTextContent('全年级（全选）')
  })

  it('真实列表允许教师重新开放已关闭的小测', async () => {
    const user = userEvent.setup()
    render(<Tab2Sessions {...defaultProps} />)
    expect(screen.getByText('已关闭(3)')).toBeInTheDocument()
    const reopenButton = screen.getByRole('button', { name: /重新开放/ })
    await user.click(reopenButton)
    expect(defaultProps.handleStartSession).toHaveBeenCalledWith(2)
  })

  it('进行中和已关闭的小测都提供编辑与删除', async () => {
    const user = userEvent.setup()
    render(<Tab2Sessions {...defaultProps} />)

    await user.click(screen.getByRole('button', { name: '编辑第一章小测' }))
    await user.click(screen.getByRole('button', { name: '删除第二章小测' }))

    expect(defaultProps.openEditSession).toHaveBeenCalledWith(mockSessions[0])
    expect(defaultProps.deleteSession).toHaveBeenCalledWith(mockSessions[1])
  })

  it('空状态显示暂无小测', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} sessions={[]} />)
    expect(screen.getByTestId('empty-state')).toBeInTheDocument()
  })

  it('加载中显示加载状态', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} sLoading={true} />)
    expect(screen.getByTestId('loading')).toBeInTheDocument()
  })

  it('表格显示小测数量', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} />)
    expect(screen.getByTestId('session-count').textContent).toBe('共 2 场小测')
  })

  it('进行中的小测显示结束按钮', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} />)
    expect(screen.getByTestId('end-btn-1')).toBeInTheDocument()
    expect(screen.queryByTestId('start-btn-1')).not.toBeInTheDocument()
  })

  it('已关闭的小测显示重新开放按钮', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} />)
    expect(screen.getByTestId('start-btn-2')).toBeInTheDocument()
    expect(screen.getByTestId('start-btn-2')).toHaveTextContent('重新开放')
    expect(screen.queryByTestId('end-btn-2')).not.toBeInTheDocument()
  })

  it('点击开始触发 handleStartSession', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab2Sessions {...defaultProps} />)
    await user.click(screen.getByTestId('start-btn-2'))
    expect(defaultProps.handleStartSession).toHaveBeenCalledWith(2)
  })

  it('点击结束触发 handleEndSession', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab2Sessions {...defaultProps} />)
    await user.click(screen.getByTestId('end-btn-1'))
    expect(defaultProps.handleEndSession).toHaveBeenCalledWith(1)
  })

  it('点击编辑触发 openEditSession', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab2Sessions {...defaultProps} />)
    await user.click(screen.getByTestId('edit-btn-1'))
    expect(defaultProps.openEditSession).toHaveBeenCalledWith(mockSessions[0])
  })

  it('点击新建小测触发 openNewSession', async () => {
    const user = userEvent.setup()
    render(<SimplifiedTab2Sessions {...defaultProps} />)
    await user.click(screen.getByTestId('new-session-btn'))
    expect(defaultProps.openNewSession).toHaveBeenCalled()
  })

  it('SessionModal 编辑模式显示正确标题', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} sModal={{ open: true, mode: 'edit', data: mockSessions[0] }} />)
    expect(screen.getByText('编辑小测')).toBeInTheDocument()
  })

  it('SessionModal 新建模式显示正确标题', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} sModal={{ open: true, mode: 'create', data: null }} />)
    expect(screen.getByText('新建小测')).toBeInTheDocument()
  })

  it('SessionModal 成功消息显示', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} sModal={{ open: true }} sMsg={{ type: 'success', text: '保存成功' }} />)
    expect(screen.getByTestId('s-msg').textContent).toBe('保存成功')
  })

  it('SessionModal 保存按钮 disabled 状态（无 units）', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} sModal={{ open: true }} sForm={{ ...defaultProps.sForm, units: [] }} />)
    expect(screen.getByTestId('submit-btn')).toBeDisabled()
  })

  it('SessionModal 有 units 时保存按钮 enabled', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} sModal={{ open: true }} sForm={{ ...defaultProps.sForm, units: [1, 2] }} />)
    expect(screen.getByTestId('submit-btn')).not.toBeDisabled()
  })

  it('SessionModal sSaving 时保存按钮显示加载文本', () => {
    render(<SimplifiedTab2Sessions {...defaultProps} sModal={{ open: true }} sSaving={true} sForm={{ ...defaultProps.sForm, units: [1] }} />)
    expect(screen.getByTestId('submit-btn').textContent).toBe('保存中...')
  })
})
