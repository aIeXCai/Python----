#!/usr/bin/env bash
# 一键同步：把 GitHub 上的 main 构建成可发布的单端口产物（deploy/public）。
#
# 用法：
#   bash deploy/sync_and_publish.sh              # 用 origin/main
#   bash deploy/sync_and_publish.sh origin/jifang3   # 用指定分支
#
# 说明：构建源永远是 GitHub 上「已提交」的代码，不受本地未提交改动影响。
# 两种取码方式（自动选择）：
#   1) git fetch + git archive —— 正常情况
#   2) GitHub 源码包下载 —— git 协议被网络拦截时自动兜底
# 执行完这个脚本后，需要在 WorkBuddy 对话里让它发布目录 deploy/public（发布通道不在命令行里）。
set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
OUT="$DEPLOY_DIR/public"
SRC="$ROOT/.deploy-src"
TARBALL="/tmp/pylearn-src-$$.tar.gz"
REF="${1:-origin/main}"
BRANCH="${REF#origin/}"

cd "$ROOT"

# ---------- 解析仓库标识（用于 API / 源码包地址） ----------
REPO_URL="$(git config --get remote.origin.url 2>/dev/null || echo '')"
SLUG="$(printf '%s' "$REPO_URL" | python3 -c '
import re, sys
u = sys.stdin.read().strip()
m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", u)
print("{}/{}".format(m.group(1), m.group(2)) if m else "")
')"
if [ -z "$SLUG" ] || [ "$SLUG" = "$REPO_URL" ]; then
    echo "无法从 remote.origin.url 解析仓库标识：$REPO_URL" >&2
    exit 1
fi

cleanup() { rm -f "$TARBALL"; }
trap cleanup EXIT

echo "[1/5] 获取 GitHub 上 $BRANCH 的最新提交"

MODE="git"
if ! git -c http.version=HTTP/1.1 fetch origin --quiet 2>/dev/null; then
    MODE="tarball"
fi

if [ "$MODE" = "git" ]; then
    if ! SHA="$(git rev-parse "$REF" 2>/dev/null)"; then
        MODE="tarball"
    fi
fi

if [ "$MODE" = "git" ]; then
    echo "      方式：git fetch（本地仓库）"
    COMMIT_SUBJECT="$(git log -1 --format='%s' "$SHA")"
    COMMIT_DATE="$(git log -1 --format='%cd' --date=short "$SHA")"
    LOCAL_HEAD="$(git rev-parse HEAD)"
else
    echo "      方式：GitHub 源码包（git 协议不可用，自动兜底）"
    META="$(curl -s --max-time 40 "https://api.github.com/repos/$SLUG/commits/$BRANCH")"
    SHA="$(printf '%s' "$META" | python3 -c "
import json,sys
d=json.load(sys.stdin)
if 'sha' not in d: raise SystemExit('API 返回异常: '+str(d.get('message')))
print(d['sha'])
")"
    read -r COMMIT_SUBJECT COMMIT_DATE <<EOF
