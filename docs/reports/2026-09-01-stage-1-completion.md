# 阶段 1 完成报告：生产配置与同源 API

完成日期：2026-09-01
关联 PRD：`docs/prd/2026-09-01-production-alicloud-deployment-prd.md`
关联 DEV：`docs/dev/2026-09-01-production-alicloud-deployment-dev.md`

## 1. 完成内容

1. 前端新增唯一 API 地址入口，默认使用同源 `/api`，支持 `VITE_API_BASE_URL` 覆盖。
2. 学生 API、信息课 API、聊天 API、教师登录和教师管理页面均已移除固定 `localhost:8080`。
3. Vite 开发服务器增加 `/api` → `http://127.0.0.1:8080` 代理。
4. Django 新增 `development`、`test`、`production` 三种明确环境。
5. Django 密钥、DEBUG、主机白名单、CORS、CSRF 和日志级别完成环境变量化。
6. 生产环境会拒绝缺少/过短密钥、`DEBUG=True`、空主机白名单、`ALLOWED_HOSTS=*` 和非 HTTPS 跨域来源。
7. 生产环境启用 HTTPS 代理识别、安全 Cookie、HSTS、防 MIME 嗅探和点击劫持保护。
8. 新增进程存活 `/api/health/live/` 和数据库就绪 `/api/health/ready/`。
9. 新增脱敏的 400、403、404、500 JSON 错误响应。
10. 新增前后端环境示例、部署配置手册、后端测试和独立前端运行时验证。

## 2. 关键改动文件

### 前端

- `frontend/src/api/config.js`：唯一 API 地址及路径拼接入口。
- `frontend/src/api/index.js`、`chat.js`、`info.js`：统一使用同源配置。
- `frontend/src/pages/auth/TeacherLogin.jsx`：复用统一登录 API。
- `frontend/src/pages/teacher/` 下 4 个管理页面及 1 个 tab：清理零散固定地址。
- `frontend/vite.config.js`：本地 `/api` 代理。
- `frontend/scripts/verify-api-config.mjs`：不依赖 Vitest 的运行时验证。
- `frontend/.env.example`：前端变量说明。

### 后端

- `backend/school_platform/environment.py`：环境变量解析和生产安全校验。
- `backend/school_platform/settings.py`：三环境配置、安全项和控制台日志。
- `backend/school_platform/health.py`：存活与数据库就绪检查。
- `backend/school_platform/errors.py`：通用脱敏错误响应。
- `backend/school_platform/urls.py`：健康路由和错误 handler 注册。
- `backend/school_platform/tests/`：18 项阶段 1 测试。
- `backend/.env.example`：后端变量模板。
- `requirements.txt`：明确加入现有 settings 所需的 `python-dotenv`。

### 文档

- `docs/deployment/stage-1-configuration.md`：配置、启动和复验手册。
- PRD、DEV、总路线图及本完成报告。

仓库中另有不属于阶段 1 的既存/并行改动，本阶段没有覆盖或回退它们。

## 3. 自动验证结果

### 3.1 已通过

| 验证 | 结果 |
|---|---|
| 后端阶段测试 | 18/18 通过 |
| Django production `check --deploy` | 通过，0 个问题 |
| 缺少生产密钥 | 按预期退出码 1 |
| `ALLOWED_HOSTS=*` | 按预期退出码 1 |
| 生产 `DEBUG=true` | 按预期退出码 1 |
| 前端独立运行时验证 | 默认地址、路径规范化及 index/chat/info 三模块请求全部通过 |
| 前端改动文件语法解析 | 10/10 个运行时文件通过 Babel parser |
| 固定 API 地址静态搜索 | `frontend/src` 中 0 处 |
| Python 编译检查 | `backend/school_platform` 通过 |
| Git 空白/补丁检查 | `git diff --check` 通过 |

### 3.2 真实本地联调

同时启动 Django 和 Vite 后：

