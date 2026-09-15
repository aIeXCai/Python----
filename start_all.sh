#!/usr/bin/env bash
# Start Django, Local Runner, and Vite for local/classroom use.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$SCRIPT_DIR/.server_pids"
mkdir -p "$LOG_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
info() { printf "${CYAN}[INFO]${NC}  %s\n" "$1"; }
warn() { printf "${YELLOW}[WARN]${NC}  %s\n" "$1"; }
ok() { printf "${GREEN}[ OK ]${NC}  %s\n" "$1"; }
fail() { printf "${RED}[FAIL]${NC}  %s\n" "$1" >&2; }

if [[ "${1:-}" == "--stop" ]]; then
    exec bash "$SCRIPT_DIR/stop_all.sh"
fi

choose_python() {
    local candidate
    for candidate in \
        "$SCRIPT_DIR/.venv/bin/python" \
        "/opt/miniconda3/envs/pylearn/bin/python" \
        "$(command -v python3 2>/dev/null || true)" \
        "$(command -v python 2>/dev/null || true)"; do
        if [[ -n "$candidate" && -x "$candidate" ]]; then
            PYTHON="$candidate"
            return
        fi
    done
    fail "未找到可用的 Python。"
    exit 1
}

wait_for_url() {
    local url="$1" name="$2" count
    for count in {1..20}; do
        if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
            ok "$name 已就绪 ($url)"
            return 0
        fi
        sleep 1
    done
    fail "$name 启动超时，请查看 logs 目录。"
    return 1
}

port_is_busy() {
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

cleanup_failed_start() {
    local code=$?
    trap - ERR
    fail "启动未完成，正在回收已启动的本项目进程。"
    bash "$SCRIPT_DIR/stop_all.sh" --quiet || true
    exit "$code"
}
trap cleanup_failed_start ERR

printf '\n========================================\n'
printf '  Python 学习平台 — 一键启动\n'
printf '========================================\n\n'

choose_python
"$PYTHON" -c "import django, psutil, requests" 2>/dev/null || {
    fail "Python 依赖不完整，请在虚拟环境中安装 requirements.txt。"
    exit 1
}
command -v npm >/dev/null 2>&1 || { fail "npm 未安装，请先安装 Node.js。"; exit 1; }
NODE="$(command -v node 2>/dev/null || true)"
[[ -n "$NODE" && -x "$NODE" ]] || { fail "node 不可用。"; exit 1; }
command -v curl >/dev/null 2>&1 || { fail "curl 不可用。"; exit 1; }
command -v lsof >/dev/null 2>&1 || { fail "lsof 不可用。"; exit 1; }
[[ -d "$SCRIPT_DIR/frontend/node_modules" ]] || {
    fail "前端依赖不存在，请先在 frontend 目录执行 npm ci。"
    exit 1
}
ok "环境检查通过 ($PYTHON)"

bash "$SCRIPT_DIR/stop_all.sh" --quiet || true
for port in 8080 5173; do
    if port_is_busy "$port"; then
        fail "端口 $port 已被非本项目进程占用，请先释放该端口。"
        exit 1
    fi
done

"$PYTHON" "$SCRIPT_DIR/scripts/init_local_runner.py"
[[ -f "$SCRIPT_DIR/backend/.env.security.local" ]] || \
    warn "未找到 backend/.env.security.local，教师创建学生/查看密码功能将不可用。"

export DJANGO_ENV="${DJANGO_ENV:-development}"
export DJANGO_DB_ENGINE="${DJANGO_DB_ENGINE:-sqlite}"
: > "$PID_FILE"

info "启动 Django 后端 (127.0.0.1:8080)..."
(
    cd "$SCRIPT_DIR/backend"
    nohup "$PYTHON" "$SCRIPT_DIR/backend/manage.py" runserver 127.0.0.1:8080 --noreload \
        > "$LOG_DIR/django.log" 2>&1 &
    printf 'django=%s\n' "$!" >> "$PID_FILE"
)
wait_for_url "http://127.0.0.1:8080/api/health/live/" "Django API"

info "启动 Local Runner..."
(
    cd "$SCRIPT_DIR"
    nohup "$PYTHON" "$SCRIPT_DIR/scripts/run_local_runner.py" \
        > "$LOG_DIR/runner.log" 2>&1 &
    printf 'runner=%s\n' "$!" >> "$PID_FILE"
)
(
    cd "$SCRIPT_DIR/backend"
    "$PYTHON" manage.py runner_status --wait 20
)

info "启动 Vite 前端 (0.0.0.0:5173)..."
(
    cd "$SCRIPT_DIR/frontend"
    nohup "$NODE" "$SCRIPT_DIR/frontend/node_modules/vite/bin/vite.js" \
        > "$LOG_DIR/vite.log" 2>&1 &
    printf 'vite=%s\n' "$!" >> "$PID_FILE"
)
wait_for_url "http://127.0.0.1:5173/" "Vite 前端"

trap - ERR
printf '\n========================================\n'
ok "Django、Local Runner 和 Vite 已全部就绪。"
printf '========================================\n'
printf '  学生登录：  http://localhost:5173/login\n'
printf '  教师登录：  http://localhost:5173/teacher-login\n'
printf '  Runner 状态：cd backend && "%s" manage.py runner_status\n' "$PYTHON"
printf '  日志：        %s/{django,runner,vite}.log\n' "$LOG_DIR"
printf '  停止：        bash stop_all.sh\n\n'
