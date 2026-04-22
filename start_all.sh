#!/bin/bash
# ============================================================
# Python 学习平台 — 一键启动所有服务
# ============================================================
# 服务端口：
#   8080 — Django 后端（主 API）
#   5173 — Vite 前端开发服务器
#   5000 — server.py（遗留兼容，可选）
# ============================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/opt/miniconda3/envs/pylearn/bin/python"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
ok()    { echo -e "${GREEN}[ OK ]${NC}  $1"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $1"; }

# ---------- 清理旧进程 ----------
cleanup() {
    info "正在停止已有服务..."
    for port in 8080 5173 5000; do
        pid=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$pid" ]; then
            kill $pid 2>/dev/null && ok "已停止端口 $port (PID $pid)" || true
        fi
    done
    sleep 1
}

# ---------- 检查端口 ----------
check_port() {
    if lsof -i:$1 >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# ---------- 等待服务就绪 ----------
wait_for() {
    local url=$1
    local name=$2
    local maxwait=15
    local count=0
    while [ $count -lt $maxwait ]; do
        if curl -s --max-time 2 "$url" >/dev/null 2>&1; then
            ok "$name 已就绪 ($url)"
            return 0
        fi
        count=$((count + 1))
        sleep 1
    done
    fail "$name 启动超时（${maxwait}s）"
    return 1
}

# ============================================================
# 主流程
# ============================================================

echo ""
echo "========================================"
echo "  Python 学习平台 — 启动脚本"
echo "========================================"
echo ""

# 检查 Python 环境
if [ ! -x "$PYTHON" ]; then
    warn "未找到 /opt/miniconda3/envs/pylearn/bin/python，尝试 python3"
    PYTHON="python3"
fi

"$PYTHON" -c "import django" 2>/dev/null || {
    fail "Django 未安装，请先：pip install django djangorestframework django-cors-headers"
    exit 1
}
ok "Python 环境检查通过 ($PYTHON)"

# 检查 npm
if ! command -v npm >/dev/null 2>&1; then
    fail "npm 未安装，请先安装 Node.js"
    exit 1
fi
ok "npm 检查通过 ($(npm --version))"

# 清理旧进程
cleanup

# ---- 1. 启动 Django ----
info "启动 Django 后端 (端口 8080)..."
cd "$SCRIPT_DIR/backend"
nohup "$PYTHON" manage.py runserver 8080 > "$LOG_DIR/django.log" 2>&1 &
DJANGO_PID=$!
ok "Django 已启动 (PID $DJANGO_PID)"

# ---- 2. 启动 Vite 前端 ----
info "启动 Vite 前端 (端口 5173)..."
cd "$SCRIPT_DIR/frontend"
nohup npm run dev > "$LOG_DIR/vite.log" 2>&1 &
VITE_PID=$!
ok "Vite 已启动 (PID $VITE_PID)"

# ---- 3. 启动 server.py (可选) ----
if [ -f "$SCRIPT_DIR/server.py" ]; then
    info "启动 server.py (端口 5000，可选)..."
    cd "$SCRIPT_DIR"
    nohup "$PYTHON" server.py > "$LOG_DIR/server.log" 2>&1 &
    SERVER_PID=$!
    ok "server.py 已启动 (PID $SERVER_PID)"
fi

# ---- 等待服务就绪 ----
echo ""
info "等待服务启动..."
wait_for "http://localhost:8080/api/ai/admin/dashboard/" "Django API"
wait_for "http://localhost:5173/" "Vite 前端"
[ -n "$SERVER_PID" ] && wait_for "http://localhost:5000/" "server.py"

# ---- 完成 ----
echo ""
echo "========================================"
ok  "全部服务启动完成！"
echo "========================================"
echo ""
echo "  前端页面：  http://localhost:5173"
echo "  学生登录：  http://localhost:5173/login"
echo "  老师登录：  http://localhost:5173/teacher-login"
echo "  Django API：http://localhost:8080"
echo ""
echo "  老师账号：  alex / teacher123"
echo "  学生账号：  張小華 / pass123（八年級/7班）"
echo ""
echo "  日志文件："
echo "    $LOG_DIR/django.log"
echo "    $LOG_DIR/vite.log"
[ -n "$SERVER_PID" ] && echo "    $LOG_DIR/server.log"
echo ""
echo "  停止全部服务：bash start_all.sh --stop"
echo "========================================"

# 保存 PID 供停止使用
echo "$DJANGO_PID $VITE_PID ${SERVER_PID:-}" > "$SCRIPT_DIR/.server_pids"
