# -*- coding: utf-8 -*-
"""打字登山 · 分年级题库构建与校验

源文件：src/<lang>_g<grade>s<sem>.py，每个模块暴露 ROWS（列表，元素为短键字典）
输出：dist/typing-bank-<lang>-g<grade>.jsonl 与 dist/全部.jsonl
"""
import importlib, json, os, re, sys, glob

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
DIST = os.path.join(ROOT, "dist")

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

try:
    from opencc import OpenCC
    CC = OpenCC("t2s")
except Exception:  # 没装就退化为空操作
    class _CC:
        @staticmethod
        def convert(s):
            return s
    CC = _CC()

KEYS = ["id", "language", "grade", "grade_label", "semester", "textbook_series",
        "edition", "unit", "lesson_no", "textbook_title_or_topic", "title", "genre",
        "material_type", "paragraphs", "difficulty_draft", "han_character_count",
        "english_character_count", "source_title", "source_url",
        "license_or_permission", "edition_check_status",
        "alignment_level", "note"]

SERIES = {"zh": "统编版语文（人民教育出版社）",
          "en": "人教 PEP 三年级起点／人教版初中英语"}
GRADE_LABEL = {g: "一二三四五六七八九"[g - 1] + "年级" for g in range(3, 9)}

# 各年级参考字数带。口径：下限＝保证 5 分钟有字可打（速度×5 分钟），上限只是"舒适参考"。
# 假设速度：中文 3–8 年级 15/17/19/22/26/30 字每分；英文 50/58/66/76/90/100 字符每分
# 这是"待实测校准"的参数，学生试打后只需改这里再重跑 build.py
# 注意：偏长不作错误（打不完也能拿分），只有偏短才报错——偏短意味着 5 分钟打空。
BAND = {
    "zh": {3: (80, 120), 4: (95, 140), 5: (110, 155),
           6: (128, 178), 7: (148, 202), 8: (165, 225)},
    # 下限 = max(年级带下限, 本年级速度 × 5 分钟)，保证每组都能打满 5 分钟
    "en": {3: (250, 350), 4: (290, 390), 5: (330, 435),
           6: (380, 485), 7: (450, 550), 8: (500, 615)},
}
GENRE_MAP = {"narrative": "记叙文", "dialogue": "对话", "letter": "书信",
             "说明": "说明文", "记叙": "记叙文", "写景": "写景散文"}

SPEED = {"zh": {3: 15, 4: 17, 5: 19, 6: 22, 7: 26, 8: 30},
         "en": {3: 50, 4: 58, 5: 66, 6: 76, 7: 90, 8: 100}}

# 组诗／组文里夹了非本课篇目的 12 条。正文不动，只在 note 前加统一标记，
# 让平台能按 note 含「含同主题延伸」把这几条从「纯课内原文」筛选里排除。
# 注意：标记是机器可读的固定串，改文案时要同步改 03 号文档与平台筛选条件。
EXTENDED_TAG = "【含同主题延伸】"
EXTENDED = {
    "zh-4-1-49", "zh-4-1-50", "zh-4-2-29", "zh-4-2-30",
    "zh-5-1-22", "zh-5-1-48", "zh-5-2-38", "zh-5-2-40",
    "zh-6-1-36", "zh-6-1-37", "zh-6-2-43", "zh-6-2-46",
}


def load(module_path):
    sys.path.insert(0, SRC)
    name = os.path.basename(module_path)[:-3]
    mod = importlib.import_module(name)
    importlib.reload(mod)
    return mod.ROWS


def count_han(paras):
    return len(CJK.findall("".join(paras)))


def count_en(paras):
    return len(" ".join(paras))


def expand(lang, grade, sem, rows):
    out = []
    for i, r in enumerate(rows, 1):
        rid = r.get("id") or "%s-%d-%d-%02d" % (lang, grade, sem, i)
        paras = [p.strip() for p in r["p"] if p.strip()]
        raw_ln = r.get("ln")
        # 英语一律只做到单元对齐（教材按单元组织，无课次可对），课次字段留“—”
        # 语文逐课对齐：lesson_no 必须输出整数（平台 importing.py 只接受 int 或 —），
        # 写成字符串 "1" 会被判「lesson_no 必须是非负整数或为空」而整行退收。
        if lang == "en":
            lesson_no = "—"
            align = "单元对齐"
        elif isinstance(raw_ln, int):
            lesson_no = raw_ln
            align = "逐课对齐"
        else:
            lesson_no = "—"
            align = "单元对齐"
        out.append({
            "id": rid,
            "language": "zh" if lang == "zh" else "en",
            "grade": grade,
            "grade_label": GRADE_LABEL[grade],
            "semester": "上" if sem == 1 else "下",
            "textbook_series": SERIES[lang],
            "edition": r["ed"],
            "unit": r["u"],
            "lesson_no": lesson_no,
            "textbook_title_or_topic": r["tt"],
            "title": r["ti"],
            "genre": GENRE_MAP.get(r["ge"], r["ge"]),
            "material_type": r["mt"],
            "paragraphs": paras,
            "difficulty_draft": r["d"],
            "han_character_count": count_han(paras) if lang == "zh" else 0,
            "english_character_count": count_en(paras) if lang == "en" else 0,
            "source_title": r["st"],
            "source_url": r["su"],
            "license_or_permission": r["lic"],
            "edition_check_status": r["ecs"],
            "alignment_level": align,
            "note": (EXTENDED_TAG + r.get("note", "")) if rid in EXTENDED else r.get("note", ""),
        })
    return out


