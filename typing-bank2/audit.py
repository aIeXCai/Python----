# -*- coding: utf-8 -*-
"""按审阅笔记的五类口径审计题库，供修订前后比对。

用法：
    python3 audit.py            # 打印汇总与待修清单
    python3 audit.py --csv 路径  # 另存为与审阅笔记同格式的 CSV
"""
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")

SPEED = {"zh": {3: 15, 4: 17, 5: 19, 6: 22, 7: 26, 8: 30},
         "en": {3: 50, 4: 58, 5: 66, 6: 76, 7: 90, 8: 100}}
BAND = {"zh": {3: (80, 120), 4: (95, 140), 5: (110, 155),
               6: (128, 178), 7: (148, 202), 8: (165, 225)},
        "en": {3: (250, 350), 4: (290, 390), 5: (330, 435),
               6: (380, 485), 7: (450, 550), 8: (500, 615)}}

# 可作为公版原文底本的域名
TEXT_HOSTS = ("ctext.org", "wikisource.org", "news.cn")

def load():
    return [json.loads(l) for l in open(os.path.join(DIST, "全部.jsonl"), encoding="utf-8")]


def audit(rows):
    out = []
    for r in rows:
        lg, g = r["language"], r["grade"]
        n = r["han_character_count"] if lg == "zh" else r["english_character_count"]
        lo, hi = BAND[lg][g]
        sp = SPEED[lg][g]
        minutes = round(n / sp, 2)
        su = r["source_url"]
        flags = {
            # 只卡下限：偏长不算问题（不强求打完），偏短才是要续篇的
            "篇幅偏短": int(n < lo),
            "按假设速度不足5分钟": int(minutes < 5),
            "复核教材版本": int(r["edition_check_status"] != "已核对"),
            # 公版原作必须有具体文本页；首页、教材目录页都不算
            "复核公版来源": int(r["material_type"] == "公版原作"
                          and (su.rstrip("/") in ("https://ctext.org/zh", "https://ctext.org")
                               or not any(h in su for h in TEXT_HOSTS))),
            # 挂公版标签但授权字段没写公版，属来源类别误标
            "已确认来源类别需修": int(r["material_type"] == "公版原作"
                              and "公版" not in r["license_or_permission"]
                              and "公有领域" not in r["license_or_permission"]),
        }
        if any(flags.values()):
            out.append({
                "ID": r["id"], "语言": lg, "年级": g, "学期": r["semester"],
                "标题": r["title"], "正文计量": n, "目标下限": lo, "目标上限": hi,
                "预计打完分钟": minutes, **flags,
            })
    return out


def main():
    rows = load()
    out = audit(rows)
    print("全库 %d 条，待修 %d 条\n" % (len(rows), len(out)))
    for k in ("篇幅偏短", "按假设速度不足5分钟", "复核教材版本", "复核公版来源", "已确认来源类别需修"):
        sub = [x for x in out if x[k]]
        c = collections.Counter((x["语言"], x["年级"]) for x in sub)
        print("%-20s %3d 篇  %s" % (k, len(sub), dict(sorted(c.items()))))
    print()
    # 每篇还需要补多少字（偏长不再列出，只作参考计数）
    over = sum(1 for r in rows
               if (r["han_character_count"] if r["language"] == "zh" else r["english_character_count"])
               > BAND[r["language"]][r["grade"]][1])
    print("参考：超出舒适带上限 %d 篇（偏长不报错，不影响计时）\n" % over)
    need = collections.defaultdict(list)
    for x in out:
        lo = x["目标下限"]
        n = x["正文计量"]
        if n < lo:
            need[(x["语言"], x["年级"], x["学期"])].append((x["ID"], x["标题"], n, lo - n))
    tot = 0
    for k in sorted(need):
        tot += len(need[k])
        print("%s %d年级%s册 %2d 篇待调" % (k[0], k[1], k[2], len(need[k])))
    print("\n需调正文合计 %d 篇" % tot)
    if "--csv" in sys.argv:
        p = sys.argv[sys.argv.index("--csv") + 1]
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
        print("已写出", p)
    return len(out)


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
