#!/usr/bin/env bash
# 构建「可公网发布」的单端口版本到 deploy/public。
# 产物结构：app/(Django 源码) + web/(前端静态包) + problems/(AI 题目) + server.py + start.sh
set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
OUT="$DEPLOY_DIR/public"

mkdir -p "$OUT/app" "$OUT/web" "$OUT/problems"

echo "[1/4] 复制后端源码（排除数据库、密钥、本地 MySQL 数据目录）"
rsync -a --delete \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env*' \
  --exclude='db.sqlite3*' \
  --exclude='.local' \
  --exclude='migration_artifacts' \
  --exclude='media/*' \
  --exclude='submissions/*' \
  "$ROOT/backend/" "$OUT/app/"

echo "[2/4] 复制 AI 题目目录"
rsync -a --delete "$ROOT/problems/" "$OUT/problems/"

echo "[3/4] 构建前端生产包"
(cd "$ROOT/frontend" && npx vite build >/dev/null)

echo "[4/4] 同步前端产物到 web/"
rsync -a --delete "$ROOT/frontend/dist/" "$OUT/web/"

echo "完成：$OUT ($(du -sh "$OUT" | cut -f1))"
