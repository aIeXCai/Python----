#!/usr/bin/env bash
# 把教室机的数据库整理成「种子库」，供公网版首次初始化使用。
#
# 用法：
#   bash deploy/prepare_seed.sh <db.sqlite3 路径> [.env.security.local 路径]
#
# 做的事：复制 → 清理 Runner 历史回执 → VACUUM 压缩 → 校验完整性 → 转换密钥文件格式
set -Eeuo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="$DEPLOY_DIR/public/seed"

if [ $# -lt 1 ]; then
    echo "用法：bash deploy/prepare_seed.sh <db.sqlite3> [.env.security.local]" >&2
    exit 1
fi

SRC_DB="$1"
SRC_KEY="${2:-}"
[ -f "$SRC_DB" ] || { echo "找不到数据库文件：$SRC_DB" >&2; exit 1; }

mkdir -p "$OUT"
TMP="$OUT/db.sqlite3"

echo "[1/5] 复制数据库（$(du -h "$SRC_DB" | cut -f1)）"
cp "$SRC_DB" "$TMP"
# 若源库带 WAL，一并落盘
[ -f "$SRC_DB-wal" ] && cp "$SRC_DB-wal" "$TMP-wal" || true

echo "[2/5] 清理 Runner 历史回执并压缩"
python3 - "$TMP" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
cur = con.cursor()
for table in ("execution_runnerrequestreceipt",):
    try:
        n = cur.execute(f"delete from {table}").rowcount
        print(f"      清理 {table}: 删除 {n} 行")
    except sqlite3.Error as exc:
        print(f"      跳过 {table}: {exc}")
con.commit()
cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
con.execute("VACUUM")
con.close()
PY

echo "[3/5] 校验完整性"
python3 - "$TMP" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
ok = con.execute("PRAGMA integrity_check").fetchone()[0]
print("      integrity_check:", ok)
if ok != "ok":
    sys.exit(1)
for label, sql in {
    "用户": "select count(*) from users_customuser",
    "学生": "select count(*) from users_customuser where role='student'",
    "小测场次": "select count(*) from info_tech_quizsession",
    "小测提交": "select count(*) from info_tech_quizsubmission",
    "信息课题目": "select count(*) from info_tech_question",
    "AI 题目": "select count(*) from ai_courses_aichoicequestion",
}.items():
    try:
        print(f"      {label}: {con.execute(sql).fetchone()[0]}")
    except sqlite3.Error:
        print(f"      {label}: 表不存在（旧版本库？）")
con.close()
PY

echo "[4/5] 转换学生密码密钥"
if [ -n "$SRC_KEY" ] && [ -f "$SRC_KEY" ]; then
    KEYS="$(grep -E '^DJANGO_STUDENT_PASSWORD_KEYS=' "$SRC_KEY" | head -1)"
    IDS="$(grep -E '^DJANGO_STUDENT_PASSWORD_PRIMARY_KEY_ID=' "$SRC_KEY" | head -1)"
    if [ -z "$KEYS" ] || [ -z "$IDS" ]; then
        echo "      密钥文件里没找到 DJANGO_STUDENT_PASSWORD_KEYS / PRIMARY_KEY_ID，学生密码将无法解密" >&2
    else
        printf '%s\n%s\n' "$KEYS" "$IDS" > "$OUT/password_keys.env"
        chmod 600 "$OUT/password_keys.env"
        echo "      已写入 seed/password_keys.env（密钥 ID：${IDS#*=}）"
    fi
else
    echo "      未提供密钥文件：种子库里的学生密码将无法在线上查看（不影响登录）"
fi

echo "[5/5] 生成种子版本号"
SEED_ID="$(python3 - "$TMP" <<'PY'
import hashlib, sys
h = hashlib.sha256()
with open(sys.argv[1], "rb") as fh:
    for chunk in iter(lambda: fh.read(1 << 20), b""):
        h.update(chunk)
print(h.hexdigest()[:12])
PY
)"
printf '%s\n' "$SEED_ID" > "$OUT/ID"
echo "      ID: $SEED_ID（线上若已导入过同 ID 的种子，重启时不会重复覆盖）"

echo "[6/6] 完成"
du -sh "$OUT"
echo
echo "注意：seed/ 含真实学生数据，已在 .gitignore 中排除，不要提交到 GitHub。"