def main():
    os.makedirs(DIST, exist_ok=True)
    all_rows, problems = [], []

    pat = re.compile(r"^(zh|en)_g(\d)s(\d)(?:_[a-z0-9]+)?$")
    buckets = {}
    order = []
    origin_per_key = {}
    origin = {}  # id -> [模块名, 标题]，供 padtool 类脚本按 id 回改源文件
    for path in sorted(glob.glob(os.path.join(SRC, "*.py"))):
        base = os.path.basename(path)[:-3]
        if base.startswith("_"):
            continue
        m = pat.match(base)
        if not m:
            continue
        lang, grade, sem = m.group(1), int(m.group(2)), int(m.group(3))
        key = (lang, grade, sem)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
            origin_per_key[key] = []
        mod_rows = load(path)
        buckets[key].extend(mod_rows)
        origin_per_key[key].extend([(base, r["ti"]) for r in mod_rows])

    for key in order:
        lang, grade, sem = key
        rows = expand(lang, grade, sem, buckets[key])
        for r, (mod, ti) in zip(rows, origin_per_key[key]):
            origin[r["id"]] = [mod, ti]
        all_rows.extend(rows)

    # 按 lang-grade 分组重写
    for lang in ("zh", "en"):
        for g in range(3, 9):
            sub = [r for r in all_rows if r["language"] == lang and r["grade"] == g]
            if not sub:
                continue
            with open(os.path.join(DIST, "typing-bank-%s-g%d.jsonl" % (lang, g)), "w",
                      encoding="utf-8") as f:
                for r in sub:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(os.path.join(DIST, "全部.jsonl"), "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(os.path.join(ROOT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(origin, f, ensure_ascii=False, indent=0)

    # ---- 校验 ----
    ids = [r["id"] for r in all_rows]
    if len(ids) != len(set(ids)):
        problems.append("ID 重复")
    for r in all_rows:
        if list(r) != KEYS:
            problems.append("%s 字段顺序/名称不符" % r["id"])
        if not r["paragraphs"]:
            problems.append("%s 正文为空" % r["id"])
        for k in ("unit", "title", "textbook_title_or_topic", "source_title", "source_url"):
            if not str(r[k]).strip():
                problems.append("%s 的 %s 为空" % (r["id"], k))
        # 平台口径（backend/typing_practice/importing.py）：lesson_no 只收非负整数或 —。
        # 写成字符串 "1" 会被判「必须是非负整数」，整份导入失败，故在此拦住。
        if r["language"] == "zh" and r["alignment_level"] == "逐课对齐":
            if not isinstance(r["lesson_no"], int) or isinstance(r["lesson_no"], bool):
                problems.append("%s 的 lesson_no 必须是整数，实为 %r" % (r["id"], r["lesson_no"]))
        elif r["lesson_no"] != "—":
            problems.append("%s 为单元对齐，lesson_no 必须是 —，实为 %r" % (r["id"], r["lesson_no"]))
        if r["id"] in EXTENDED and not r["note"].startswith(EXTENDED_TAG):
            problems.append("%s 缺同主题延伸标记" % r["id"])
        key = "han_character_count" if r["language"] == "zh" else "english_character_count"
        lo, hi = BAND[r["language"]][r["grade"]]
        # 只卡下限：偏长不算问题（游戏不强求打完），偏短等于 5 分钟打空，必须续篇
        if r[key] < lo:
            problems.append("%s 字数 %d 偏短（下限 %d，差 %d）" % (r["id"], r[key], lo, lo - r[key]))
        body = "".join(r["paragraphs"])
        if r["language"] == "zh":
            # 人名、地名用字（如毕昇的「昇」）不算繁体，放行
            EXEMPT = set("昇巘")
            if CC.convert(body) != body:
                diff = sorted({a for a, b2 in zip(body, CC.convert(body)) if a != b2} - EXEMPT)
                if diff:
                    problems.append("%s 含繁体字 %s" % (r["id"], "".join(diff)[:8]))
            if re.search(r"[a-zA-Z]*[,.;:!?][\u4e00-\u9fff]", body):
                problems.append("%s 中文里混入半角标点" % r["id"])
        else:
            if re.search(r"[\u3000-\u303f\uff01-\uff5e]", body):
                problems.append("%s 英文里混入全角标点" % r["id"])

    missing_ext = EXTENDED - {r["id"] for r in all_rows}
    if missing_ext:
        problems.append("同主题延伸清单里有不存在的 ID：%s" % "、".join(sorted(missing_ext)))

    print("总条数", len(all_rows))
    over = 0
    for lang in ("zh", "en"):
        for g in range(3, 9):
            sub = [r for r in all_rows if r["language"] == lang and r["grade"] == g]
            if sub:
                k = "han_character_count" if lang == "zh" else "english_character_count"
                v = [r[k] for r in sub]
                sp = SPEED[lang][g]
                hi = BAND[lang][g][1]
                over += sum(1 for x in v if x > hi)
                print("  %s %d年级 %d 条  %s %d–%d  平均 %.0f  预计 %.1f–%.1f 分钟%s" % (
                    lang, g, len(sub), "汉字" if lang == "zh" else "字符",
                    min(v), max(v), sum(v) / len(v), min(v) / sp, max(v) / sp,
                    "  （超出舒适带 %d 条，不算错）" % sum(1 for x in v if x > hi) if any(x > hi for x in v) else ""))
    print("超出舒适参考带共 %d 条（偏长不报错）" % over)
    print("问题 %d 项" % len(problems))
    for p in problems[:40]:
        print("  -", p)


if __name__ == "__main__":
    main()
