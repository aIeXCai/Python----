#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
LOCAL_ROOT="${BACKEND_DIR}/.local/mysql-stage2"
DATA_DIR="${LOCAL_ROOT}/data"
CONFIG_FILE="${LOCAL_ROOT}/my.cnf"
PID_FILE="${LOCAL_ROOT}/mysql.pid"
LOG_FILE="${LOCAL_ROOT}/mysql.log"
ENV_FILE="${BACKEND_DIR}/.env.mysql.local"
RUNTIME_ROOT="/tmp/python-site-stage2-mysql-$(id -u)"
SOCKET_FILE="${RUNTIME_ROOT}/mysql.sock"

MYSQL_PREFIX="${MYSQL8_PREFIX:-/opt/homebrew/opt/mysql@8.0}"
MYSQLD="${MYSQL_PREFIX}/bin/mysqld"
MYSQL="${MYSQL_PREFIX}/bin/mysql"
MYSQLADMIN="${MYSQL_PREFIX}/bin/mysqladmin"

PORT=3308
TARGET_DB='python_learning_stage2'
TEST_DB='python_learning_stage2_test'
APP_USER='python_stage2'

fail() {
  echo "错误：$*" >&2
  exit 1
}

require_mysql() {
  [[ -x "${MYSQLD}" ]] || fail "未找到 MySQL 8.0，请先执行 brew install mysql@8.0"
  "${MYSQLD}" --version | grep -q 'Ver 8\.0\.' || fail "mysqld 不是 MySQL 8.0"
}

ensure_safe_paths() {
  [[ "${LOCAL_ROOT}" == "${BACKEND_DIR}/.local/mysql-stage2" ]] || fail "本地数据目录校验失败"
  [[ "${RUNTIME_ROOT}" == /tmp/python-site-stage2-mysql-* ]] || fail "运行目录校验失败"
}

write_config() {
  mkdir -p "${LOCAL_ROOT}" "${RUNTIME_ROOT}"
  chmod 700 "${LOCAL_ROOT}" "${RUNTIME_ROOT}"
  umask 077
  printf '%s\n' \
    '[mysqld]' \
    "basedir=${MYSQL_PREFIX}" \
    "datadir=${DATA_DIR}" \
    "port=${PORT}" \
    "socket=${SOCKET_FILE}" \
    "pid-file=${PID_FILE}" \
    "log-error=${LOG_FILE}" \
    'bind-address=127.0.0.1' \
    'mysqlx=0' \
    'local-infile=0' \
    'secure-file-priv=NULL' \
    'skip-name-resolve=ON' \
    'character-set-server=utf8mb4' \
    'collation-server=utf8mb4_0900_ai_ci' \
    > "${CONFIG_FILE}"
  chmod 600 "${CONFIG_FILE}"
}

is_running() {
  [[ -S "${SOCKET_FILE}" ]] && "${MYSQLADMIN}" --protocol=socket --socket="${SOCKET_FILE}" -uroot ping >/dev/null 2>&1
}

wait_until_running() {
  local attempt
  for attempt in {1..60}; do
    if is_running; then
      return 0
    fi
    sleep 0.25
  done
  tail -30 "${LOG_FILE}" >&2 2>/dev/null || true
  fail "MySQL 未能在 15 秒内启动"
}

root_sql() {
  "${MYSQL}" --protocol=socket --socket="${SOCKET_FILE}" -uroot "$@"
}

command_install_check() {
  require_mysql
  "${MYSQLD}" --version
  "${MYSQL}" --version
}

command_init() {
  require_mysql
  ensure_safe_paths
  write_config
  if [[ -d "${DATA_DIR}/mysql" ]]; then
    echo "MySQL 隔离数据目录已经初始化。"
    return
  fi
  mkdir -p "${DATA_DIR}"
  chmod 700 "${DATA_DIR}"
  "${MYSQLD}" --defaults-file="${CONFIG_FILE}" --initialize-insecure
  echo "MySQL 8.0 隔离数据目录初始化完成。"
}

command_start() {
  require_mysql
  ensure_safe_paths
  [[ -f "${CONFIG_FILE}" ]] || fail "实例尚未初始化，请先执行 init"
  mkdir -p "${RUNTIME_ROOT}"
  chmod 700 "${RUNTIME_ROOT}"
  if is_running; then
    echo "MySQL 8.0 已在 127.0.0.1:${PORT} 运行。"
    return
  fi
  rm -f "${SOCKET_FILE}" "${PID_FILE}"
  "${MYSQLD}" --defaults-file="${CONFIG_FILE}" --daemonize
  wait_until_running
  echo "MySQL 8.0 已在 127.0.0.1:${PORT} 启动。"
}

