# 阶段 1 配置与验证手册

日期：2026-09-01

## 1. 本地开发启动

### 1.1 启动后端

```bash
cd backend
DJANGO_ENV=development python manage.py runserver 127.0.0.1:8080
```

开发模式默认：

- `DEBUG=True`
- 允许 `localhost`、`127.0.0.1` 和 `[::1]`
- 使用仅限本地的开发密钥
- 关闭全开放 CORS

### 1.2 启动前端

另开一个终端：

```bash
cd frontend
npm run dev
```

不要设置 `VITE_API_BASE_URL`。浏览器会请求前端域名下的 `/api/...`，Vite 再代理至 `http://127.0.0.1:8080`。

## 2. 环境变量

后端示例见 `backend/.env.example`，前端示例见 `frontend/.env.example`。

| 变量 | 必填环境 | 说明 |
|---|---|---|
| `DJANGO_ENV` | 全部 | `development`、`test` 或 `production` |
| `DJANGO_SECRET_KEY` | production | 至少 32 位的随机生产密钥 |
| `DJANGO_DEBUG` | production | 必须为 `false` |
| `DJANGO_ALLOWED_HOSTS` | production | 逗号分隔域名，禁止 `*` |
| `DJANGO_CORS_ALLOWED_ORIGINS` | 跨域时 | 逗号分隔的 HTTPS 来源；同源部署留空 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | production | 例如 `https://learn.example.com` |
| `DJANGO_LOG_LEVEL` | 可选 | 默认 `INFO`，测试默认 `WARNING` |
| `VITE_API_BASE_URL` | 特殊前端部署 | 默认不设置，使用 `/api` |

真实 `.env` 文件已被 Git 忽略，不要把生产密钥写进 `.env.example` 或其他仓库文件。

## 3. 健康检查

后端直接检查：

```bash
curl -i http://127.0.0.1:8080/api/health/live/
curl -i http://127.0.0.1:8080/api/health/ready/
```

预期均返回 HTTP 200：

```json
{"status": "ok"}
```

前端开发代理检查：

```bash
curl -i http://127.0.0.1:5173/api/health/live/
curl -i http://127.0.0.1:5173/api/health/ready/
```

这两项成功说明浏览器同源 `/api` 可以经 Vite 到达 Django。

## 4. 自动验证

### 4.1 后端阶段测试

```bash
cd backend
DJANGO_ENV=test python manage.py test school_platform.tests -v 2
```

预期：18 项测试全部通过。

### 4.2 前端地址验证

```bash
cd frontend
npm run verify:api-config
rg -n "http://localhost:8080/api" src
```

预期：第一条显示 `API config verification passed`；第二条无输出。

Vitest 定向命令：

```bash
npx vitest run src/api/config.test.js src/api/index.test.js
```

当前仓库存在 Vitest 启动后停在 `RUN` 的既有基线问题。如仍复现，使用 `Ctrl+C` 终止，并保留上述独立验证结果；该基线问题记录在路线图阶段 9，不得误报为测试通过。

## 5. 生产配置安全检查

以下密钥只用于本地检查，不是可投入使用的真实生产密钥：

```bash
cd backend
DJANGO_ENV=production \
DJANGO_SECRET_KEY='replace-this-with-a-real-random-secret-over-32-characters' \
DJANGO_ALLOWED_HOSTS='example.test' \
DJANGO_CSRF_TRUSTED_ORIGINS='https://example.test' \
DJANGO_DB_ENGINE=mysql \
DJANGO_DB_NAME=python_learning \
DJANGO_DB_USER=python_learning \
DJANGO_DB_PASSWORD='replace-with-database-password' \
DJANGO_DB_HOST=127.0.0.1 \
DJANGO_DB_PORT=3306 \
python manage.py check --deploy
```

阶段 2 起 production 强制使用 MySQL。上述命令需要目标 MySQL 可连接；预期为 `System check identified no issues`。

以下危险配置必须失败：

```bash
DJANGO_ENV=production DJANGO_SECRET_KEY='' DJANGO_ALLOWED_HOSTS='example.test' python manage.py check
```

预期：提示必须设置 `DJANGO_SECRET_KEY`，退出码非 0。

```bash
DJANGO_ENV=production \
DJANGO_SECRET_KEY='replace-this-with-a-real-random-secret-over-32-characters' \
DJANGO_ALLOWED_HOSTS='*' \
python manage.py check
```

预期：提示 `DJANGO_ALLOWED_HOSTS` 不能包含 `*`，退出码非 0。

```bash
DJANGO_ENV=production \
DJANGO_SECRET_KEY='replace-this-with-a-real-random-secret-over-32-characters' \
DJANGO_ALLOWED_HOSTS='example.test' \
DJANGO_DEBUG=true \
python manage.py check
```

预期：提示生产环境必须关闭 DEBUG，退出码非 0。

## 6. 浏览器人工验证

1. 按第 1 节启动前后端。
2. 打开 Vite 输出的网址，通常为 `http://127.0.0.1:5173`。
3. 按 `F12` 打开开发者工具，进入 Network。
4. 完成一次学生登录，筛选 `Fetch/XHR`，确认请求 URL 以当前前端域名的 `/api/auth/login/` 开头。
5. 注销后完成一次教师登录，确认请求同样走 `/api/auth/login/`。
6. 学生端打开一道编程题；教师端打开学生管理或题库管理，确认各至少一个 `/api/...` 请求返回 200。
7. 在浏览器分别打开 `/api/health/live/` 与 `/api/health/ready/`，确认显示 `{"status":"ok"}`。
8. Network 中不应出现固定的 `http://localhost:8080/api` 请求。
