import { Star } from 'lucide-react'
import TITLE_ICONS from './titleIcons.js'

/**
 * 境界徽记：把后端给的 icon key 映射成图标，颜色也由后端给，
 * 这样改称号表只动 points/titles.py 一处，前端不用跟着改。
 *
 * title.path（可选）是道号：疾风 / 智识 / 双修，显示在境界前面。
 * 同一套数据在卡片、风云榜、天梯里都用这一个组件，避免三处写法不一致。
 */
export default function TitleBadge({ title, size = 16, showName = true, showPath = true, className = '' }) {
  if (!title?.name) return null
  const Icon = TITLE_ICONS[title.icon] || Star
  const path = showPath ? title.path : null

  return (
    <span
      className={`title-badge${className ? ` ${className}` : ''}`}
      style={{ color: title.color || '#94a3b8' }}
    >
      <Icon size={size} aria-hidden="true" />
      {path?.label ? (
        <>
          <span
            className="title-path"
            style={{ color: path.color, borderColor: path.color }}
            title={path.desc || ''}
          >
            {path.label}
          </span>
          <span className="title-path-dot" aria-hidden="true">·</span>
        </>
      ) : null}
      {showName ? <span className="title-badge-name">{title.name}</span> : null}
    </span>
  )
}
