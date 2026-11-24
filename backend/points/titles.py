"""称号体系：白省天骄十阶。

规则（2026-11-24 与教师定稿）：
1. 称号只由当前积分余额决定，达到阈值自动晋升，不需要发证书。
2. 跌破阈值会降级，但 `PointsAccount.peak_balance` 记住历史最高，
   前端用 `honor` 字段显示「曾为 X」——不公开羞辱，但荣誉留痕。
3. 阈值刻意压低前五级（50/150/300/500/800），保证开学两周内多数学生能破境一次。
4. 除境界外还有一个「道号」（疾风/智识/双修），按打字与小测的累计积分判定，
   回答的是「往哪个方向练」，与境界互不影响，见 `path_payload()`。

这是称号的唯一真源：前端只认 `icon` / `color` 两个 key，改名改阈值只动这里。
"""

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from django.conf import settings

ONE_DECIMAL = Decimal('0.1')
ZERO = Decimal('0')

# level 从 1 开始，按 min 升序；group 用于前端分层配色
TIERS = [
    {'level': 1, 'key': 'mengxue', 'name': '蒙学童生', 'min': 0, 'icon': 'star', 'color': '#94a3b8', 'group': '格物'},
    {'level': 2, 'key': 'gewu_apprentice', 'name': '格物学徒', 'min': 50, 'icon': 'star', 'color': '#60a5fa', 'group': '格物'},
    {'level': 3, 'key': 'gewu_master', 'name': '格物修士', 'min': 150, 'icon': 'sparkles', 'color': '#3b82f6', 'group': '格物'},
    {'level': 4, 'key': 'nanshan_walker', 'name': '南山行者', 'min': 300, 'icon': 'compass', 'color': '#8b5cf6', 'group': '南山'},
    {'level': 5, 'key': 'nanshan_sword', 'name': '南山执剑', 'min': 500, 'icon': 'sword', 'color': '#7c3aed', 'group': '南山'},
    {'level': 6, 'key': 'chuangxin_mage', 'name': '创新术士', 'min': 800, 'icon': 'flame', 'color': '#f97316', 'group': '创新'},
    {'level': 7, 'key': 'chuangxin_archmage', 'name': '创新大术士', 'min': 1200, 'icon': 'wand', 'color': '#ea580c', 'group': '创新'},
    {'level': 8, 'key': 'baisheng_chosen', 'name': '白省天骄', 'min': 1800, 'icon': 'crown', 'color': '#eab308', 'group': '白省'},
    {'level': 9, 'key': 'baisheng_sage', 'name': '白省圣贤', 'min': 2600, 'icon': 'gem', 'color': '#d97706', 'group': '白省'},
    {'level': 10, 'key': 'history_name', 'name': '校史留名', 'min': 3500, 'icon': 'trophy', 'color': '#b45309', 'group': '校史'},
]

TIERS_BY_KEY = {tier['key']: tier for tier in TIERS}


def quantize(value):
    if value is None:
        return ZERO
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(ONE_DECIMAL, rounding=ROUND_HALF_UP)


def tier_for(points):
    """按余额取当前境界；余额为负（异常态）时回落到第一阶。"""
    value = quantize(points)
    current = TIERS[0]
    for tier in TIERS:
        if value >= Decimal(tier['min']):
            current = tier
        else:
            break
    return current


def next_tier(tier):
    index = TIERS.index(tier)
    return TIERS[index + 1] if index + 1 < len(TIERS) else None


def title_payload(balance, peak=None):
    """给接口用的称号描述：当前境界 + 下一级进度 + 历史最高荣誉。"""
    value = quantize(balance)
    current = tier_for(value)
    payload = {
        'level': current['level'],
        'key': current['key'],
        'name': current['name'],
        'icon': current['icon'],
        'color': current['color'],
        'group': current['group'],
        'peak_level': current['level'],
        'next': None,
        'honor': None,
    }

    upcoming = next_tier(current)
    if upcoming:
        remaining = max(ZERO, quantize(Decimal(upcoming['min']) - value))
        payload['next'] = {
            'level': upcoming['level'],
            'name': upcoming['name'],
            'threshold': upcoming['min'],
            'remaining': str(remaining),
        }

    if peak is not None:
        peak_tier = tier_for(peak)
        payload['peak_level'] = peak_tier['level']
        if peak_tier['level'] > current['level']:
            payload['honor'] = {
                'level': peak_tier['level'],
                'name': peak_tier['name'],
                'icon': peak_tier['icon'],
                'color': peak_tier['color'],
            }
    return payload


