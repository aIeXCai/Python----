# -*- coding: utf-8 -*-
"""源文件共用构造器。每个模块用 make_rows(...) 拿到 R，再构建 ROWS。"""


def make_rows(ed, st, su, lic, mt_default="教材主题原创", ecs_default="已核对"):
    def R(ln, u, tt, ti, ge, p, d="L3 易", mt=None, ecs=None, note=""):
        return dict(ln=ln, u=u, tt=tt, ti=ti, ge=ge,
                    mt=mt or mt_default, d=d, p=p,
                    st=st, su=su, lic=lic, note=note,
                    ecs=ecs or ecs_default, ed=ed)
    return R
