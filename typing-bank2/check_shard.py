# -*- coding: utf-8 -*-
"""单篇分片自检：字数、标点、段落、重复。

用法：python3 check_shard.py news/zh_g7_01.py
"""
import importlib.util
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
BAND = {"zh": {7: (300, 380), 8: (340, 440)},
        "en": {7: (1200, 1400), 8: (1300, 1500)}}

try:
    from opencc import OpenCC
    CC = OpenCC("t2s")
except Exception:
    class _CC:
        @staticmethod
        def convert(s):
            return s
    CC = _CC()


def load(path):
    name = os.path.basename(path)[:-3]
    spec = importlib.util.spec_from_file_location("shard_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(path):
    mod = load(path)
    base = os.path.basename(path)
    m = re.match(r"^(zh|en)_g(7|8)_\d+$", base[:-3])
    if not m:
        print("文件名必须是 zh_g7_01.py / en_g8_03.py 这种格式")
        return 1
    lang, grade = m.group(1), int(m.group(2))
    lo, hi = BAND[lang][grade]
    cap = int(hi * 1.15)
    bad = 0
    titles, bodies = set(), set()
    rows = getattr(mod, "ROWS", [])
    print("%s  语言 %s 年级 %d 目标 %d–%d（上限 %d）共 %d 篇" % (base, lang, grade, lo, hi, cap, len(rows)))
    for i, row in enumerate(rows, 1):
        if len(row) != 3:
            print("  #%02d 元组应为 (栏目, 标题, [段落])，实际 %d 项" % (i, len(row)))
            bad += 1
            continue
        unit, title, paras = row
        body = "".join(paras) if lang == "zh" else " ".join(paras)
        n = len(CJK.findall(body)) if lang == "zh" else len(body)
        notes = []
        if not unit or not str(unit).strip():
            notes.append("栏目为空")
        if not title or not str(title).strip():
            notes.append("标题为空")
        if not (3 <= len(paras) <= 7):
            notes.append("段落 %d 段（需 3–7 段）" % len(paras))
        if n < lo:
            notes.append("偏短 %d（差 %d）" % (n, lo - n))
        if n > cap:
            notes.append("偏长 %d（超 %d）" % (n, n - cap))
        if lang == "zh":
            if CC.convert(body) != body:
                diff = sorted({a for a, b in zip(body, CC.convert(body)) if a != b})
                notes.append("繁体字 %s" % "".join(diff)[:8])
            if re.search(r"[a-zA-Z]*[,.;:!?][\u4e00-\u9fff]", body):
                notes.append("半角标点")
        else:
            if any(not " " <= ch <= "~" for ch in body):
                bad_chars = sorted({ch for ch in body if not " " <= ch <= "~"})
                notes.append("非 ASCII %s" % "".join(bad_chars)[:6])
            if len(body.split()) < 120:
                notes.append("词数 %d（<120）" % len(body.split()))
        if title in titles:
            notes.append("标题重复")
        titles.add(title)
        if body in bodies:
            notes.append("正文重复")
        bodies.add(body)
        flag = "  ← " + "；".join(notes) if notes else ""
        if notes:
            bad += 1
        print("  #%02d %-4d %s%s" % (i, n, title, flag))
    print("不合格 %d 篇" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
