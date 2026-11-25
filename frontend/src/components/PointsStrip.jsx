import { Sparkles, Trophy } from 'lucide-react'
import TitleBadge from './TitleBadge.jsx'

function formatPoints(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '0'
  return Number.isInteger(number) ? String(number) : number.toFixed(1)
}

/**
 * 选课页顶部的积分条：一登录就能看到自己的积分与境界。
 *
 * 与仪表盘里的 PointsCard 不同，这里只占一行——选课页的主角是三个课程入口，
 * 积分做「一眼可见」的摘要即可：余额、称号、班级排名、距下一阶还差多少。
 * data 为空（加载中/接口不可用）时不渲染任何数字占位，避免闪烁误导。
 */
export default function PointsStrip({ data, loading }) {
  if (!data) {
    if (!loading) return null
    return (
      <section className="points-strip points-strip--loading" aria-busy="true" aria-label="我的积分">
        <span className="points-strip-label">
          <Sparkles size={16} aria-hidden="true" /> 我的积分
        </span>
        <span className="points-strip-loading">载入中…</span>
      </section>
    )
  }

  const title = data.title
  const rank = data.rank
  const classSize = data.class_size
  const next = title?.next

  return (
    <section className="points-strip" aria-label="我的积分">
      <span className="points-strip-label">
        <Sparkles size={16} aria-hidden="true" /> 我的积分
      </span>
      <span className="points-strip-value">
        {formatPoints(data.balance)}
        <span className="points-strip-unit">分</span>
      </span>

      {title ? (
        <span className="points-strip-badge">
          <TitleBadge title={title} size={15} />
        </span>
      ) : null}

      {rank ? (
        <span className="points-strip-meta">
          <Trophy size={14} aria-hidden="true" /> 班级第 {rank} 名
          {classSize ? <span className="points-strip-sub">共 {classSize} 人</span> : null}
        </span>
      ) : null}

      {next ? (
        <span className="points-strip-next">
          距 {next.name} 还差 {formatPoints(next.remaining)} 分
        </span>
      ) : title ? (
        <span className="points-strip-next">已达顶阶</span>
      ) : null}
    </section>
  )
}
