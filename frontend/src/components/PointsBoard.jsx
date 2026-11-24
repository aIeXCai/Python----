import { Crown, RefreshCw } from 'lucide-react'
import TitleBadge from './TitleBadge.jsx'

function formatPoints(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '0'
  return Number.isInteger(number) ? String(number) : number.toFixed(1)
}

const MEDAL_CLASS = { 1: 'gold', 2: 'silver', 3: 'bronze' }

/**
 * 班级风云榜：本班按积分降序，标出称号与本人。
 * 数据来自 GET /api/points/leaderboard/，由父组件按 20 秒轮询刷新。
 * 打字/小测分项不占版面，只挂在积分数字的 title 上（鼠标悬停可见），
 * 行内空间留给姓名和称号，避免窄侧栏里挤成一团。
 * 点某人的称号会打开天梯图并标出他所在的段位（onOpenTitle）。
 */
export default function PointsBoard({ data, loading, onRefresh, updatedAt, onOpenTitle }) {
  const entries = data?.entries || []
  const me = data?.me

  return (
    <section className="points-board" aria-label="班级风云榜">
      <header className="points-board-header">
        <h2>
          <Crown size={18} aria-hidden="true" />
          班级风云榜
        </h2>
        <button type="button" className="points-board-refresh" onClick={onRefresh} aria-label="刷新榜单">
          <RefreshCw size={14} className={loading ? 'spin' : undefined} />
        </button>
      </header>

      {entries.length === 0 ? (
        <p className="points-board-empty">
          {loading ? '加载中…' : '还没有人获得积分，快去做一场打字或小测吧'}
        </p>
      ) : (
        <ol className="points-board-list">
          {entries.map((entry) => (
            <li
              key={entry.student_id}
              className={`points-board-row${entry.self ? ' is-self' : ''}`}
            >
              <span className={`points-board-rank ${MEDAL_CLASS[entry.rank] || ''}`}>
                {entry.rank}
              </span>
              <span className="points-board-person">
                <span className="points-board-name" title={entry.label}>
                  {entry.label}
                  {entry.self ? <em>我</em> : null}
                </span>
                {entry.title ? (
                  <button
                    type="button"
                    className="points-board-title-btn"
                    onClick={() => onOpenTitle?.(entry)}
                    title={`查看 ${entry.label} 的境界天梯`}
                  >
                    <TitleBadge title={entry.title} size={11} className="points-board-title" />
                  </button>
                ) : null}
              </span>
              <span
                className="points-board-score"
                title={`打字 ${formatPoints(entry.typing_points)} · 小测 ${formatPoints(entry.quiz_points)}`}
              >
                {formatPoints(entry.points)}
              </span>
            </li>
          ))}
        </ol>
      )}

      <footer className="points-board-footer">
        {me ? <span>我目前第 {me.rank} 名</span> : <span>共 {entries.length} 人</span>}
        <span>{updatedAt ? `${updatedAt} 更新` : '每 20 秒自动刷新'}</span>
      </footer>
    </section>
  )
}
