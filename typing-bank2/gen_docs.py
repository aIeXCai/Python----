# -*- coding: utf-8 -*-
"""生成 dist/01-题库目录.md（400 篇新闻题库的目录与统计）。"""
import json
import os
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")


def main():
    rows = [json.loads(line) for line in open(os.path.join(DIST, "全部.jsonl"), encoding="utf-8")]
    out = ["# 打字登山 · 新闻题库目录", "",
           "共 %d 篇；只收七、八年级中英文，三至六年级已退出上线题库（源稿仍在 `src/`，旧产物在 `dist-legacy/`）。" % len(rows),
           "",
           "| 年级 | 语言 | 篇数 | 篇幅区间 | 平均 | 满分所需 | 冗余倍数 |",
           "|---|---|---|---|---|---|---|"]
    plan = {("zh", 7): (300, 380, 110, 130), ("zh", 8): (340, 440, 130, 150),
            ("en", 7): (1200, 1400, 350, 450), ("en", 8): (1300, 1500, 400, 500)}
    for lang in ("zh", "en"):
        for grade in (7, 8):
            sub = [r for r in rows if r["language"] == lang and r["grade"] == grade]
            if not sub:
                continue
            key = "han_character_count" if lang == "zh" else "english_character_count"
            v = [r[key] for r in sub]
            lo, hi, full_lo, full_hi = plan[(lang, grade)]
            out.append("| %d | %s | %d | %d–%d | %.0f | %d–%d %s | %.1f–%.1f |" % (
                grade, "中文" if lang == "zh" else "英文", len(sub), min(v), max(v),
                sum(v) / len(v), full_lo, full_hi, "汉字" if lang == "zh" else "字符",
                min(v) / full_hi, max(v) / full_lo))
    out += ["", "冗余倍数＝文章篇幅 ÷ 打满 100 分所需的字数（字符数）。倍数大于 2 表示手快的学生到五分钟仍有字可打。", ""]

    for lang in ("zh", "en"):
        for grade in (7, 8):
            sub = [r for r in rows if r["language"] == lang and r["grade"] == grade]
            if not sub:
                continue
            key = "han_character_count" if lang == "zh" else "english_character_count"
            out += ["## %d 年级 %s（%d 篇）" % (grade, "中文" if lang == "zh" else "英文", len(sub)), "",
                    "| # | 编号 | 栏目 | 标题 | %s | 学期 |" % ("汉字" if lang == "zh" else "字符"),
                    "|---|---|---|---|---|---|"]
            for i, r in enumerate(sub, 1):
                out.append("| %d | `%s` | %s | %s | %d | %s |" % (
                    i, r["id"], r["unit"], r["title"], r[key], r["semester"]))
            out.append("")
            cnt = Counter(r["unit"] for r in sub)
            out += ["栏目分布：" + "、".join("%s %d 篇" % (k, v) for k, v in cnt.items()), ""]

    with open(os.path.join(DIST, "01-题库目录.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("已生成 01-题库目录.md，%d 篇" % len(rows))


if __name__ == "__main__":
    main()
