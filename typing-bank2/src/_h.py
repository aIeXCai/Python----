# -*- coding: utf-8 -*-
"""紧凑构造器：把每篇压成一行元组，减少样板。

中文用法：
    R = mkzh(ED, ST, SU, LIC, UNITS, d="L4 易")
    ROWS = R(
        (1, "1 观潮", "标题", "记叙文", ["段1", "段2"]),
    )
UNITS = {"第一单元 xxx": [1, 2, 3], ...}，按课次自动带出单元名。

英文用法：
    R = mken(ED, ST, SU, LIC, ecs="已核对", d="L3 易")
    ROWS = R(
        ("Unit 1 Helping at home", "家庭帮助与家务", "Title", "记叙", ["..."]),
    )
"""


def _pack(base, extra):
    """行元组可带第 6 个元素（dict）覆盖任意字段，用于单篇的公版来源与备注。"""
    if extra:
        base.update(extra)
    return base


def mkzh(ed, st, su, lic, units, d="L4 易", ecs="已核对", mt="教材主题原创"):
    def R(*rows):
        out = []
        for row in rows:
            ln, tt, ti, ge, p = row[:5]
            extra = row[5] if len(row) > 5 else None
            u = next((k for k, v in units.items() if ln in v), "单元待核对")
            out.append(_pack({"ln": ln, "u": u, "tt": tt, "ti": ti, "ge": ge, "mt": mt,
                              "d": d, "p": list(p), "st": st, "su": su,
                              "lic": lic, "ecs": ecs, "ed": ed}, extra))
        return out
    return R


def mken(ed, st, su, lic, ecs="已核对", d="L3 易", mt="教材主题原创"):
    def R(*rows):
        out = []
        for row in rows:
            u, tt, ti, ge, p = row[:5]
            extra = row[5] if len(row) > 5 else None
            out.append(_pack({"ln": "", "u": u, "tt": tt, "ti": ti, "ge": ge, "mt": mt,
                              "d": d, "p": list(p), "st": st, "su": su,
                              "lic": lic, "ecs": ecs, "ed": ed}, extra))
        return out
    return R
