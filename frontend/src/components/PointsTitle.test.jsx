/**
 * 称号（白省天骄十阶）在学生端的渲染：积分卡片 + 风云榜。
 * 运行: cd frontend && npx vitest run src/components/PointsTitle.test.jsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

vi.mock('lucide-react', () => {
  const Stub = () => <span />
  return {
    Star: Stub, Sparkles: Stub, Trophy: Stub, Compass: Stub, Sword: Stub,
    Flame: Stub, Wand2: Stub, Crown: Stub, Gem: Stub, RefreshCw: Stub,
    ChevronRight: Stub,
  }
})

import PointsCard from './PointsCard.jsx'
import PointsBoard from './PointsBoard.jsx'

const MERIDIAN = {
  level: 3, key: 'gewu_master', name: '格物修士', icon: 'sparkles',
  color: '#3b82f6', group: '格物',
  path: { key: 'gale', label: '疾风', color: '#0ea5e9', desc: '打字强于小测', upgrade: null },
  next: { level: 4, name: '南山行者', threshold: 300, remaining: '13.9' },
  honor: null,
}

describe('积分卡片上的称号', () => {
  it('显示当前境界与下一级差距', () => {
    render(
      <PointsCard
        data={{ balance: '286.1', rank: 15, class_size: 21, earned_total: '286.1', spent_total: '0.0', title: MERIDIAN }}
      />,
    )
    expect(screen.getByText('格物修士')).toBeInTheDocument()
    expect(screen.getByText(/距 南山行者 还差 13.9 分/)).toBeInTheDocument()
  })

  it('称号前显示道号', () => {
    render(
      <PointsCard
        data={{ balance: '286.1', rank: 15, class_size: 21, title: MERIDIAN }}
      />,
    )
    expect(screen.getByText('疾风')).toBeInTheDocument()
    expect(screen.getByText('格物修士')).toBeInTheDocument()
  })

  it('掉级后显示「曾为」荣誉', () => {
    render(
      <PointsCard
        data={{
          balance: '100', rank: 20, class_size: 21,
          title: {
            ...MERIDIAN, name: '格物学徒', level: 2,
            honor: { level: 5, name: '南山执剑', icon: 'sword', color: '#7c3aed' },
          },
        }}
      />,
    )
    expect(screen.getByText('格物学徒')).toBeInTheDocument()
    expect(screen.getByText('曾为 南山执剑')).toBeInTheDocument()
  })

  it('点称号可以打开进阶天梯', () => {
    const onOpenLadder = vi.fn()
    render(
      <PointsCard
        data={{ balance: '286.1', rank: 15, class_size: 21, title: MERIDIAN }}
        onOpenLadder={onOpenLadder}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /查看进阶天梯/ }))
    expect(onOpenLadder).toHaveBeenCalledTimes(1)
  })
})

describe('风云榜上的称号', () => {
  it('每行在姓名下显示称号', () => {
    render(
      <PointsBoard
        data={{
          entries: [
            {
              student_id: 1, label: '王雨桐', points: '729.0', typing_points: '457.0',
              quiz_points: '272.0', rank: 1, self: false,
              title: { level: 5, name: '南山执剑', icon: 'sword', color: '#7c3aed' },
            },
          ],
          me: null,
        }}
      />,
    )
    expect(screen.getByText('王雨桐')).toBeInTheDocument()
    expect(screen.getByText('南山执剑')).toBeInTheDocument()
  })

  it('点榜单里的称号会把那个人交给天梯弹窗', () => {
    const onOpenTitle = vi.fn()
    render(
      <PointsBoard
        data={{
          entries: [
            {
              student_id: 1, label: '王雨桐', points: '729.0', typing_points: '457.0',
              quiz_points: '272.0', rank: 1, self: false,
              title: { level: 5, name: '南山执剑', icon: 'sword', color: '#7c3aed' },
            },
          ],
          me: null,
        }}
        onOpenTitle={onOpenTitle}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /南山执剑/ }))
    expect(onOpenTitle).toHaveBeenCalledWith(expect.objectContaining({ label: '王雨桐' }))
  })
})

describe('风云榜的行内容', () => {
  it('只显示总分，打字/小测分项收进悬停提示，避免挤占版面', () => {
    render(
      <PointsBoard
        data={{
          entries: [
            {
              student_id: 1, label: '王雨桐', points: '729.0', typing_points: '457.0',
              quiz_points: '272.0', rank: 1, self: false, title: null,
            },
          ],
          me: null,
        }}
      />,
    )
    expect(screen.getByText('729')).toBeInTheDocument()
    expect(screen.queryByText(/打字 /)).not.toBeInTheDocument()
    expect(screen.queryByText(/小测 /)).not.toBeInTheDocument()
    expect(screen.getByTitle('打字 457 · 小测 272')).toBeInTheDocument()
  })
})
