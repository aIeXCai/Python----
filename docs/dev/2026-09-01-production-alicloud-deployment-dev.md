# 阶段 1：生产配置与同源 API 改造 DEV

关联 PRD：`docs/prd/2026-09-01-production-alicloud-deployment-prd.md`
版本：v1.0
日期：2026-09-01
状态：已完成（2026-09-01）

## 1. 实施目标

本实施只完成部署前的第一层基础能力：浏览器统一使用同源 `/api`，Django 能以开发、测试、生产三种环境安全启动，并提供日志、错误响应和健康检查。数据库仍为 SQLite，运行方式仍为本地 Django/Vite 开发服务器。

## 2. 总体技术方案

```text
浏览器
  │ fetch /api/...
  ▼
Vite（本地开发）                    未来 Nginx（生产）
  │ proxy /api                     │ proxy /api
  └──────────────► Django :8080 ◄──┘
                         │
                         ├─ /api/health/live/  进程存活
                         └─ /api/health/ready/ 数据库就绪

配置来源
  backend/.env 或进程环境变量
       └─ school_platform/environment.py：解析和安全校验
            └─ school_platform/settings.py：生成 Django 配置
```

关键选择：

- 不把 API 主机名写进各页面；所有前端模块只从 `src/api/config.js` 获取地址。
- 不拆成多份 Django settings 文件，避免本阶段大规模调整启动入口；使用 `DJANGO_ENV` 明确分支，并把解析/校验提取为可独立测试的模块。
- 生产配置采用“安全失败”：缺少密钥、开启调试或使用 `*` 主机时直接抛出 `ImproperlyConfigured`。
- 同源为默认模式，所有环境默认关闭全开放 CORS；只有显式来源列表才启用跨域白名单。
- 健康检查放在项目层，不归属具体课程 app。

## 3. 文件级改动

### 3.1 前端

#### 新增 `frontend/src/api/config.js`

导出：

- `normalizeApiBase(rawValue)`：清理空白和末尾 `/`；空值返回 `/api`。
- `API_BASE_URL`：由 `import.meta.env.VITE_API_BASE_URL` 生成，默认 `/api`。
- `apiUrl(path)`：保证路径以单个 `/` 拼接，避免双斜杠。

不在该模块读取 Token，也不承担业务错误处理。

#### 修改 API 模块

- `frontend/src/api/index.js`
- `frontend/src/api/info.js`
- `frontend/src/api/chat.js`

以上模块删除本地 `BASE_URL` / `API_BASE`，统一导入 `API_BASE_URL` 或 `apiUrl()`。SSE 仍使用原生 `fetch` 和 `ReadableStream`，不改变流式逻辑。

#### 修改教师端页面

- `frontend/src/pages/auth/TeacherLogin.jsx`：复用现有 `login()`，删除重复且写死地址的登录请求。
- `frontend/src/pages/teacher/aiAdmin.jsx`
- `frontend/src/pages/teacher/StudentManagement.jsx`
- `frontend/src/pages/teacher/InfoAdmin.jsx`
- `frontend/src/pages/teacher/tabs/Tab2Sessions.jsx`

教师管理页面从统一配置导入 API 地址；原有请求方法、鉴权头和响应处理暂不重构。`Tab2Sessions` 的弹窗请求也使用统一入口。

#### 修改 `frontend/vite.config.js`

增加开发代理：

```js
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8080',
      changeOrigin: true,
    },
  },
}
```

不重写路径。Vite 测试配置保持不变。

#### 环境示例

新增 `frontend/.env.example`：说明通常无需配置 `VITE_API_BASE_URL`；仅在前后端确实不同源时才覆盖。

### 3.2 后端

#### 新增 `backend/school_platform/environment.py`

提供可测试的纯配置函数：

- `get_environment()`：只接受 `development`、`test`、`production`。
- `get_bool(name, default)`：接受 `1/true/yes/on` 和 `0/false/no/off`，其他值报错。
- `get_list(name, default=())`：解析逗号分隔列表、去空白和空项。
- `validate_production_settings(...)`：校验生产密钥、`DEBUG`、主机、CORS 和 CSRF 来源。

