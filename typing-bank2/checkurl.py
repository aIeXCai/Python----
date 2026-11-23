# -*- coding: utf-8 -*-
"""核对公版条目的来源链接：能否打开、页面里是否真有这段原文。"""
import json, re, html, subprocess, sys, time
from opencc import OpenCC

CC = OpenCC("t2s")
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
COLL = ("quantangshi", "quan-song-shi", "quan-song-ci", "wen-xuan", "quan-tang-wen")


def fetch(u):
    r = subprocess.run(["curl", "-sL", "-m", "25", "-A", "Mozilla/5.0",
                        "-w", "\n%{http_code}", u], capture_output=True, text=True)
    body = r.stdout
    code = body[-3:].strip()
    return code, body[:-4]


def page_text(h):
    h = re.sub(r"<script.*?</script>", "", h, flags=re.S)
    return CC.convert(html.unescape(re.sub(r"<[^>]+>", " ", h)))


rows = [json.loads(l) for l in open("dist-legacy/全部.jsonl", encoding="utf-8")]
seen = {}
report = []
for r in rows:
    if r["material_type"] != "公版原作":
        continue
    u = r["source_url"]
    probe = "".join(CJK.findall(r["paragraphs"][0]))[:8]
    if u not in seen:
        time.sleep(0.8)
        code, body = fetch(u)
        if code != "200":
            seen[u] = ("HTTP " + code, False)
        elif any(k in u for k in COLL):
            seen[u] = ("200 集合页", None)
        else:
            seen[u] = ("200", probe in page_text(body))
    st, hit = seen[u]
    report.append((r["id"], st, hit, u, probe))

bad = [x for x in report if x[1] != "200 集合页" and x[2] is not True]
for x in report:
    print("%-11s %-10s %-5s %s  [%s]" % (x[0], x[1], {True: "命中", False: "未见", None: "--"}[x[2]], x[3], x[4]))
print("\n合计 %d 条，可疑 %d 条" % (len(report), len(bad)))
