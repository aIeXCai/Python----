import {
  Compass, Crown, Flame, Gem, Sparkles, Star, Sword, Trophy, Wand2,
} from 'lucide-react'

/**
 * 称号图标映射：后端 `points/titles.py` 只给 icon key，前端在这里落成组件。
 * 与 TitleBadge 分开成独立文件，避免组件文件里混导出常量（热更新会失效）。
 */
const TITLE_ICONS = {
  star: Star,
  sparkles: Sparkles,
  compass: Compass,
  sword: Sword,
  flame: Flame,
  wand: Wand2,
  crown: Crown,
  gem: Gem,
  trophy: Trophy,
}

export default TITLE_ICONS
