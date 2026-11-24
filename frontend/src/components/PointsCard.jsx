import { ChevronRight, Sparkles, Trophy } from 'lucide-react'
import TitleBadge from './TitleBadge.jsx'

function formatPoints(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '0'
  return Number.isInteger(number) ? String(number) : number.toFixed(1)
}

/**
 * 登录后最上方的积分卡片：个人积分 + 本班排名 + 当前境界。
 * data 为 GET /api/points/me/ 的返回；为空时显示占位。
 * 点称号可展开进阶天梯（onOpenLadder）。
 */
export default function PointsCard({ data, loading, onOpenLadder }) {
  const balance = formatPoints(data?.balance)
  const rank = data?.rank
  const classSize = data?.class_size
  const earned = formatPoints(data?.earned_total)
  const spent = formatPoints(data?.spent_total)
  const title = data?.title

  return (
    <section className="points-hero" aria-label="我的积分">
      <div className="points-hero-main">
        <div className="points-hero-icon" aria-hidden="true">
          <Sparkles size={26} />
        </div>
        <div>
          <p className="points-hero-label">我的积分</p>
          <p className="points-hero-value">
            {loading && !data ? '—' : balance}
            <span className="points-hero-unit">分</span>
          </p>
          {title ? (
            <div className="points-hero-title">
              <button
                type="button"
                className="points-hero-title-btn"
                onClick={onOpenLadder}
                title="点击查看进阶天梯"
                aria-label="查看进阶天梯"
              >
                <TitleBadge title={title} size={15} />
                <ChevronRight size={14} className="points-hero-title-hint" aria-hidden="true" />
              </button>
              <span className="points-hero-next">
                {title.next
                  ? `距 ${title.next.name} 还差 ${formatPoints(title.next.remaining)} 分`
                  : '已达顶阶'}
              </span>
            </div>
          ) : null}
          {title?.honor ? (
            <p className="points-hero-honor">曾为 {title.honor.name}</p>
          ) : null}
        </div>
      </div>

      <dl className="points-hero-stats">
        <div>
          <dt>积分排名</dt>
          <dd>
            {rank ? (
              <>
                <Trophy size={14} aria-hidden="true" /> 第 {rank} 名
              </>
            ) : '—'}
            {classSize ? <span className="points-hero-sub">共 {classSize} 人</span> : null}
          </dd>
        </div>
        <div>
          <dt>累计获得</dt>
          <dd>{earned}<span className="points-hero-sub">分</span></dd>
        </div>
        <div>
          <dt>已消耗</dt>
          <dd>{spent}<span className="points-hero-sub">分</span></dd>
        </div>
      </dl>
    </section>
  )
}
