import random


# 海拔和路线名称沿用已核对的登山 Demo。
PEAKS = (
    ('01-everest', '珠穆朗玛峰', 5400, 8848.86, '南坳 · 东南山脊'),
    ('02-k2', '乔戈里峰', 4970, 8611, '阿布鲁齐山脊'),
    ('03-kangchenjunga', '干城章嘉峰', 5475, 8586, '亚隆冰川南侧'),
    ('04-lhotse', '洛子峰', 5364, 8516, '洛子壁 · 洛子沟'),
    ('05-makalu', '马卡鲁峰', 5600, 8485, '西北山脊'),
    ('06-cho-oyu', '卓奥友峰', 4800, 8201, '西面 · 西山脊'),
    ('07-dhaulagiri-i', '道拉吉里Ⅰ峰', 4750, 8167, '东北山脊'),
    ('08-manaslu', '马纳斯卢峰', 4700, 8163, '东北面'),
    ('09-nanga-parbat', '南迦帕尔巴特峰', 4200, 8126, '迪亚米尔面 · 金斯霍弗'),
    ('10-annapurna-i', '安纳普尔纳Ⅰ峰', 4190, 8091, '北壁'),
    ('11-gasherbrum-i', '加舒尔布鲁木Ⅰ峰', 5100, 8080, '日本沟路线'),
    ('12-broad-peak', '布洛阿特峰', 4850, 8047, '西山脊'),
    ('13-gasherbrum-ii', '加舒尔布鲁木Ⅱ峰', 5000, 8035, '南面 · 西南山脊'),
    ('14-shishapangma', '希夏邦马峰', 5000, 8027, '北坡 · 经中峰至主峰'),
)


def select_peak_pair(exclude=()):
    keys = ('id', 'name', 'base_altitude', 'summit_altitude', 'route')
    candidates = [peak for peak in PEAKS if peak[0] not in exclude]
    return [
        dict(zip(keys, peak, strict=True), route_version='demo-v1')
        for peak in random.sample(candidates, 2)
    ]