| 请求 | 结果 |
|---|---|
| Django `/api/health/live/` | 200，`{"status":"ok"}` |
| Django `/api/health/ready/` | 200，`{"status":"ok"}` |
| Vite `/api/health/live/` | 200，成功代理至 Django |
| Vite `/api/health/ready/` | 200，成功代理至 Django |
| Vite 首页 `/` | 200 |
| Vite 代理的无效教师登录 | 401（符合预期，证明 POST 登录链路到达 Django） |

验证完成后已停止本地 Django 和 Vite 进程。

### 3.3 全量回归及既有问题

- Django 全量测试：304 项，302 通过、2 失败。
- 两项失败仍为改造前已存在的：
  - `ProblemDetailViewTest.test_detail_includes_template_code`
  - `ProblemDetailSerializerTest.test_serializer_includes_template_code`
- 本次新增 18 项测试全部通过，没有新增后端失败。
- Python 环境另有既存 `requests` 依赖版本警告，未影响测试结果。

### 3.4 前端既有工具链阻塞

- Vitest：超过 30 秒只显示 `RUN`，未开始执行用例，手工终止。
- Vite production build：超过 60 秒停在 `transforming...`，手工终止。
- ESLint：超过 30 秒无输出，手工终止。

以上三项与网站审阅时记录的基线现象一致，已归入路线图阶段 9。阶段 1 使用独立 Node 运行时验证、语法解析、静态搜索和真实代理联调作为替代证据，未把停滞命令表述为通过。

## 4. 用户验证步骤

项目根目录：

```bash
cd "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1"
```

### 步骤 1：验证后端阶段测试

```bash
cd backend
DJANGO_ENV=test python manage.py test school_platform.tests -v 2
```

预期：显示 `Ran 18 tests` 和 `OK`。

### 步骤 2：验证前端同源配置

```bash
cd ../frontend
npm run verify:api-config
rg -n "http://localhost:8080/api" src
```

预期：第一条显示 `API config and three runtime API modules verification passed`；第二条没有输出。

### 步骤 3：启动本地后端

```bash
cd ../backend
DJANGO_ENV=development python manage.py runserver 127.0.0.1:8080
```

保持该终端运行。

### 步骤 4：启动本地前端

打开第二个终端：

```bash
cd "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/frontend"
npm run dev -- --host 127.0.0.1
```

预期显示 `http://127.0.0.1:5173/`。

### 步骤 5：验证同源健康检查

打开第三个终端：

```bash
curl -i http://127.0.0.1:5173/api/health/live/
curl -i http://127.0.0.1:5173/api/health/ready/
```

预期两条都返回 HTTP 200 和 `{"status": "ok"}`。

### 步骤 6：用浏览器验证学生端和教师端

1. 打开 `http://127.0.0.1:5173/`。
2. 按 F12，打开 Network，筛选 Fetch/XHR。
3. 使用现有学生账号登录，确认 `/api/auth/login/` 返回 200。
4. 打开一道题，确认题目请求以 `/api/ai/` 或 `/api/info/` 开头。
5. 注销后使用现有教师账号登录，打开学生管理或题库管理。
6. 确认教师请求以 `/api/...` 开头且返回 200。
7. 确认 Request URL 使用 `127.0.0.1:5173/api/...`，没有固定的 `localhost:8080/api`。

### 步骤 7：验证生产安全检查

完整命令和三组失败场景见 `docs/deployment/stage-1-configuration.md` 第 5 节。正向命令应显示 0 个问题；缺少密钥、通配主机和开启 DEBUG 都必须失败。

### 步骤 8：停止服务

分别回到前后端终端按 `Ctrl+C`。

## 5. 已知限制与下一步

- 当前正式数据库仍是 SQLite，不能用于正式教学；阶段 2 将接入 MySQL 并演练数据迁移。
- 学生代码仍未隔离，不能在公网生产环境开放；阶段 5 处理。
- 前端测试、构建和 Lint 的停滞仍需阶段 9 修复。
- 当前 2 项 Django 基线失败仍需阶段 9 修复。
- 本阶段没有购买、创建或修改任何阿里云资源。

下一步建议：先确认本阶段报告和人工验证结果，再决定何时开始阶段 2。