command_status() {
  require_mysql
  if ! is_running; then
    fail "MySQL 8.0 当前未运行"
  fi
  local version
  version="$(root_sql --batch --skip-column-names -e 'SELECT VERSION();')"
  [[ "${version}" == 8.0.* ]] || fail "服务端版本不是 MySQL 8.0"
  echo "MySQL 服务端版本：${version}"
  echo "监听地址：127.0.0.1:${PORT}"
}

write_env_file() {
  local password="$1"
  umask 077
  printf '%s\n' \
    'DJANGO_ENV=development' \
    'DJANGO_DB_ENGINE=mysql' \
    "DJANGO_DB_NAME=${TARGET_DB}" \
    "DJANGO_DB_USER=${APP_USER}" \
    "DJANGO_DB_PASSWORD=${password}" \
    'DJANGO_DB_HOST=127.0.0.1' \
    "DJANGO_DB_PORT=${PORT}" \
    'DJANGO_DB_CONN_MAX_AGE=30' \
    'DJANGO_DB_CONNECT_TIMEOUT=5' \
    "DJANGO_DB_TEST_NAME=${TEST_DB}" \
    > "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
}

command_provision() {
  is_running || fail "MySQL 尚未运行"
  local password
  if [[ -f "${ENV_FILE}" ]]; then
    password="$(sed -n 's/^DJANGO_DB_PASSWORD=//p' "${ENV_FILE}")"
    [[ -n "${password}" ]] || fail "本地环境文件缺少数据库密码"
  else
    password="$(openssl rand -hex 24)"
  fi

  root_sql <<SQL
CREATE DATABASE IF NOT EXISTS \`${TARGET_DB}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE IF NOT EXISTS \`${TEST_DB}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS '${APP_USER}'@'127.0.0.1' IDENTIFIED BY '${password}';
ALTER USER '${APP_USER}'@'127.0.0.1' IDENTIFIED BY '${password}';
GRANT ALL PRIVILEGES ON \`${TARGET_DB}\`.* TO '${APP_USER}'@'127.0.0.1';
GRANT ALL PRIVILEGES ON \`${TEST_DB}\`.* TO '${APP_USER}'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
  write_env_file "${password}"
  echo "MySQL 测试数据库和最小权限用户已创建。"
  echo "本地凭据已写入被 Git 忽略的 backend/.env.mysql.local。"
}

reset_database() {
  local database="$1"
  is_running || fail "MySQL 尚未运行"
  case "${database}" in
    "${TARGET_DB}"|"${TEST_DB}") ;;
    *) fail "拒绝重建未授权数据库：${database}" ;;
  esac
  root_sql <<SQL
DROP DATABASE IF EXISTS \`${database}\`;
CREATE DATABASE \`${database}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
GRANT ALL PRIVILEGES ON \`${database}\`.* TO '${APP_USER}'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL
  echo "已重建本地测试数据库：${database}"
}

command_stop() {
  if is_running; then
    "${MYSQLADMIN}" --protocol=socket --socket="${SOCKET_FILE}" -uroot shutdown
  fi
  rm -f "${SOCKET_FILE}" "${PID_FILE}"
  echo "MySQL 8.0 已停止。"
}

command_destroy() {
  ensure_safe_paths
  command_stop
  [[ "${LOCAL_ROOT}" == "${BACKEND_DIR}/.local/mysql-stage2" ]] || fail "拒绝删除未知目录"
  rm -rf "${LOCAL_ROOT}"
  rm -rf "${RUNTIME_ROOT}"
  rm -f "${ENV_FILE}"
  echo "阶段 2 隔离实例和本地凭据已删除。"
}

usage() {
  echo "用法：$0 {install-check|init|start|status|provision|reset-target|reset-test|stop|destroy}"
}

main() {
  ensure_safe_paths
  case "${1:-}" in
    install-check) command_install_check ;;
    init) command_init ;;
    start) command_start ;;
    status) command_status ;;
    provision) command_provision ;;
    reset-target) reset_database "${TARGET_DB}" ;;
    reset-test) reset_database "${TEST_DB}" ;;
    stop) command_stop ;;
    destroy) command_destroy ;;
    *) usage; exit 2 ;;
  esac
}

main "$@"
