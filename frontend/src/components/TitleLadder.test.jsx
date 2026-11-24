/**
 * 进阶天梯弹窗：十阶倒排、当前阶进度、掉级留痕、点他人称号定位。
 * 运行: cd frontend && npx vitest run src/components/TitleLadder.test.jsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'

vi.mock('lucide-react', () => {
  const Stub = (props) => <span {...props} />
  return {
    Star: Stub, Sparkles: Stub, Compass: Stub, Sword: Stub, Flame: Stub,
    Wand2: Stub, Crown: Stub, Gem: Stub, Trophy: Stub,
    Check: Stub, Lock: Stub, X: Stub,
  }
})

import TitleLadder from './TitleLadder.jsx'

const TITLE = {
  level: 3, key: 'gewu_master', name: '格物修士', icon: 'sparkles',
  color: '#3b82f6', group: '格物', peak_level: 3,
  next: { level: 4, name: '南山行者', threshold: 300, remaining: '13.9' },
  honor: null,
}

function tier(level, name, min, extra = {}) {
  return {
    level, key: name, name, min, icon: 'star', color: '#60a5fa', group: '格物',
    reached: false, current: false, was_reached: false, remaining: null, progress: null,
    ...extra,
  }
}

// 用 4 阶简化，但保持与后端一致的状态位语义
const LADDER = [
  tier(1, '蒙学童生', 0, { reached: true, was_reached: true }),
  tier(2, '格物学徒', 50, { reached: true, was_reached: true }),
  tier(3, '格物修士', 150, {
    reached: true, current: true, was_reached: true, remaining: '13.9', progress: 0.9073,
  }),
  tier(4, '南山行者', 300),
]

describe('进阶天梯', () => {
  it('关闭时不渲染任何内容', () => {
    render(<TitleLadder open={false} onClose={() => {}} ladder={LADDER} title={TITLE} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('从高到低排列，并标出当前阶与晋升进度', () => {
    render(<TitleLadder open onClose={() => {}} ladder={LADDER} title={TITLE} />)

    const dialog = screen.getByRole('dialog')
    expect(dialog).toBeInTheDocument()

    // 只在阶梯列表里比较顺序，避开顶部摘要里的同名称号
    const list = within(dialog).getByRole('list')
    const names = within(list).getAllByText(/蒙学童生|格物学徒|格物修士|南山行者/)
      .map((node) => node.textContent)
    // 顶阶在上：南山行者在最前，蒙学童生在最后
    expect(names[0]).toBe('南山行者')
    expect(names[names.length - 1]).toBe('蒙学童生')

    expect(screen.getByText('当前')).toBeInTheDocument()
    expect(screen.getByText('再得 13.9 分晋升 南山行者')).toBeInTheDocument()

    const bar = screen.getByRole('progressbar')
    expect(bar).toHaveAttribute('aria-valuenow', '91')
  })

  it('未达成的阶段显示锁，掉级后的历史高阶显示「曾达」', () => {
    const demoted = {
      ...TITLE, level: 2, name: '格物学徒', peak_level: 5, honor: { level: 5, name: '南山执剑' },
    }
    const ladder = [
      tier(1, '蒙学童生', 0, { reached: true, was_reached: true }),
      tier(2, '格物学徒', 50, { reached: true, current: true, was_reached: true, progress: 0.5, remaining: '100' }),
      tier(5, '南山执剑', 500, { was_reached: true }),
      tier(6, '创新术士', 800),
    ]
    render(<TitleLadder open onClose={() => {}} ladder={ladder} title={demoted} />)

    expect(screen.getByText('曾达')).toBeInTheDocument()
    expect(screen.getAllByLabelText('未达成')).toHaveLength(1)
    expect(screen.getByText('曾为 南山执剑')).toBeInTheDocument()
  })

  it('点风云榜别人的称号，天梯上标出他所在的段位', () => {
    render(
      <TitleLadder
        open
        onClose={() => {}}
        ladder={LADDER}
        title={TITLE}
        focus={{ level: 4, label: '王雨桐' }}
      />,
    )
    expect(screen.getByText('王雨桐')).toBeInTheDocument()
    expect(screen.getByText('当前')).toBeInTheDocument()
  })

  it('展示三种道号，标出自己那一种与升级提示', () => {
    const PATHS = [
      { key: 'gale', label: '疾风', color: '#0ea5e9', desc: '打字强于小测，手法是你的长板' },
      { key: 'wisdom', label: '智识', color: '#8b5cf6', desc: '小测强于打字，读题与判断是你的长板' },
      { key: 'balanced', label: '双修', color: '#eab308', desc: '打字与小测相差不到三成，两条路都在走' },
    ]
    const title = {
      ...TITLE,
      path: {
        key: 'gale', label: '疾风', color: '#0ea5e9',
        upgrade: { name: '双修', need: '47.9', hint: '小测再得 47.9 分即可双修' },
      },
    }
    render(
      <TitleLadder
        open
        onClose={() => {}}
        ladder={LADDER}
        title={title}
        paths={PATHS}
        split={{ typing: '457.0', quiz: '272.0' }}
      />,
    )

    expect(screen.getByText('修行道号')).toBeInTheDocument()
    // 三种道号都列出来，双修不再只存在于方案里
    expect(screen.getByText('双修')).toBeInTheDocument()
    expect(screen.getByText('智识')).toBeInTheDocument()
    expect(screen.getByText(/累计 打字 457 · 小测 272/)).toBeInTheDocument()
    expect(screen.getByText(/小测再得 47.9 分即可双修/)).toBeInTheDocument()
  })

  it('按 Esc 与点遮罩都能关闭', () => {
    const onClose = vi.fn()
    const { container } = render(
      <TitleLadder open onClose={onClose} ladder={LADDER} title={TITLE} />,
    )

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)

    fireEvent.click(container.querySelector('.title-ladder-overlay'))
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
