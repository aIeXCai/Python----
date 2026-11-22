# -*- coding: utf-8 -*-
"""生成分年级可读目录"""
import json, os, collections

DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
rows = [json.loads(l) for l in open(os.path.join(DIST, "全部.jsonl"), encoding="utf-8")]

L = []
L.append("# 打字登山 · 分年级题库目录\n")
L.append("每条含完整正文，标题、出处、授权单独存放，不计入打字正文。")
L.append("`grade_label` 为年级标签，`lesson_no` 为对应课次，`textbook_title_or_topic` 为所对应的课文。\n")

L.append("## 一、总量\n")
L.append("| 年级 | 中文 | 英文 | 合计 |")
L.append("|---|---|---|---|")
for g in range(3, 9):
    z = len([r for r in rows if r["language"] == "zh" and r["grade"] == g])
    e = len([r for r in rows if r["language"] == "en" and r["grade"] == g])
    if z or e:
        L.append("| %s | %d | %d | %d |" % ("一二三四五六七八九"[g - 1] + "年级", z, e, z + e))
L.append("")

for lang, name in (("zh", "中文"), ("en", "英文")):
    sub = [r for r in rows if r["language"] == lang]
    if not sub:
        continue
    sec = "二" if lang == "zh" else "三"
    L.append("## %s、%s\n" % (sec, "中文（统编版语文）" if lang == "zh" else "英文（人教 PEP／人教版）"))
    key = "han_character_count" if lang == "zh" else "english_character_count"
    unit = "汉字" if lang == "zh" else "字符"
    cur = None
    for r in sub:
        head = (r["grade"], r["semester"])
        if head != cur:
            cur = head
            grp = [x for x in sub if (x["grade"], x["semester"]) == head]
            eds = sorted({x["edition"] for x in grp})
            L.append("#### %s%s册（%d 篇，%s合计 %d）\n" % (
                r["grade_label"], r["semester"], len(grp), unit, sum(x[key] for x in grp)))
            L.append("版本：%s\n" % "；".join(eds))
            L.append("| 序 | id | 单元 | 课次 | 对应课文 | 标题 | 体裁 | %s |" % unit)
            L.append("|---|---|---|---|---|---|---|---|")
        L.append("| %s | `%s` | %s | %s | %s | %s | %s | %d |" % (
            r["id"].split("-")[3], r["id"], r["unit"],
            "—" if r["lesson_no"] in ("—", "", None) else r["lesson_no"],
            r["textbook_title_or_topic"], r["title"], r["genre"], r[key]))
    L.append("")

open(os.path.join(DIST, "01-题库目录.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("目录已生成", len(rows), "条")
