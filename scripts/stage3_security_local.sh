#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"
BACKEND_DIR="${PROJECT_ROOT}/backend"
ENV_FILE="${BACKEND_DIR}/.env.security.local"

fail() {
  echo "错误：$*" >&2
  exit 1
}

ensure_safe_path() {
  [[ "${ENV_FILE}" == "${PROJECT_ROOT}/backend/.env.security.local" ]] || fail "本地安全文件路径校验失败"
  [[ "${PROJECT_ROOT}" != "/" ]] || fail "项目路径校验失败"
}

command_init() {
  ensure_safe_path
  if [[ -e "${ENV_FILE}" ]]; then
    echo "本地学生密码密钥已经存在；未覆盖。"
    return
  fi
  STAGE3_ENV_FILE="${ENV_FILE}" python - <<'PY'
import os
from pathlib import Path
from cryptography.fernet import Fernet

target = Path(os.environ['STAGE3_ENV_FILE']).resolve()
expected = (target.parent / '.env.security.local').resolve()
if target != expected or target.name != '.env.security.local':
    raise SystemExit('本地安全文件路径校验失败')
target.parent.mkdir(parents=True, exist_ok=True)
key = Fernet.generate_key().decode('ascii')
content = (
    f'DJANGO_STUDENT_PASSWORD_KEYS=stage3-v1:{key}\n'
    'DJANGO_STUDENT_PASSWORD_PRIMARY_KEY_ID=stage3-v1\n'
    'DJANGO_TOKEN_TTL_HOURS=12\n'
    'DJANGO_PASSWORD_REVEAL_LIMIT=30\n'
    'DJANGO_PASSWORD_REVEAL_SECONDS=30\n'
)
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w', encoding='utf-8') as stream:
    stream.write(content)
os.chmod(target, 0o600)
PY
  echo "本地学生密码密钥已生成到被 Git 忽略的 backend/.env.security.local。"
}

command_status() {
  ensure_safe_path
  [[ -f "${ENV_FILE}" ]] || fail "本地安全文件不存在，请先执行 init"
  local mode
  mode="$(stat -f '%Lp' "${ENV_FILE}")"
  [[ "${mode}" == "600" ]] || fail "本地安全文件权限必须为 600，当前为 ${mode}"
  STAGE3_ENV_FILE="${ENV_FILE}" PYTHONPATH="${BACKEND_DIR}" python - <<'PY'
import os
from dotenv import dotenv_values
from users.security import parse_password_key_config

values = dotenv_values(os.environ['STAGE3_ENV_FILE'])
config = parse_password_key_config(
    values.get('DJANGO_STUDENT_PASSWORD_KEYS', ''),
    values.get('DJANGO_STUDENT_PASSWORD_PRIMARY_KEY_ID', ''),
)
if not config.configured:
    raise SystemExit('本地学生密码密钥配置无效')
print('本地学生密码密钥配置有效（密钥内容未显示）。')
PY
}

command_destroy() {
  ensure_safe_path
  [[ -e "${ENV_FILE}" ]] || {
    echo "本地安全文件不存在。"
    return
  }
  STAGE3_ENV_FILE="${ENV_FILE}" python - <<'PY'
import os
from pathlib import Path

target = Path(os.environ['STAGE3_ENV_FILE']).resolve()
if target.name != '.env.security.local' or target.parent.name != 'backend':
    raise SystemExit('拒绝删除未知文件')
target.unlink()
PY
  echo "本地学生密码密钥文件已删除；使用该密钥的密码密文将无法解密。"
}

usage() {
  echo "用法：$0 {init|status|destroy}"
}

case "${1:-}" in
  init) command_init ;;
  status) command_status ;;
  destroy) command_destroy ;;
  *) usage; exit 1 ;;
esac