def ladder_payload(balance, peak=None):
    """完整十阶天梯，供前端「点击称号」弹窗展示。

    每项额外带四个状态位，前端只按标记渲染，不自己算阈值：
    - reached：当前余额已达成（本阶及以下）；
    - current：当前所处的一阶；
    - was_reached：历史最高达到过（掉级后仍留痕）；
    - progress：仅当前阶有值，本阶门槛到下一阶门槛的完成比例（0~1）。
    """
    value = quantize(balance)
    current = tier_for(value)
    peak_value = quantize(peak) if peak is not None else value
    peak_level = tier_for(peak_value)['level']
    upcoming = next_tier(current)

    rows = []
    for tier in TIERS:
        row = {
            'level': tier['level'],
            'key': tier['key'],
            'name': tier['name'],
            'min': tier['min'],
            'icon': tier['icon'],
            'color': tier['color'],
            'group': tier['group'],
            'reached': tier['level'] <= current['level'],
            'current': tier['level'] == current['level'],
            'was_reached': tier['level'] <= peak_level,
            'remaining': None,
            'progress': None,
        }
        if row['current']:
            if not upcoming:
                row['progress'] = 1.0
            else:
                span = Decimal(upcoming['min']) - Decimal(tier['min'])
                done = value - Decimal(tier['min'])
                ratio = float(done / span) if span > 0 else 1.0
                row['progress'] = round(min(1.0, max(0.0, ratio)), 4)
                row['remaining'] = str(max(ZERO, quantize(Decimal(upcoming['min']) - value)))
        rows.append(row)
    return rows


# ── 道号（修行方向）──────────────────────────────────────────────────────
# 与境界正交：境界看总量，道号看结构（打字 vs 小测）。
# 双修门槛放在 settings 里，觉得"双修太难/太易"只改环境变量，不用动代码。
PATH_MIN = Decimal(str(getattr(settings, 'POINTS_PATH_MIN', '50')))
PATH_BALANCE_RATIO = Decimal(str(getattr(settings, 'POINTS_PATH_BALANCE_RATIO', '0.7')))

PATH_GALE = {
    'key': 'gale', 'label': '疾风', 'color': '#0ea5e9',
    'desc': '打字强于小测，手法是你的长板',
}
PATH_WISDOM = {
    'key': 'wisdom', 'label': '智识', 'color': '#8b5cf6',
    'desc': '小测强于打字，读题与判断是你的长板',
}
PATH_BALANCED = {
    'key': 'balanced', 'label': '双修', 'color': '#eab308',
    'desc': '打字与小测相差不到三成，两条路都在走',
}


def path_payload(typing_points, quiz_points):
    """按累计发放的打字/小测积分给一个道号。

    - 两边都不足 PATH_MIN：返回 None（新手不硬塞方向，前端不显示前缀）；
    - 两边都过线且弱者 ≥ 强者 × 0.7：双修；
    - 其余情况取较强的一边：打字 → 疾风，小测 → 智识。

    带 `upgrade` 时前端可以直接原样显示提示文案，不必自己再算一遍阈值。
    """
    typing = max(ZERO, quantize(typing_points))
    quiz = max(ZERO, quantize(quiz_points))
    if typing < PATH_MIN and quiz < PATH_MIN:
        return None

    strong = max(typing, quiz)
    weak = min(typing, quiz)
    if typing >= PATH_MIN and quiz >= PATH_MIN and weak >= strong * PATH_BALANCE_RATIO:
        payload = dict(PATH_BALANCED)
        payload['upgrade'] = None
        return payload

    payload = dict(PATH_GALE if typing >= quiz else PATH_WISDOM)
    weak_label = '小测' if payload['key'] == 'gale' else '打字'
    if weak < PATH_MIN:
        # 弱项还没起步，先让它过门槛，再谈双修（否则会算出"再得 210 分"这种离谱数字）
        need = quantize(PATH_MIN - weak)
        hint = f'{weak_label}再得 {need} 分迈过 {PATH_MIN:.0f} 分门槛，方向才看得出来'
    else:
        target = (strong * PATH_BALANCE_RATIO).quantize(ONE_DECIMAL, rounding=ROUND_CEILING)
        need = quantize(max(ZERO, target - weak))
        hint = f'{weak_label}再得 {need} 分即可双修'
    payload['upgrade'] = {'name': '双修', 'need': str(need), 'hint': hint}
    return payload


def path_options():
    """给前端展示「三种道号怎么来的」，避免规则只活在后端代码里。"""
    return [dict(PATH_GALE), dict(PATH_WISDOM), dict(PATH_BALANCED)]
