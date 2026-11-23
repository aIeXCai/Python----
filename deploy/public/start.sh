#!/usr/bin/env bash
# 公网演示版启动脚本：初始化空库 → 导入课程数据 → 建演示教师 → gunicorn → 单端口网关
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DATA="$ROOT/data"
PY="${PYTHON:-python3}"
PORT="${PORT:-3000}"

mkdir -p "$DATA"

# ---------- 0. 种子库 ----------
# seed/ 里是「起始版本」的数据库与密钥。规则：
#   - 没有 data/db.sqlite3          → 导入种子库
#   - 有库，但 seed/ID 与已应用的 ID 不同 → 视为"换了一版起始库"，备份旧库后导入新的（只发生一次）
#   - 有库且 ID 相同                 → 跳过，保留线上数据
# 日常发布不携带新 ID，因此不会覆盖线上新增的账号和成绩。
SEED="$ROOT/seed"
SEED_ID=""
[ -f "$SEED/ID" ] && SEED_ID="$(cat "$SEED/ID")"
APPLIED_ID=""
[ -f "$DATA/.seed_applied" ] && APPLIED_ID="$(cat "$DATA/.seed_applied")"

if [ -f "$SEED/db.sqlite3" ] && [ "$SEED_ID" != "$APPLIED_ID" ]; then
    if [ -f "$DATA/db.sqlite3" ]; then
        BAK="$DATA/db.sqlite3.bak-$(date +%Y%m%d%H%M%S)"
        echo "[start] 种子库版本变更（${APPLIED_ID:-空} -> ${SEED_ID}），先备份现有库到 $(basename "$BAK")"
        cp "$DATA/db.sqlite3" "$BAK"
    fi
    echo "[start] 导入种子数据库 $SEED_ID"
    cp "$SEED/db.sqlite3" "$DATA/db.sqlite3"
    rm -f "$DATA/db.sqlite3-wal" "$DATA/db.sqlite3-shm"
    printf '%s\n' "$SEED_ID" > "$DATA/.seed_applied"
elif [ -f "$DATA/db.sqlite3" ]; then
    echo "[start] 数据库已存在，种子未变更，跳过导入（保留线上数据）"
else
    echo "[start] 无种子库，将创建空库"
fi

# 学生密码密文是随种子库一起带的，运行时密钥必须与加密时那把一致，否则解密全部失败：
# 列表接口只校验状态字段仍显示"可查看"，点开却返回 409「密码不可查看，请为学生重置密码」。
# 旧逻辑是"data 里没有才导入种子密钥"，但早期部署已由下面的兜底逻辑生成了一把随机密钥
# （key_id 同样是 stage3-v1），于是种子密钥永远不会被采纳，841 个学生全部不可查。
# 现在改为以种子密钥为准：内容不同则先备份旧文件再覆盖，保证一次性修复。
if [ -s "$SEED/password_keys.env" ]; then
    if [ -s "$DATA/password_keys.env" ] && ! cmp -s "$SEED/password_keys.env" "$DATA/password_keys.env"; then
        BAK="$DATA/password_keys.env.old-$(date +%Y%m%d%H%M%S)"
        echo "[start] 运行时学生密码密钥与种子不一致，备份旧密钥到 $(basename "$BAK")，改用种子密钥"
        cp "$DATA/password_keys.env" "$BAK"
    fi
    cp "$SEED/password_keys.env" "$DATA/password_keys.env"
fi

# ---------- 1. 首次启动生成密钥（只存于沙箱内） ----------
if [ ! -s "$DATA/secret_key" ]; then
    "$PY" -c "import secrets;print(secrets.token_urlsafe(50))" > "$DATA/secret_key"
fi
export DJANGO_SECRET_KEY="$(cat "$DATA/secret_key")"

if [ ! -s "$DATA/password_keys.env" ]; then
    "$PY" - "$DATA/password_keys.env" <<'PYEOF'
import sys
from cryptography.fernet import Fernet
with open(sys.argv[1], "w") as fh:
    fh.write("DJANGO_STUDENT_PASSWORD_KEYS=stage3-v1:%s\n" % Fernet.generate_key().decode())
    fh.write("DJANGO_STUDENT_PASSWORD_PRIMARY_KEY_ID=stage3-v1\n")
PYEOF
fi
set -a
# shellcheck disable=SC1090
. "$DATA/password_keys.env"
set +a

