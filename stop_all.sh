#!/bin/bash
# 停止 Python 学习平台全部服务

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
ok()   { echo -e "${GREEN}[ OK ]${NC}  $1"; }
warn() { echo -e "${RED}[STOP]${NC}  $1"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server_pids"

echo ""
echo "========================================"
echo "  停止全部服务"
echo "========================================"

if [ -f "$PID_FILE" ]; then
    for pid in $(cat "$PID_FILE"); do
        if [ -n "$pid" ] && kill -0 $pid 2>/dev/null; then
            kill $pid 2>/dev/null && ok "已停止 PID $pid" || true
        fi
    done
    rm -f "$PID_FILE"
fi

# 安全清理：强制关闭占用端口的进程
for port in 8080 5173 5000; do
    pid=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null && warn "强制关闭端口 $port (PID $pid)" || true
    fi
done

echo ""
ok "所有服务已停止"
echo "========================================"
echo ""
