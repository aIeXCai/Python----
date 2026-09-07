import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrictMode } from 'react'

const getProblemClassOptions = vi.fn()
const updateAdminProblem = vi.fn()
const updateProblemPublication = vi.fn()

vi.mock('../../../api/index.js', () => ({
  getProblemClassOptions: (...args) => getProblemClassOptions(...args),
  updateAdminProblem: (...args) => updateAdminProblem(...args),
  updateProblemPublication: (...args) => updateProblemPublication(...args),
}))

vi.mock('lucide-react', () => ({
  ChevronDown: () => <span>down</span>,
  X: () => <span>x</span>,
}))

import ProblemEditModal from './ProblemEditModal.jsx'

const baseProblem = {
  problem_id: 'scope-ui',
  title: '范围界面测试',
  difficulty: '入门',
  grade_tag: '',
  description: '题目描述',
  template_code: 'print("hello")',
  management_version: 3,
  publishing_suspended: false,
  can_edit_content: true,
  publication: { all_school: false, scopes: [] },
}

describe('ProblemEditModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getProblemClassOptions.mockImplementation(grade => Promise.resolve({ grade, classes: ['1', '2'] }))
    updateAdminProblem.mockResolvedValue({ ...baseProblem, management_version: 4 })
    updateProblemPublication.mockResolvedValue({
      management_version: 4,
      publishing_suspended: false,
      all_school: false,
      scopes: [
        { grade: '七年级', visible: true, all_classes: true, classes: [] },
        { grade: '八年级', visible: true, all_classes: true, classes: [] },
      ],
    })
  })

  it('Alex 先多选年级，再一键全选这些年级的全部班级', async () => {
    const user = userEvent.setup()
    const onSaved = vi.fn()
    render(
      <ProblemEditModal
        problem={baseProblem}
        user={{ is_superuser: true, managed_grade: '' }}
        onClose={vi.fn()}
        onSaved={onSaved}
      />,
    )

    expect(screen.getByText('全校可见')).toBeInTheDocument()
    await user.click(screen.getByText('请选择可见年级'))
    await user.click(screen.getByLabelText('七年级'))
    await user.click(screen.getByLabelText('八年级'))
    await waitFor(() => {
      expect(getProblemClassOptions).toHaveBeenCalledWith('七年级')
      expect(getProblemClassOptions).toHaveBeenCalledWith('八年级')
    })

    await user.click(screen.getByText('已选 2 个年级，点击配置班级'))
    await user.click(screen.getByLabelText('全选已选年级的所有班级'))
    await user.click(screen.getByRole('button', { name: '保存修改' }))

    expect(updateProblemPublication).toHaveBeenCalledWith('scope-ui', expect.objectContaining({
      expected_version: 3,
      all_school: false,
      scopes: expect.arrayContaining([
        expect.objectContaining({ grade: '七年级', visible: true, all_classes: true, classes: [] }),
        expect.objectContaining({ grade: '八年级', visible: true, all_classes: true, classes: [] }),
      ]),
    }))
    expect(onSaved).toHaveBeenCalled()
  })

  it('全校可见时无需展开年级和班级列表', async () => {
    const user = userEvent.setup()
    render(
      <ProblemEditModal
        problem={baseProblem}
        user={{ is_superuser: true, managed_grade: '' }}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('checkbox', { name: /^全校可见/ }))
    await user.click(screen.getByRole('button', { name: '保存修改' }))
    expect(getProblemClassOptions).not.toHaveBeenCalled()
    expect(updateProblemPublication).toHaveBeenCalledWith('scope-ui', expect.objectContaining({ all_school: true }))
  })

  it('可为题目选择适用年级标签并随内容一起保存', async () => {
    const user = userEvent.setup()
    render(
      <ProblemEditModal
        problem={baseProblem}
        user={{ is_superuser: true, managed_grade: '' }}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )
    await user.selectOptions(screen.getByLabelText('适用年级标签'), '九年级')
    await user.click(screen.getByRole('checkbox', { name: /^全校可见/ }))
    await user.click(screen.getByRole('button', { name: '保存修改' }))
    expect(updateAdminProblem).toHaveBeenCalledWith('scope-ui', expect.objectContaining({
      expected_version: 3,
      grade_tag: '九年级',
    }))
  })

  it('StrictMode 下已有可见范围时仍可修改标签并保存', async () => {
    const user = userEvent.setup()
    const problemWithScope = {
      ...baseProblem,
      publication: {
        all_school: false,
        scopes: [{ grade: '七年级', visible: true, all_classes: true, classes: [] }],
      },
    }
    render(
      <StrictMode>
        <ProblemEditModal
          problem={problemWithScope}
          user={{ is_superuser: true, managed_grade: '' }}
          onClose={vi.fn()}
          onSaved={vi.fn()}
        />
      </StrictMode>,
    )

    await user.selectOptions(screen.getByLabelText('适用年级标签'), '八年级')
    const saveButton = screen.getByRole('button', { name: '保存修改' })
    await waitFor(() => expect(saveButton).toBeEnabled())
    await user.click(saveButton)

    expect(updateAdminProblem).toHaveBeenCalledWith('scope-ui', expect.objectContaining({
      grade_tag: '八年级',
    }))
  })

  it('普通教师只管理自己的年级，未选班级时给出明确校验', async () => {
    const user = userEvent.setup()
    render(
      <ProblemEditModal
        problem={{ ...baseProblem, can_edit_content: false }}
        user={{ is_superuser: false, managed_grade: '七年级' }}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    )
    expect(screen.queryByText('全校可见')).not.toBeInTheDocument()
    expect(screen.getByText('我的管理年级')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: '八年级' })).not.toBeInTheDocument()
    await waitFor(() => expect(getProblemClassOptions).toHaveBeenCalledTimes(1))
    await user.click(screen.getByRole('checkbox', { name: /^对我管理的年级可见/ }))
    await user.click(screen.getByRole('button', { name: '保存修改' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('请为七年级选择可见班级')
    expect(updateProblemPublication).not.toHaveBeenCalled()
  })
})