# ---------- 2. Django 运行环境 ----------
# 演示环境使用 SQLite；项目生产模式强制要求 MySQL，这里显式以 development 运行并关闭 DEBUG，
# 关闭生产专属的强制 HTTPS/Cookie 安全开关（对外由平台域名提供 HTTPS）。
export DJANGO_ENV=development
export DJANGO_DEBUG=false
export DJANGO_DB_ENGINE=sqlite
export DJANGO_DB_NAME="$DATA/db.sqlite3"
export DJANGO_ALLOWED_HOSTS='*'
export DJANGO_CORS_ALLOWED_ORIGINS=''
export DJANGO_CSRF_TRUSTED_ORIGINS=''
export DJANGO_SECURE_SSL_REDIRECT=false
export DJANGO_SESSION_COOKIE_SECURE=false
export DJANGO_CSRF_COOKIE_SECURE=false
export DJANGO_LOG_LEVEL=INFO
# 演示版不启用服务端代码执行（学生端 Python 由浏览器内 Pyodide 完成）
export CODE_EXECUTION_ENABLED=false
export EXECUTION_REQUIRE_HEALTHY_RUNNER=false
# 打字练习使用正式题库（随包携带，首次启动导入；否则题池为空）
export TYPING_PRACTICE_FORMAL=true

cd "$ROOT/app"

# 迁移前先备份现有库（保留最近 3 份），避免新版本迁移出问题时无路可退
if [ -f "$DATA/db.sqlite3" ]; then
    mkdir -p "$DATA/backups"
    BAK="$DATA/backups/db-$(date +%Y%m%d%H%M%S).sqlite3"
    cp "$DATA/db.sqlite3" "$BAK"
    echo "[start] 迁移前备份：$(basename "$BAK")"
    ls -1t "$DATA/backups"/db-*.sqlite3 2>/dev/null | tail -n +4 | xargs rm -f 2>/dev/null || true
fi

echo "[start] 迁移数据库"
"$PY" manage.py migrate --noinput

# 密钥自检：启动日志里直接给出「能解出多少 / 解不出多少」，
# 避免再次出现"接口说可查看、点开却 409"这种只在用户侧才暴露的问题。
echo "[start] 校验学生密码可解密情况"
"$PY" manage.py shell -c "
from django.conf import settings
from users.models import CustomUser
from users.security import StudentPasswordCipher, PasswordEncryptionError
cipher = StudentPasswordCipher(settings.STUDENT_PASSWORD_KEY_CONFIG)
ok = bad = 0
qs = CustomUser.objects.filter(role='student', password_recovery_status='available').exclude(encrypted_password='')
for u in qs.iterator():
    try:
        cipher.decrypt(u.encrypted_password, u.password_encryption_key_id)
        ok += 1
    except PasswordEncryptionError:
        bad += 1
print('[start] 学生密码可解密 %d / 不可解密 %d' % (ok, bad))
" 2>/dev/null | tail -n 1 || echo "[start] ⚠️ 密钥自检失败（不影响启动）"

UNIT_COUNT="$("$PY" manage.py shell -c "from info_tech.models import Unit; print(Unit.objects.count())" | tail -n 1)"
if [ "$UNIT_COUNT" = "0" ]; then
    echo "[start] 首次导入课程数据"
    "$PY" manage.py loaddata \
        info_tech/fixtures/current_curriculum.json \
        ai_courses/fixtures/current_ai_catalog.json
fi

# 打字题库：release_typing_bank 把已核对文章写入正式题池。
# 以前只在题池为空时导入，题库换代后线上仍跑旧文章；现在按 bank.jsonl 的指纹判断，
# 题库一变就重新发布（release 会把清单外的旧版本统一降为待审，等于自动下线旧文章）。
BANK="$ROOT/typing-bank/bank.jsonl"
if [ -f "$BANK" ]; then
    BANK_ID="$("$PY" -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$BANK")"
    BANK_APPLIED=""
    [ -f "$DATA/.bank_applied" ] && BANK_APPLIED="$(cat "$DATA/.bank_applied")"
    if [ "$BANK_ID" != "$BANK_APPLIED" ]; then
        echo "[start] 题库版本变更（${BANK_APPLIED:-无} -> $BANK_ID），导入打字题库（$(wc -l < "$BANK" | tr -d ' ') 篇）"
        if "$PY" manage.py release_typing_bank "$BANK"; then
            printf '%s\n' "$BANK_ID" > "$DATA/.bank_applied"
        else
            echo "[start] ⚠️ 题库导入失败，保留线上现有题库"
        fi
    else
        echo "[start] 打字题库已是最新版本，跳过导入"
    fi
fi

echo "[start] 确保演示教师账号存在""$PY" manage.py shell -c "
from users.models import CustomUser
u, created = CustomUser.objects.get_or_create(
    username='demo',
    defaults={'role': 'teacher', 'is_staff': True, 'is_superuser': True, 'email': 'demo@example.com'},
)
if created:
    u.set_password('Demo2026')
    u.save()
print('demo teacher', 'created' if created else 'exists')
" || echo "[start] 演示账号创建失败，忽略"

# ---------- 3. 启动 Django ----------
echo "[start] 启动 gunicorn"
gunicorn school_platform.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 2 \
    --threads 4 \
    --timeout 90 \
    --access-logfile - \
    --error-logfile - &

for _ in $(seq 1 60); do
    if "$PY" -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health/live/',timeout=2)" 2>/dev/null; then
        echo "[start] Django 就绪"
        break
    fi
    sleep 1
done

# ---------- 4. 单端口网关 ----------
exec "$PY" "$ROOT/server.py"
