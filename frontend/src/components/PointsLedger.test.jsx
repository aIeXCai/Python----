/**
 * 积分明细弹窗：流水渲染、正负号、分页加载、空态与错误态。
 * 运行: cd frontend && npx vitest run src/components/PointsLedger.test.jsx
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

vi.mock('lucide-react', () => {
  const Stub = () => <span aria-hidden="true" />
  return {
    Coins: Stub, Gift: Stub, Keyboard: Stub, Loader2: Stub,
    RotateCcw: Stub, SlidersHorizontal: Stub, Target: Stub, X: Stub,
  }
})

vi.mock('../api/points.js', () => ({ getMyPointsLedger: vi.fn() }))

import PointsLedger from './PointsLedger.jsx'
import { getMyPointsLedger } from '../api/points.js'

const ENTRY_TYPING = {
  id: 12, delta: '24.5', balance_after: '208.7', reason: 'typing_attempt',
  reason_label: '打字练习', note: '', time: '11-25 15:02',
}
const ENTRY_TEACHER = {
  id: 11, delta: '-20.0', balance_after: '184.2', reason: 'teacher_adjust',
  reason_label: '教师调整', note: '课堂扣分', time: '11-24 09:30',
}

describe('积分明细弹窗', () => {
  beforeEach(() => {
    getMyPointsLedger.mockReset()
  })

  it('open 为 false 时不渲染、也不请求接口', () => {
    render(<PointsLedger open={false} onClose={() => {}} />)
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(getMyPointsLedger).not.toHaveBeenCalled()
  })

  it('打开后拉取并逐条展示流水，正负号分开渲染', async () => {
    getMyPointsLedger.mockResolvedValue({
      entries: [ENTRY_TYPING, ENTRY_TEACHER], has_more: false, next_before: null,
    })
    render(<PointsLedger open onClose={() => {}} balance="208.7" />)

    expect(await screen.findByText('打字练习')).toBeInTheDocument()
    expect(screen.getByText('教师调整')).toBeInTheDocument()
    expect(screen.getByText('+24.5')).toBeInTheDocument()
    // 整数去掉多余的 .0，与积分卡同一套 formatPoints 口径
    expect(screen.getByText('−20')).toBeInTheDocument()
    expect(screen.getByText('课堂扣分')).toBeInTheDocument()
    expect(screen.getByText('余额 208.7 分')).toBeInTheDocument()
    expect(screen.getByText('11-25 15:02')).toBeInTheDocument()
    expect(getMyPointsLedger).toHaveBeenCalledWith({ limit: 20, before: null })
  })

  it('弹窗头部显示当前积分', async () => {
    getMyPointsLedger.mockResolvedValue({ entries: [ENTRY_TYPING], has_more: false })
    render(<PointsLedger open onClose={() => {}} balance="208.7" />)
    await screen.findByText('打字练习')
    expect(screen.getByText('208.7')).toBeInTheDocument()
  })

  it('没有记录时给出去哪里赚分的提示', async () => {
    getMyPointsLedger.mockResolvedValue({ entries: [], has_more: false })
    render(<PointsLedger open onClose={() => {}} />)
    expect(await screen.findByText(/还没有积分记录/)).toBeInTheDocument()
  })

  it('接口失败时显示错误而不是空白', async () => {
    getMyPointsLedger.mockRejectedValue(new Error('请求失败（500）'))
    render(<PointsLedger open onClose={() => {}} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('请求失败（500）')
  })

  it('有下一页时「加载更多」带游标追加，到底后提示结束', async () => {
    getMyPointsLedger
      .mockResolvedValueOnce({ entries: [ENTRY_TYPING], has_more: true, next_before: 12 })
      .mockResolvedValueOnce({ entries: [ENTRY_TEACHER], has_more: false, next_before: null })
    render(<PointsLedger open onClose={() => {}} />)

    const more = await screen.findByRole('button', { name: '加载更多' })
    fireEvent.click(more)

    expect(await screen.findByText('教师调整')).toBeInTheDocument()
    expect(getMyPointsLedger).toHaveBeenLastCalledWith({ limit: 20, before: 12 })
    expect(screen.getByText('打字练习')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '加载更多' })).toBeNull()
    expect(screen.getByText('已经到底了')).toBeInTheDocument()
  })

  it('按 Esc 关闭', async () => {
    const onClose = vi.fn()
    getMyPointsLedger.mockResolvedValue({ entries: [ENTRY_TYPING], has_more: false })
    render(<PointsLedger open onClose={onClose} />)
    await screen.findByText('打字练习')
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  })
})
