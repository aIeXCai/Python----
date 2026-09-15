#!/usr/bin/env bash
# Stop only processes recorded by this project's start script.

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server_pids"
QUIET=false
[[ "${1:-}" == "--quiet" ]] && QUIET=true

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
say() { $QUIET || printf '%s\n' "$1"; }
ok() { $QUIET || printf "${GREEN}[ OK ]${NC}  %s\n" "$1"; }
warn() { $QUIET || printf "${YELLOW}[WARN]${NC}  %s\n" "$1"; }

children_of() {
    pgrep -P "$1" 2>/dev/null || true
}

signal_tree() {
    local signal="$1" pid="$2" child
    [[ "$pid" =~ ^[0-9]+$ ]] || return 0
    for child in $(children_of "$pid"); do
        signal_tree "$signal" "$child"
    done
    kill "-$signal" "$pid" 2>/dev/null || true
}

stop_pid() {
    local name="$1" pid="$2" count command marker
    [[ "$pid" =~ ^[0-9]+$ ]] || return 0
    kill -0 "$pid" 2>/dev/null || return 0
    command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    case "$name" in
        django) marker="$SCRIPT_DIR/backend/manage.py" ;;
        runner) marker="$SCRIPT_DIR/scripts/run_local_runner.py" ;;
        vite) marker="$SCRIPT_DIR/frontend" ;;
        legacy) marker='' ;;
        *) marker='__invalid_service__' ;;
    esac
    if [[ -n "$marker" && "$command" != *"$marker"* ]]; then
        warn "PID ${pid} 不再属于本项目 ${name}，已跳过。"
        return 0
    fi
    signal_tree TERM "$pid"
    for count in {1..20}; do
        kill -0 "$pid" 2>/dev/null || { ok "已停止 $name (PID $pid)"; return; }
        sleep 0.5
    done
    signal_tree KILL "$pid"
    warn "$name 未在 10 秒内退出，已强制停止 (PID $pid)"
}

say ''
say '========================================'
say '  停止 Python 学习平台'
say '========================================'

if [[ -f "$PID_FILE" ]]; then
    # Runner first: it marks itself draining and stops claiming before Web exits.
    for wanted in runner django vite; do
        while IFS='=' read -r name pid; do
            [[ "$name" == "$wanted" ]] && stop_pid "$name" "$pid"
        done < "$PID_FILE"
    done
    if ! grep -q '=' "$PID_FILE" 2>/dev/null; then
        warn "发现旧格式 PID 文件，因无法验证进程归属已跳过终止。"
    fi
    rm -f "$PID_FILE"
fi

for port in 8080 5173; do
    if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        warn "端口 $port 仍被其他进程占用（未自动终止）。"
    fi
done
ok "本项目记录的服务已停止。"
