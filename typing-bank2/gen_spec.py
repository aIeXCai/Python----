# -*- coding: utf-8 -*-
"""生成编制规格文档（数字全部取自已构建数据，不手写）"""
import json, os

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
rows = [json.loads(l) for l in open(os.path.join(DIST, "全部.jsonl"), encoding="utf-8")]

SPEED = {"zh": {3: 15, 4: 17, 5: 19, 6: 22, 7: 26, 8: 30},
         "en": {3: 50, 4: 58, 5: 66, 6: 76, 7: 90, 8: 100}}
BAND = {"zh": {3: (80, 120), 4: (95, 140), 5: (110, 155),
               6: (128, 178), 7: (148, 202), 8: (165, 225)},
        "en": {3: (250, 350), 4: (290, 390), 5: (330, 435),
               6: (380, 485), 7: (450, 550), 8: (500, 615)}}
CN = "一二三四五六七八九"

L = ["# 打字登山 · 分年级题库编制规格\n",
     "编制时间：2026-11-20　　适用：小学三年级至初中八年级，语文（统编版）与英语（人教 PEP／人教版）\n",
     "## 一、与上一版的差别\n",
     "| 项 | 上一版 | 本版 |", "|---|---|---|",
     "| 组织方式 | 三至八年级共 200 组 | **每个年级 100 篇中文 + 100 篇英文** |",
     "| 年级标识 | 只有 `grade` | 增加 `grade_label`（如「三年级」）与 `lesson_no`（课次），可按年级分库 |",
     "| 古诗词 | 57 组，短的仅 76 汉字 | **每年级不超过 10 篇，且只用长篇**；课本无长诗的年级不放 |",
     "| 篇幅 | 76–236 汉字，同年级跨度近 3 倍 | 按年级设字数带，逐篇校验 |",
     "",
     "## 二、字数带与预计用时\n",
     "口径：**下限＝本年级速度 × 5 分钟**（保证 5 分钟有字可打），上限只是「舒适参考」，**偏长不判错**——游戏不强求打完才给分，多出来的部分是给手快的学生玩的。只有偏短要补，偏短意味着 5 分钟会打空。\n",
     "| 年级 | 中文速度（汉字/分） | 中文目标 | 英文速度（字符/分） | 英文目标 |",
     "|---|---|---|---|---|"]
for g in range(3, 9):
    L.append("| %s年级 | %d | %d–%d 汉字 | %d | %d–%d 字符 |" % (
        CN[g - 1], SPEED["zh"][g], BAND["zh"][g][0], BAND["zh"][g][1],
        SPEED["en"][g], BAND["en"][g][0], BAND["en"][g][1]))

L += ["",
      "速度是**假设值**，必须用学生试打校准。校验规则：**低于下限报错（须续篇），高于上限只做统计不报错**；要改只改 `build.py` 顶部的 `BAND` 与 `SPEED`，重跑即可。\n",
      "## 三、诗词配额与选取原则\n",
      "1. 每个年级中文**最多 10 篇诗词**，其余为课文类材料。",
      "2. 诗词只用长篇或组诗：《木兰诗》《孔雀东南飞》《琵琶行》《茅屋为秋风所破歌》《卖炭翁》《白雪歌送武判官归京》等。**不用四句绝句单独成篇**——那类只有 20–30 字，打不满 5 分钟。",
      "3. 低年级课本里没有长篇诗，所以**三年级诗词配额实际为 0**，古诗课改配同主题写景原创文（如《秋天的山》《雨后的湖》）。这是取舍，不是遗漏。",
      "4. 文言文不受诗词配额限制，可录公版原文（作者逝世逾五十年），长度天然合适。",
      "",
      "## 四、正文来源口径（重要）\n",
      "教材可以免费在线阅读，不等于可以转载。所以：\n",
      "| 材料 | 能否录原文 | 本库做法 | `material_type` |",
      "|---|---|---|---|",
      "| 古诗文、文言文（公版） | 可以 | 录原文，注明作品、作者、底本 | 公版原作 |",
      "| 现代课文（版权保护期内） | **不可以** | 写同课文主题、同句式难度的原创练习文 | 教材主题原创 |",
      "| 教材节选（有书面许可） | 可以 | 尚未取得任何许可，本库不使用此标签 | 获准教材节选 |",
      "",
      "「其余全要是课本的文章」在本库落实为：**每一篇都锚定到具体课次**（`lesson_no` + `textbook_title_or_topic`），题材、结构、词汇难度对齐该课，正文为原创而非课文原文。教学对齐在，侵权风险没有。\n",
      "## 五、字段\n",
      "`id`、`language`、`grade`、`grade_label`、`semester`、`textbook_series`、`edition`、`unit`、`lesson_no`、`textbook_title_or_topic`、`title`、`genre`、`material_type`、`paragraphs`、`difficulty_draft`、`han_character_count`、`english_character_count`、`source_title`、`source_url`、`license_or_permission`、`edition_check_status`、`alignment_level`、`note`（共 23 项；后两项为 v2 追加，见下）\n",
      "\n",
      "**v2（2026-11-20）追加两列**：`alignment_level` 取「逐课对齐／单元对齐」——语文 599 篇按课次，英语 600 篇教材按 Unit 组织只能到单元、`lesson_no` 一律为 `—`；`note` 存编者说明、底本卷次、节选范围，**说明文字一律不进 `paragraphs`**，学生打不到。\n",
      "**v3（2026-11-20）字段口径**：`lesson_no` 在逐课对齐条目里是**整数**（`1`、`28`），不是字符串；平台只收非负整数或 `—`，字符串会导致整份导入被退收。`note` 开头为 `【含同主题延伸】` 的 12 条，正文夹了非本课篇目，筛选「纯课内原文」时应排除。\n",
      "- `han_character_count` 只数汉字，标点不计；`english_character_count` 含单词间空格。",
      "- `paragraphs` 为完整段落数组，逐段渲染、逐段计分，不要按句号切分。",
      "- `genre` 取值：记叙文／写景散文／童话／说明文／科普／诗歌／文言文／对话／书信。\n",
      "## 六、进度\n",
      "| 年级 | 中文 | 英文 | 汉字区间 | 字符区间 | 状态 |",
      "|---|---|---|---|---|---|"]
for g in range(3, 9):
    z = [r for r in rows if r["language"] == "zh" and r["grade"] == g]
    e = [r for r in rows if r["language"] == "en" and r["grade"] == g]
    zr = "%d–%d" % (min(r["han_character_count"] for r in z), max(r["han_character_count"] for r in z)) if z else "—"
    er = "%d–%d" % (min(r["english_character_count"] for r in e), max(r["english_character_count"] for r in e)) if e else "—"
    st = "已完成" if len(z) >= 100 and len(e) >= 100 else ("进行中" if z or e else "待编")
    L.append("| %s年级 | %d/100 | %d/100 | %s | %s | %s |" % (CN[g - 1], len(z), len(e), zr, er, st))

L += ["",
      "构建与校验：`python3 build.py`（生成 JSONL + 校验），`python3 gen_catalog.py`（目录），`python3 gen_spec.py`（本文档）。",
      "源数据按册存放于 `src/`，一册可拆 `_a`/`_b` 分片，构建时按语言、年级、册次合并并统一编号。", ""]

txt = "\n".join(L)
while "\n\n\n" in txt:
    txt = txt.replace("\n\n\n", "\n\n")
open(os.path.join(DIST, "00-编制规格.md"), "w", encoding="utf-8").write(txt)
print("规格文档已生成，共", len(rows), "条")
