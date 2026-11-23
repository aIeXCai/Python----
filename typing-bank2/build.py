# -*- coding: utf-8 -*-
"""打字登山 · 新闻题库构建与校验（只出七、八年级）

源文件：news/<lang>_g<grade>_<序号>.py，每个模块暴露：
    SEMESTER = "上" | "下"
    ROWS = [(栏目, 标题, [段1, 段2, ...]), ...]

输出：dist/typing-bank-<lang>-g<grade>.jsonl 与 dist/全部.jsonl

三至六年级的教材源稿仍在 src/，但不再参与构建；旧 1200 篇产物在 dist-legacy/，
用 build_legacy.py 可重现。
"""
import glob
import importlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
NEWS = os.path.join(ROOT, "news")
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

GRADE_LABEL = {7: "七年级", 8: "八年级"}

TEXTBOOK_SERIES = "自编新闻练习材料（配合课堂打字训练，不绑定教材版本）"
EDITION = "新闻体 v1（2026-11）"
GENRE = "新闻通讯"
MATERIAL_TYPE = "自编新闻"
SOURCE_TITLE = "打字登山·自编新闻练习文 v1"
SOURCE_URL = "https://github.com/aIeXCai/Python----"
LICENSE = "本库自编，校内教学可自由使用"
CHECK_STATUS = "已核对"
ALIGNMENT = "非教材对齐"

# 篇幅带：下限＝本年级满分手速 × 5 分钟再留冗余，保证手快的学生到 5 分钟仍有字可打。
# 满分口径（平台 scoring.py）：中文满分需 目标速度×5 个汉字；英文满分需 目标速度×25 个字符。
#   七年级中文 22–26 字/分 → 满分 110–130 字 → 文章 300 字以上
#   八年级中文 26–30 字/分 → 满分 130–150 字 → 文章 340 字以上
#   七年级英文 14–18 词/分 → 满分 350–450 字符 → 文章 950 字符以上
#   八年级英文 16–20 词/分 → 满分 400–500 字符 → 文章 1050 字符以上
BAND = {
    "zh": {7: (300, 380), 8: (340, 440)},
    "en": {7: (1200, 1400), 8: (1300, 1500)},
}
# 硬上下限：低于 floor 报错（打不满五分钟），高于 cap 报错（老师审阅时太拖）
FLOOR_RATIO = 1.0
CAP_RATIO = 1.15

PARAS_MIN, PARAS_MAX = 3, 7

ROW_RE = re.compile(r"^(zh|en)_g(7|8)_(\d+)$")


def load(path):
    sys.path.insert(0, NEWS)
    name = os.path.basename(path)[:-3]
    mod = importlib.import_module(name)
    importlib.reload(mod)
    return mod


def count_han(paras):
    return len(CJK.findall("".join(paras)))


def count_en(paras):
    return len(" ".join(paras))


def expand(lang, grade, sem, rows, start_no):
    out = []
    for offset, (unit, title, paras) in enumerate(rows):
        no = start_no + offset
        paras = [p.strip() for p in paras if p.strip()]
        out.append({
            "id": "%s-%d-news-%03d" % (lang, grade, no),
            "language": lang,
            "grade": grade,
            "grade_label": GRADE_LABEL[grade],
            "semester": sem,
            "textbook_series": TEXTBOOK_SERIES,
            "edition": EDITION,
            "unit": unit,
            "lesson_no": "—",
            "textbook_title_or_topic": unit,
            "title": title,
            "genre": GENRE,
            "material_type": MATERIAL_TYPE,
            "paragraphs": paras,
            "difficulty_draft": "L5 中",
            "han_character_count": count_han(paras) if lang == "zh" else 0,
            "english_character_count": count_en(paras) if lang == "en" else 0,
            "source_title": SOURCE_TITLE,
            "source_url": SOURCE_URL,
            "license_or_permission": LICENSE,
            "edition_check_status": CHECK_STATUS,
            "alignment_level": ALIGNMENT,
            "note": "",
        })
    return out