校验错误只显示变量名和修复方向，不回显密钥值。

#### 修改 `backend/school_platform/settings.py`

配置规则如下：

| 配置 | development 默认 | test 默认 | production |
|---|---|---|---|
| `DJANGO_ENV` | `development` | 显式设为 `test` | 必须设为 `production` |
| `DJANGO_SECRET_KEY` | 使用仅限本地的开发值 | 使用仅限测试的固定值 | 必须显式提供且不等于开发值 |
| `DJANGO_DEBUG` | `true` | `false` | 必须为 `false` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | `testserver,localhost` | 必须显式提供，禁止 `*` |
| `DJANGO_CORS_ALLOWED_ORIGINS` | 空 | 空 | 可选，仅显式 HTTPS 来源 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 空 | 空 | 按生产域名显式提供 |
| `DJANGO_LOG_LEVEL` | `INFO` | `WARNING` | `INFO` |

生产环境额外启用：

- `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`
- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_CONTENT_TYPE_NOSNIFF=True`
- HSTS 及子域/预加载安全项
- `X_FRAME_OPTIONS='DENY'`

这些布尔项允许用相应环境变量覆盖，以便后续测试环境排障，但生产安全校验不会允许 `DEBUG=True`。

日志使用 Django `LOGGING` 字典配置输出到 console，格式包括时间、级别、logger 和消息。默认不增加请求正文中间件，因此不会主动记录密码、Token、Cookie 或请求体。

#### 新增 `backend/school_platform/health.py`

- `live(request)`：返回 `JsonResponse({'status': 'ok'})`。
- `ready(request)`：通过 `django.db.connection.cursor()` 执行 `SELECT 1`；成功返回 200，异常返回 `{'status':'unavailable'}` 和 503，并只记录通用告警。
- 仅允许 GET；其他方法返回 405。

#### 新增 `backend/school_platform/errors.py`

定义生产通用 JSON 错误处理器：400、403、404、500。响应只包含稳定的中文错误说明，不包含异常字符串和堆栈。DRF 已处理的业务错误不受影响。

#### 修改 `backend/school_platform/urls.py`

- 注册 `/api/health/live/` 和 `/api/health/ready/`。
- 注册项目级 400/403/404/500 handler。
- 保留 `DEBUG` 下的 media 服务行为。

#### 环境示例与文档

- 新增 `backend/.env.example`，只含占位值。
- 新增 `docs/deployment/stage-1-configuration.md`，记录开发启动、生产变量、健康检查和失败场景验证命令。
- 保持 `.env` 被 Git 忽略，并补充 `.env.*` 忽略规则的例外，确保示例文件可提交、真实变体不提交。

## 4. 测试设计

### 4.1 前端测试

新增 `frontend/src/api/config.test.js`：

1. 空值、空字符串使用 `/api`。
2. 自定义地址去除末尾斜杠。
3. `apiUrl()` 正确处理有/无开头斜杠。
4. 不生成重复斜杠。

修改受影响测试：

- `frontend/src/api/index.test.js`：期望请求改为 `/api/...`。
- 教师 tabs 测试夹具中的 API 改为 `/api`，避免仓库继续保留误导性的本地主机地址。
- 如教师登录已有测试，则验证它调用统一 `login()`；若没有，新增最小测试覆盖提交路径。

验证命令：

```bash
cd frontend
npm test -- --run src/api/config.test.js src/api/index.test.js
npm run build
```

若 Vitest 全量运行仍出现已记录的基线停滞，使用单文件命令验证本阶段测试，并保留超时证据；不得把全量测试写为通过。

### 4.2 后端测试

新增测试包：

- `backend/school_platform/tests/test_environment.py`
- `backend/school_platform/tests/test_health.py`
- `backend/school_platform/tests/test_errors.py`

覆盖：

1. 合法/非法布尔解析。
2. 列表去空白和空项。
3. 非法 `DJANGO_ENV` 被拒绝。
4. 生产缺少密钥、`DEBUG=True`、`ALLOWED_HOSTS=*` 被拒绝。
5. 生产 CORS/CSRF 非 HTTPS 来源被拒绝。
6. live 返回 200 且不查询数据库。
7. ready 数据库正常返回 200。
8. ready 数据库异常返回 503，响应不含原始异常。
9. 通用错误 handler 返回约定状态码和不泄密 JSON。

验证命令：

```bash
cd backend
DJANGO_ENV=test python manage.py test school_platform.tests -v 2
```

生产启动安全验证：

```bash
cd backend
DJANGO_ENV=production \
DJANGO_SECRET_KEY='仅用于本地验证的长随机值' \
DJANGO_ALLOWED_HOSTS='example.test' \
DJANGO_CSRF_TRUSTED_ORIGINS='https://example.test' \
python manage.py check --deploy
```

另运行缺少密钥和通配主机两组失败命令，预期非零退出。

## 5. 手工联调设计

1. 后端以 development 启动在 `127.0.0.1:8080`。
2. 前端不设置 API 环境变量，以 Vite 启动。
3. 用浏览器访问 Vite 地址，在 Network 中确认请求 URL 为 Vite 域名的 `/api/...`。
4. 分别完成一次学生登录和教师登录。
5. 学生端打开题目列表；教师端打开学生管理或题库管理，确认至少各有一个 200 请求。
6. 浏览器访问 `/api/health/live/` 和 `/api/health/ready/`，均应返回 `{"status":"ok"}`。
7. 停止后端后再次操作页面，确认没有请求回落到浏览器自身的 `localhost:8080` 固定地址。

## 6. 实施步骤与状态

### Step 1：统一前端 API 配置

- [x] 新增配置模块及单元测试。
- [x] 修改三个 API 模块。
- [x] 修改教师登录和教师管理页面。
- [x] 配置 Vite 开发代理与前端环境示例。
- [x] 静态搜索确认运行时代码无写死地址。

### Step 2：Django 环境配置

- [x] 新增环境变量解析和生产校验模块。
- [x] 重构 settings 并加入安全、CORS、CSRF 和日志配置。
- [x] 增加后端环境示例及忽略规则。
- [x] 完成配置单元测试和生产失败验证。

### Step 3：健康检查与错误响应

- [x] 新增 live/ready 视图及路由。
- [x] 新增生产通用错误 handler。
- [x] 完成健康检查与错误响应测试。

### Step 4：文档、回归与联调

- [x] 编写阶段 1 配置与启动文档。
- [x] 运行后端阶段测试和 `check --deploy`。
- [x] 运行前端阶段测试、构建和静态搜索。
- [x] 启动前后端完成同源手工联调。
- [x] 更新路线图和本 DEV 状态。
- [x] 按阶段汇报模板交付完成内容与用户验证步骤。

执行说明：Vitest、Vite build 和 ESLint 均复现改造前已记录的启动/转换停滞。依据 PRD 第 3 节和第 9.3 节，已如实记录证据，并使用独立 Node 运行时验证、Babel 语法解析、静态搜索及真实 Vite→Django 代理联调覆盖阶段 1 改动；详细结果见 `docs/reports/2026-09-01-stage-1-completion.md`。

## 7. 完成门槛

只有同时满足以下条件才把阶段 1 标记为完成：

- 运行时代码中的固定 `localhost:8080/api` 为 0。
- 默认浏览器请求使用同源 `/api`，开发代理联调成功。
- 生产环境无法以固定密钥、`DEBUG=True`、通配主机或开放 CORS 启动。
- live/ready 状态码及脱敏行为有测试证据。
- 阶段 1 的前后端测试全部通过。
- `check --deploy` 结果已记录；构建或全量测试若受既有基线阻塞，明确列出而不掩盖。
- 路线图、DEV 勾选状态和用户验证步骤全部更新。

## 8. 回滚方式

本阶段无 migration 和数据写入。若出现回归，可按代码提交回退配置模块、settings、路由及前端地址变更；恢复前端旧地址只用于紧急本地排查，不允许进入生产版本。