$(printf '%s' "$META" | python3 -c "
import json,sys
d=json.load(sys.stdin)['commit']
print(d['message'].splitlines()[0].replace('\t',' '), d['author']['date'][:10])
")
EOF
    LOCAL_HEAD="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
    if [ "$LOCAL_HEAD" != "$SHA" ]; then
        echo "      ⚠️  本地 HEAD $(printf '%.7s' "$LOCAL_HEAD") 与线上版本 $(printf '%.7s' "$SHA") 不一致"
        echo "         本次发布以 GitHub 为准；本地如需同步请执行：git fetch origin && git checkout $BRANCH"
    fi
fi

echo "      版本 $SHA"
echo "      提交 $COMMIT_SUBJECT ($COMMIT_DATE)"

# 线上只跟随 $REF，当前分支若有未合并提交，提醒一下，避免"改了却没上线"
LOCAL_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
if [ -n "$LOCAL_BRANCH" ] && [ "$LOCAL_BRANCH" != "HEAD" ] && [ "$LOCAL_BRANCH" != "$BRANCH" ]; then
    AHEAD="$(git rev-list --count "$BRANCH..$LOCAL_BRANCH" 2>/dev/null || echo 0)"
    if [ "${AHEAD:-0}" -gt 0 ]; then
        echo "      ⚠️  当前分支 $LOCAL_BRANCH 有 $AHEAD 个提交不在 $BRANCH 上，本次发布不会包含它们"
        echo "         要么先合并到 $BRANCH，要么执行：bash deploy/sync_and_publish.sh origin/$LOCAL_BRANCH"
    fi
fi

echo "[2/5] 导出该版本的已提交源码（不含未提交改动）"
rm -rf "$SRC"
mkdir -p "$SRC"
if [ "$MODE" = "git" ]; then
    git archive "$SHA" | tar -x -C "$SRC"
else
    curl -sL --max-time 240 -o "$TARBALL" \
        "https://codeload.github.com/$SLUG/tar.gz/refs/heads/$BRANCH"
    if [ ! -s "$TARBALL" ]; then
        echo "源码包下载失败，无法继续" >&2
        exit 1
    fi
    tar -xzf "$TARBALL" -C "$SRC" --strip-components=1
fi

echo "[3/5] 构建前端（复用本地 node_modules 加速）"
if [ -d "$ROOT/frontend/node_modules" ] && [ ! -e "$SRC/frontend/node_modules" ]; then
    ln -s "$ROOT/frontend/node_modules" "$SRC/frontend/node_modules"
fi
(cd "$SRC/frontend" && npx vite build >/dev/null)

echo "[4/5] 组装发布目录"
mkdir -p "$OUT"
rsync -a --delete \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='.env*' \
    --exclude='db.sqlite3*' --exclude='.local' --exclude='migration_artifacts' \
    --exclude='media/*' --exclude='submissions/*' \
    "$SRC/backend/" "$OUT/app/"
rsync -a --delete "$SRC/problems/" "$OUT/problems/"
rsync -a --delete "$SRC/frontend/dist/" "$OUT/web/"

# 静态资源预压缩：构建期生成 .gz，server.py 命中后直接发送，请求路径上零压缩开销。
# 沙箱出网带宽约 14Mbps，压缩是目前最有效的加速手段（JS 596K->~180K，wasm 9.1M->~3M）。
echo "      生成预压缩副本"
python3 - "$OUT/web" <<'PRELOAD'
import gzip
import os
import shutil
import sys

web = sys.argv[1]
EXTS = {'.js', '.mjs', '.css', '.json', '.svg', '.html', '.htm', '.map', '.txt', '.wasm', '.xml'}
orig_total = gz_total = count = 0
for root, _dirs, files in os.walk(web):
    for name in files:
        if name.endswith('.gz'):
            continue
        if os.path.splitext(name)[1].lower() not in EXTS:
            continue
        src = os.path.join(root, name)
        try:
            size = os.path.getsize(src)
        except OSError:
            continue
        if size < 1024:
            continue
        dst = src + '.gz'
        with open(src, 'rb') as fin, gzip.GzipFile(dst, 'wb', compresslevel=6, mtime=0) as fout:
            shutil.copyfileobj(fin, fout, 262144)
        gz = os.path.getsize(dst)
        if gz >= size * 0.95:
            os.remove(dst)
            continue
        orig_total += size
        gz_total += gz
        count += 1
if count:
    saved = (1 - gz_total / max(orig_total, 1)) * 100
    print("      {} 个文件：{:.1f}MB -> {:.1f}MB（省 {:.0f}%）".format(
        count, orig_total / 1048576, gz_total / 1048576, saved))
else:
    print("      无需要压缩的文件")
PRELOAD

# 打字练习正式题库（启动时由 release_typing_bank 导入；不进 Web 目录，不对外暴露）
BANK_SRC="$SRC/typing-bank2/dist/全部.jsonl"
if [ -f "$BANK_SRC" ]; then
    mkdir -p "$OUT/typing-bank"
    cp "$BANK_SRC" "$OUT/typing-bank/bank.jsonl"
    echo "      题库 $(wc -l < "$BANK_SRC" | tr -d ' ') 篇，$(du -h "$BANK_SRC" | cut -f1)"
else
    echo "      ⚠️  未找到 typing-bank2/dist/全部.jsonl，打字练习将无题可用"
fi

for f in server.py start.sh requirements.txt; do
    [ -f "$OUT/$f" ] || { echo "缺少 $OUT/$f，发布包不完整" >&2; exit 1; }
done

printf '%s\n%s\n' "$SHA" "$COMMIT_SUBJECT" > "$OUT/VERSION"

echo "[5/5] 完成：$OUT ($(du -sh "$OUT" | cut -f1))，版本 $SHA"
echo
echo "下一步：在 WorkBuddy 里说一句「把 deploy/public 发布上线」，它会重新发布到同一个链接。"
