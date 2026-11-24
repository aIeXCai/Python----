import { useEffect, useRef } from 'react'
import { Check, Lock, X } from 'lucide-react'
import TitleBadge from './TitleBadge.jsx'
import TITLE_ICONS from './titleIcons.js'

function formatPoints(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '0'
  return Number.isInteger(number) ? String(number) : number.toFixed(1)
}

/**
 * 进阶天梯弹窗：十阶称号从高到低倒排，起点在最下方，视觉上就是向上攀登。
 *
 * 数据全部来自 GET /api/points/me/ 的 `ladder`（与积分同一快照），
 * 前端不算阈值，只按 reached / current / was_reached 三个标记渲染。
 *
 * focus 可选：点风云榜上别人的称号时传入 { level, label }，
 * 那一行会额外标出「谁的段位」，自己所在的那行仍然是「当前」。
 */
export default function TitleLadder({
  open,
  onClose,
  ladder = [],
  title = null,
  focus = null,
  split = null,
  paths = [],
}) {
  const closeRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKeyDown)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [open, onClose])

  if (!open || !title || ladder.length === 0) return null

  const rows = [...ladder].sort((a, b) => b.level - a.level)

  return (
    <div className="title-ladder-overlay" role="presentation" onClick={onClose}>
      <div
        className="title-ladder"
        role="dialog"
        aria-modal="true"
        aria-labelledby="title-ladder-heading"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="title-ladder-header">
          <div>
            <p className="title-ladder-kicker">白省天骄 · 进阶天梯</p>
            <h2 id="title-ladder-heading">我的境界</h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="title-ladder-close"
            onClick={onClose}
            aria-label="关闭天梯"
          >
            <X size={18} />
          </button>
        </header>

        <div className="title-ladder-summary">
          <TitleBadge title={title} size={20} />
          <span className="title-ladder-summary-next">
            {title.next
              ? `距 ${title.next.name} 还差 ${formatPoints(title.next.remaining)} 分`
              : '已达顶阶'}
          </span>
          {title.honor ? <span className="title-ladder-summary-honor">曾为 {title.honor.name}</span> : null}
        </div>

        <ol className="title-ladder-list">
          {rows.map((row) => {
            const Icon = TITLE_ICONS[row.icon] || TITLE_ICONS.star
            const isFocus = Boolean(focus) && focus.level === row.level && !row.current
            const classes = [
              'title-ladder-row',
              row.reached ? 'is-reached' : 'is-locked',
              row.current ? 'is-current' : '',
              row.was_reached && !row.reached ? 'is-honor' : '',
              isFocus ? 'is-focus' : '',
            ].filter(Boolean).join(' ')
            const percent = Math.round((row.progress || 0) * 100)

            return (
              <li
                key={row.level}
                className={classes}
                style={{ '--tier-color': row.color }}
              >
                <span className="title-ladder-rung" aria-hidden="true" />
                <span
                  className="title-ladder-icon"
                  style={{ color: row.reached ? row.color : '#c3cbd6' }}
                  aria-hidden="true"
                >
                  <Icon size={16} />
                </span>

                <span className="title-ladder-main">
                  <span className="title-ladder-line">
                    <span
                      className="title-ladder-name"
                      style={{ color: row.reached ? row.color : '#9aa5b1' }}
                    >
                      {row.name}
                    </span>
                    <span className="title-ladder-min">{formatPoints(row.min)} 分</span>

                    {row.current ? (
                      <span className="title-ladder-tag is-me">当前</span>
                    ) : isFocus ? (
                      <span className="title-ladder-tag is-focus">{focus.label || 'TA'}</span>
                    ) : row.reached ? (
                      <Check size={13} className="title-ladder-check" aria-label="已达成" />
                    ) : row.was_reached ? (
                      <span className="title-ladder-tag is-honor">曾达</span>
                    ) : (
                      <Lock size={12} className="title-ladder-lock" aria-label="未达成" />
                    )}
                  </span>

                  {row.current ? (
                    <>
                      <span
                        className="title-ladder-progress"
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={percent}
                        aria-label={`晋升进度 ${percent}%`}
                      >
                        <span
                          className="title-ladder-progress-fill"
                          style={{ width: `${percent}%`, background: title.color }}
                        />
                      </span>
                      <span className="title-ladder-hint">
                        {title.next
                          ? `再得 ${formatPoints(row.remaining)} 分晋升 ${title.next.name}`
                          : '已至最高境界'}
                      </span>
                    </>
                  ) : null}
                </span>
              </li>
            )
          })}
        </ol>

        {paths.length > 0 ? (
          <section className="title-ladder-paths" aria-label="修行道号">
            <h3>修行道号</h3>
            <div className="title-ladder-path-grid">
              {paths.map((item) => {
                const active = title.path?.key === item.key
                return (
                  <div
                    key={item.key}
                    className={`title-ladder-path${active ? ' is-active' : ''}`}
                    style={{ '--path-color': item.color }}
                  >
                    <span className="title-ladder-path-label">{item.label}</span>
                    <span className="title-ladder-path-desc">{item.desc}</span>
                  </div>
                )
              })}
            </div>
            <p className="title-ladder-path-now">
              {split
                ? `累计 打字 ${formatPoints(split.typing)} · 小测 ${formatPoints(split.quiz)}`
                : null}
              <span className="title-ladder-path-arrow" aria-hidden="true">→</span>
              <strong style={{ color: title.path?.color || '#94a3b8' }}>
                {title.path?.label || '还没有道号'}
              </strong>
              {title.path?.upgrade ? `；${title.path.upgrade.hint}` : ''}
              {title.path && !title.path.upgrade ? '；保持两条路都在走' : ''}
            </p>
          </section>
        ) : null}

        <footer className="title-ladder-footer">
          称号按当前积分实时判定；积分减少会掉级，但「曾达」会留痕。
        </footer>
      </div>
    </div>
  )
}