def check_row(r, problems):
    rid = r["id"]
    lo, hi = BAND[r["language"]][r["grade"]]
    floor = int(lo * FLOOR_RATIO)
    cap = int(hi * CAP_RATIO)
    key = "han_character_count" if r["language"] == "zh" else "english_character_count"
    n = r[key]
    unit_name = "汉字" if r["language"] == "zh" else "字符"
    if n < floor:
        problems.append("%s 偏短 %d %s（下限 %d，差 %d）" % (rid, n, unit_name, floor, floor - n))
    if n > cap:
        problems.append("%s 偏长 %d %s（上限 %d，超 %d）" % (rid, n, unit_name, cap, n - cap))
    if not (PARAS_MIN <= len(r["paragraphs"]) <= PARAS_MAX):
        problems.append("%s 段落数 %d 不在 %d–%d 之间" % (rid, len(r["paragraphs"]), PARAS_MIN, PARAS_MAX))
    body = "".join(r["paragraphs"])
    if r["language"] == "zh":
        if CC.convert(body) != body:
            diff = sorted({a for a, b in zip(body, CC.convert(body)) if a != b})
            if diff:
                problems.append("%s 含繁体字 %s" % (rid, "".join(diff)[:8]))
        if re.search(r"[a-zA-Z]*[,.;:!?][\u4e00-\u9fff]", body):
            problems.append("%s 中文里混入半角标点" % rid)
        if re.search(r"[，。！？；：、“”‘’（）《》]", " ".join(r["paragraphs"][:1])) is None:
            problems.append("%s 首段缺少中文标点，疑似断句不全" % rid)
    else:
        if re.search(r"[\u3000-\u303f\uff01-\uff5e]", body):
            problems.append("%s 英文里混入全角标点" % rid)
        if any(not " " <= ch <= "~" for ch in body):
            problems.append("%s 英文含非 ASCII 字符" % rid)
        if n and len(body.split()) < 120:
            problems.append("%s 英文词数 %d 偏少（<120 词）" % (rid, len(body.split())))


def main():
    os.makedirs(DIST, exist_ok=True)
    modules = []
    for path in sorted(glob.glob(os.path.join(NEWS, "*.py"))):
        base = os.path.basename(path)[:-3]
        if base.startswith("_"):
            continue
        m = ROW_RE.match(base)
        if not m:
            continue
        modules.append((m.group(1), int(m.group(2)), int(m.group(3)), base, path))

    if not modules:
        print("没有找到任何新闻分片（news/<lang>_g<grade>_<no>.py）")
        return 1

    all_rows = []
    origin = {}
    problems = []
    for lang in ("zh", "en"):
        for grade in (7, 8):
            subs = sorted([x for x in modules if x[0] == lang and x[1] == grade], key=lambda x: x[2])
            if not subs:
                continue
            rows, meta = [], []
            for _, _, _, base, path in subs:
                mod = load(path)
                sem = getattr(mod, "SEMESTER", "上")
                if not hasattr(mod, "SEMESTER"):
                    problems.append("%s 缺少 SEMESTER" % base)
                if not mod.ROWS:
                    problems.append("%s 没有 ROWS" % base)
                for unit, title, paras in mod.ROWS:
                    rows.append((unit, title, paras))
                    meta.append((base, sem))
            expanded = expand(lang, grade, "上", rows, 1)
            for r, (base, sem) in zip(expanded, meta):
                r["semester"] = sem
                origin[r["id"]] = [base, r["title"]]
            all_rows.extend(expanded)

    # 逐篇校验
    seen_ids, seen_titles, seen_bodies = set(), set(), set()
    for r in all_rows:
        if r["id"] in seen_ids:
            problems.append("%s 重复 ID" % r["id"])
        seen_ids.add(r["id"])
        tk = (r["language"], r["grade"], r["title"])
        if tk in seen_titles:
            problems.append("%s 标题在本年级重复：%s" % (r["id"], r["title"]))
        seen_titles.add(tk)
        bk = (r["language"], r["grade"], "".join(r["paragraphs"]))
        if bk in seen_bodies:
            problems.append("%s 正文与本年级另一篇完全相同" % r["id"])
        seen_bodies.add(bk)
        if list(r) != KEYS:
            problems.append("%s 字段顺序/名称不符" % r["id"])
        for k in ("unit", "title", "textbook_title_or_topic"):
            if not str(r[k]).strip():
                problems.append("%s 的 %s 为空" % (r["id"], k))
        check_row(r, problems)

    # 分年级写出
    for lang in ("zh", "en"):
        for grade in (7, 8):
            sub = [r for r in all_rows if r["language"] == lang and r["grade"] == grade]
            if not sub:
                continue
            with open(os.path.join(DIST, "typing-bank-%s-g%d.jsonl" % (lang, grade)), "w",
                      encoding="utf-8") as f:
                for r in sub:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(os.path.join(DIST, "全部.jsonl"), "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(os.path.join(ROOT, "index.json"), "w", encoding="utf-8") as f:
        json.dump(origin, f, ensure_ascii=False, indent=0)

    print("总条数", len(all_rows))
    for lang in ("zh", "en"):
        for grade in (7, 8):
            sub = [r for r in all_rows if r["language"] == lang and r["grade"] == grade]
            if not sub:
                continue
            k = "han_character_count" if lang == "zh" else "english_character_count"
            v = [r[k] for r in sub]
            lo, hi = BAND[lang][grade]
            print("  %s %d年级 %d 篇  %s %d–%d（目标 %d–%d）平均 %.0f" % (
                lang, grade, len(sub), "汉字" if lang == "zh" else "字符",
                min(v), max(v), lo, hi, sum(v) / len(v)))
    print("问题 %d 项" % len(problems))
    for p in problems[:60]:
        print("  -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
