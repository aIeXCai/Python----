/* eslint-disable react-hooks/set-state-in-effect --
 * 打开弹窗即拉取第一页，setState 发生在 await 之后（异步），
 * 规则静态分析看不到 await 边界，与 AIQuizStatsTab 同一处理方式。 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Coins,
  Gift,
  Keyboard,
  Loader2,
  RotateCcw,
  SlidersHorizontal,
  Target,
  X,
} from 'lucide-react'
import { getMyPointsLedger } from '../api/points.js'

const PAGE_SIZE = 20

const REASON_STYLE = {
  typing_attempt: { icon: Keyboard, color: '#5b8def' },
  quiz_best: { icon: Target, color: '#8b5cf6' },
  hex_redraw: { icon: RotateCcw, color: '#f59e0b' },
  hex_reward: { icon: Gift, color: '#ec4899' },
  teacher_adjust: { icon: SlidersHorizontal, color: '#0ea5e9' },
  teacher_reset: { icon: Coins, color: '#94a3b8' },
}

function formatPoints(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '0'
  return Number.isInteger(number) ? String(number) : number.toFixed(1)
}

function signedDelta(value) {
  const number = Number(value)
  if (!Number.isFinite(number) || number === 0) return '0'
  return `${number > 0 ? '+' : '−'}${formatPoints(Math.abs(number))}`
}

/**
 * 积分明细弹窗：只读流水，按时间倒序，游标分页「加载更多」。
 *
 * 数据来自 GET /api/points/ledger/。每次打开重新拉第一页，
 * 保证教师刚调整完、学生一打开就能看到最新一条。
 */
export default function PointsLedger({ open, onClose, balance = null }) {
  const closeRef = useRef(null)
  const [entries, setEntries] = useState([])
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const [hasMore, setHasMore] = useState(false)
  const [nextBefore, setNextBefore] = useState(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [wasOpen, setWasOpen] = useState(open)

  // 每次打开都从第一页重新拉：渲染期比对 open 变化后重置，
  // 避免先闪一屏上次的旧流水（在 effect 里 setState 会多一轮渲染）。
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) {
      setEntries([])
      setStatus('loading')
      setError('')
      setHasMore(false)
      setNextBefore(null)
      setLoadingMore(false)
    }
  }

  const fetchPage = useCallback(async (before = null) => {
    const data = await getMyPointsLedger({ limit: PAGE_SIZE, before })
    setEntries(prev => (before ? [...prev, ...(data.entries || [])] : (data.entries || [])))
    setHasMore(Boolean(data.has_more))
    setNextBefore(data.next_before ?? null)
  }, [])

  useEffect(() => {
    if (!open) return undefined
    let cancelled = false

    fetchPage()
      .then(() => { if (!cancelled) setStatus('ready') })
      .catch(err => {
        if (cancelled) return
        setError(err?.message || '积分明细加载失败')
        setStatus('error')
      })

    return () => { cancelled = true }
  }, [open, fetchPage])

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

  const loadMore = async () => {
    if (loadingMore || !hasMore || !nextBefore) return
    setLoadingMore(true)
    try {
      await fetchPage(nextBefore)
    } catch (err) {
      setError(err?.message || '加载更多失败')
    } finally {
      setLoadingMore(false)
    }
  }

  if (!open) return null

  return (
    <div className="points-ledger-overlay" role="presentation" onClick={onClose}>
      <div
        className="points-ledger"
        role="dialog"
        aria-modal="true"
        aria-labelledby="points-ledger-heading"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="points-ledger-header">
          <div>
            <p className="points-ledger-kicker">每一分都有出处</p>
            <h2 id="points-ledger-heading">积分明细</h2>
          </div>
          <button
            ref={closeRef}
            type="button"
            className="points-ledger-close"
            onClick={onClose}
            aria-label="关闭积分明细"
          >
            <X size={18} />
          </button>
        </header>

        {balance != null ? (
          <div className="points-ledger-summary">
            <span className="points-ledger-summary-label">当前积分</span>
            <strong className="points-ledger-summary-value">{formatPoints(balance)}</strong>
            <span className="points-ledger-summary-unit">分</span>
          </div>
        ) : null}

        <div className="points-ledger-body">
          {status === 'loading' ? (
            <div className="points-ledger-state" role="status">
              <Loader2 size={18} className="points-ledger-spin" aria-hidden="true" />
              正在加载积分流水…
            </div>
          ) : status === 'error' ? (
            <div className="points-ledger-state is-error" role="alert">
              {error}
            </div>
          ) : entries.length === 0 ? (
            <div className="points-ledger-state">
              还没有积分记录。完成打字练习或小测后，这里会逐条记账。
            </div>
          ) : (
            <ol className="points-ledger-list">
              {entries.map(entry => {
                const style = REASON_STYLE[entry.reason] || { icon: Coins, color: '#667eea' }
                const Icon = style.icon
                const positive = Number(entry.delta) > 0
                return (
                  <li key={entry.id} className="points-ledger-row">
                    <span
                      className="points-ledger-icon"
                      style={{ color: style.color, background: `${style.color}14` }}
                      aria-hidden="true"
                    >
                      <Icon size={16} />
                    </span>

                    <span className="points-ledger-main">
                      <span className="points-ledger-line">
                        <span className="points-ledger-reason">{entry.reason_label}</span>
                        <span className="points-ledger-time">{entry.time}</span>
                      </span>
                      {entry.note && entry.note !== entry.reason_label ? (
                        <span className="points-ledger-note">{entry.note}</span>
                      ) : null}
                      <span className="points-ledger-after">
                        余额 {formatPoints(entry.balance_after)} 分
                      </span>
                    </span>

                    <span
                      className={`points-ledger-delta${positive ? ' is-plus' : ' is-minus'}`}
                    >
                      {signedDelta(entry.delta)}
                    </span>
                  </li>
                )
              })}
            </ol>
          )}

          {status === 'ready' && error ? (
            <p className="points-ledger-inline-error" role="alert">{error}</p>
          ) : null}
        </div>

        <footer className="points-ledger-footer">
          {hasMore ? (
            <button
              type="button"
              className="points-ledger-more"
              onClick={loadMore}
              disabled={loadingMore}
            >
              {loadingMore ? '加载中…' : '加载更多'}
            </button>
          ) : entries.length > 0 ? (
            <span className="points-ledger-end">已经到底了</span>
          ) : null}
        </footer>
      </div>
    </div>
  )
}
