# 阶段 5：学生代码 Runner 隔离 DEV 技术设计

文档日期：2026-09-03
文档状态：用户已确认（2026-09-03）
对应 PRD：`docs/prd/2026-09-03-student-code-runner-isolation-prd.md`
前置条件：阶段 5 PRD 已于 2026-09-03 确认
实施状态：Step 0–3、5–6 已完成；Step 4 按用户决定暂缓（需要 Docker）；Step 7 待 Runner 完成后执行

## 1. 技术目标与不变量

本阶段用持久化任务队列和独立 Runner，替换 Django 中两条直接执行路径：

- `ai_courses.utils.run_code_interactive()` 的本机 Python 子进程。
- `ai_courses.models.grade_submission()` 的逐测试点本机 Python 子进程。

完成后必须满足：

1. Django 请求进程不执行学生代码，也不拥有 Docker socket。
2. Runner 不连接生产数据库，不持有 Django、数据库、AI 或用户凭据。
3. 自由运行每次使用一个新沙箱；自动评测每个测试点使用一个新沙箱。
4. 沙箱非 root、无网络、只读根文件系统，无宿主机目录和密钥挂载。
5. 时间、CPU、内存、进程、临时空间和输出限制由 Runner 强制执行。
6. 排队、领取、续租、完成和重试可恢复且幂等，不依赖单个 Web 进程内存。
7. Runner 不可用时返回服务不可用，不回退到 Django 本机执行。
8. 只有 Web 写入 `Submission` 和成绩；Runner 结果写库前必须再次校验。
9. 现有题目、提交历史、最高分和教师统计口径保持兼容。
10. 普通后端测试不执行真实学生代码；安全验收必须运行真实 Docker 沙箱。

## 2. 当前基线

### 2.1 自由运行

```text
ProblemDetail.jsx
  -> POST /api/ai/run_code/
  -> CodeRunView
  -> run_code_interactive()
  -> tempfile
  -> subprocess.run([sys.executable, student.py], timeout=10)
```

已有登录、每用户 `3/second` 限流、stdin、stdout/stderr 和 10 秒超时；但执行同步占用 Web worker，并继承 Web 主机文件、网络和环境权限，也没有内存、进程、输出和磁盘限制。

### 2.2 自动评测

```text
ProblemDetail.jsx
  -> POST /api/ai/submissions/
  -> SubmissionView
  -> backend/submissions/<student>_<problem>_<time>.py
  -> grade_submission()
  -> 每测试点 subprocess.run(['python', submission_path], timeout=5)
  -> Submission
```

现有实现可按测试点比对输出并保存成绩，但代码会写入共享目录、总执行时间无上限，且课堂并发直接消耗 Web 进程。

## 3. 总体架构

采用“数据库持久化队列 + Runner 主动领取”，首版不引入 Redis、Celery 或额外云服务。

```text
学生浏览器
   │ POST run / submit
   ▼
Django 公共 API ──事务──► ExecutionTask(queued)
   │                         + Submission(pending，仅提交任务)
   │ GET task status               ▲
   ▼                               │ claim / heartbeat / complete
前端轮询                            │ 私有 HMAC 接口
                              Runner Controller
                                      │
                                      ├─ 自由运行：1 个临时容器
                                      └─ 自动评测：每测试点 1 个临时容器
```

该方案使队列随数据库持久化，Runner 无需数据库权限，也不增加 Redis 成本。后续若压测证明数据库队列不足，可以保持任务状态机和前端契约不变，只替换队列传输层。

## 4. 代码结构

### 4.1 Django 新应用

新增 `backend/execution/`：

```text
execution/
├── models.py                 # ExecutionTask、RunnerNode
├── constants.py              # 状态与安全上限
├── serializers.py            # 公共请求/响应
├── services.py               # 入队、状态迁移、结果落库
├── queue.py                  # 公平领取、租约、过期恢复
├── snapshots.py              # 测试点不可变快照
├── internal_auth.py          # Runner HMAC 鉴权
├── views_public.py           # 学生任务查询
├── views_internal.py         # claim/heartbeat/complete
├── urls_public.py
├── urls_internal.py
├── migrations/
└── tests/
```

`ai_courses.views` 保留现有业务入口，但只调用 `execution.services`，不包含执行细节。

### 4.2 独立 Runner

新增 `runner/`：

```text
runner/
├── controller.py             # 并发槽、领取、续租、结果提交
├── web_client.py             # 私有接口客户端及签名
├── sandbox.py                # Docker 隔离、输出和清理
├── grading.py                # 多测试点调度及报告
├── schemas.py                # runner.v1 契约
├── settings.py               # 严格环境变量解析
├── requirements.txt
├── Dockerfile.controller
├── sandbox/
│   ├── Dockerfile
│   └── launcher.py
└── tests/
```

同时增加 `compose.runner.dev.yml`、`.env.runner.example` 和 `scripts/verify_runner_isolation.sh`。Web 不挂载 Docker socket；只有 Runner Controller 可以调用 Runner 主机容器运行时。

## 5. 数据模型

### 5.1 `ExecutionTask`

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `public_id` | `UUIDField(unique=True)` | 对学生暴露的不可猜测 ID |
| `user` | `ForeignKey(CustomUser, PROTECT)` | 所有者 |
| `problem` | `ForeignKey(Problem, SET_NULL, null=True)` | 关联题目 |
| `task_type` | `CharField(run/grade)` | 自由运行/评测 |
| `status` | `CharField(db_index=True)` | 任务状态 |
| `code` / `stdin` | `TextField` | 请求时快照 |
| `test_snapshot` | `JSONField(null=True)` | 隐藏测试点快照 |
| `snapshot_hash` | `CharField` | 快照完整性摘要 |
| `limits` | `JSONField` | 服务端限制快照 |
| `idempotency_key` | `CharField` | 防重复创建 |
| `priority` | `PositiveSmallIntegerField` | 排队优先级 |
| `queued_at` / `started_at` / `finished_at` | `DateTimeField` | 生命周期时间 |
| `expires_at` | `DateTimeField` | 排队有效期 |
| `leased_by` | `CharField` | Runner ID |
| `lease_token_hash` | `CharField` | 一次性租约哈希 |
| `lease_expires_at` | `DateTimeField` | 租约到期 |
| `attempt_count` | `PositiveSmallIntegerField` | 领取次数 |
| `stdout` / `stderr` | `TextField` | 已限制、清理的输出 |
| `result_detail` | `JSONField` | 测试摘要/终止原因 |
| `score` | `FloatField(null=True)` | 评测得分 |
| `execution_ms` / `queue_ms` | `PositiveIntegerField` | 性能数据 |
| `created_at` / `updated_at` | `DateTimeField` | 审计时间 |

约束与索引：

- `UniqueConstraint(user, idempotency_key)`。
- `(status, priority, queued_at)` 用于领取。
- `(user, status, created_at)` 用于每用户上限和恢复。
- `(lease_expires_at, status)` 用于回收。

### 5.2 状态机

```text
queued ──claim──► running ──complete──► succeeded
  │                 │                  ├─ runtime_error
  │                 │                  ├─ wrong_answer
  │                 │                  ├─ timed_out
  │                 │                  ├─ resource_limited
  │                 │                  └─ system_error
  │                 └─lease expired──► queued（最多重试 1 次）
  │                                      └─再次失败► system_error
  └─queue expiry/disable──► cancelled
```

完成状态不可逆。相同租约与结果重复提交只返回现有结果，不再次更新成绩。

### 5.3 `Submission` 调整

- 新增 `execution_task = OneToOneField(ExecutionTask, null=True, on_delete=SET_NULL)`。
- `score` 允许 `NULL`，表示尚未形成成绩；旧记录不变。
- 正式提交先建立 `pending + score=NULL`，领取后为 `running`，完成后更新为最终状态。
- 最高分与平均分查询排除 `score IS NULL`。
- 停止向 `backend/submissions/` 写永久 `.py` 文件，数据库内 `Submission.code` 保持现有行为。

### 5.4 `RunnerNode`

保存 Runner ID、协议版本、沙箱镜像摘要、并发槽位、最后心跳、状态和最近错误摘要，不保存 Runner 密钥。

## 6. 公共 API

### 6.1 创建自由运行任务

保留路径，改为异步：

```http
POST /api/ai/run_code/
Idempotency-Key: <uuid>

{"code":"...","stdin":"..."}
```

成功返回 HTTP 202：

```json
{"task_id":"uuid","status":"queued","poll_after_ms":500}
```

事务内校验身份、代码与 stdin 大小、频率和本人活动任务数；限制值全部由服务端写入，忽略客户端限制参数。

### 6.2 创建评测任务

保留 `POST /api/ai/submissions/`。事务内：

1. 校验身份、题目和代码。
2. 读取并规范化测试点为不可变 JSON 快照。
3. 创建 `Submission(pending, score=NULL)`。
4. 创建绑定的 `ExecutionTask(type=grade)`。
5. 返回 HTTP 202、任务 ID和提交 ID。

失败时不得留下半条提交或半个任务。

### 6.3 查询和恢复

新增：

```http
GET /api/ai/executions/<task_id>/
GET /api/ai/executions/active/?problem_id=<id>&task_type=<run|grade>
```

- 查询始终附加 `user=request.user`。
- 排队/运行中返回状态和建议轮询间隔。
- 完成后返回有限输出、耗时；评测额外返回提交 ID、得分和报告。
- 不返回代码、隐藏测试、租约、Runner 内部信息或其他学生数据。

## 7. 私有 Runner 协议

```text
POST /internal/runner/v1/tasks/claim
POST /internal/runner/v1/tasks/<id>/heartbeat
POST /internal/runner/v1/tasks/<id>/complete
POST /internal/runner/v1/nodes/heartbeat
```

公网 Nginx 必须拒绝这些路径；生产环境仅允许 Runner 安全组访问内部入口。

### 7.1 鉴权

请求包含 Runner ID、时间戳、请求 UUID 和 HMAC-SHA256 签名。签名覆盖方法、路径、时间戳、请求 ID和 body 哈希。

- 时间偏差超过 60 秒拒绝。
- `claim` 请求 ID 与租约绑定，重放不能领取第二个任务。
- `heartbeat/complete` 还需提供明文 lease token，数据库只存其哈希。
- 完成后租约失效，迟到结果不能覆盖数据。
- 使用独立 `RUNNER_SERVICE_SECRET`，不复用用户 Token 或 Django Secret。

### 7.2 公平领取

`claim` 在事务中：

1. 处理已过排队有效期的任务。
2. 排除已经有 `running` 任务的用户。
3. 按 `priority, queued_at, id` 选择最早任务。
4. MySQL 使用 `select_for_update(skip_locked=True)`；SQLite 使用事务与状态条件回退。
5. 设置 Runner、随机租约、租约到期、开始时间和领取次数。

默认每学生最多 1 个运行任务、2 个排队任务，因此单个学生不能占满全部执行槽。

### 7.3 租约恢复

- 初始租约 30 秒，执行期间每 5 秒续租。
- `recover_execution_tasks` 管理命令回收过期租约。
- 第一次失联重新排队，第二次标记 `system_error`。
- Runner 重启先清理自己的遗留容器，再领取新任务。

### 7.4 结果落库

`complete` 校验任务、Runner、租约、协议版本、结果状态、JSON 大小、输出长度、测试点数量、得分和耗时。通过后在同一事务更新 `ExecutionTask` 与 `Submission`，数据库提交成功才向 Runner确认。

## 8. Runner 与沙箱

### 8.1 Controller 生命周期

1. 启动时校验服务密钥、内部地址、镜像摘要、并发数和限制。
2. 检查 Docker 和沙箱能力。
3. 清理本 Runner 的遗留任务容器。
4. 按空闲槽位领取，每槽一次处理一个任务。
5. 执行期间发送租约心跳。
6. 提交结构化结果并等待确认。
7. 退出时停止领取、限时等待并清理。

Runner 对 Web 下发限制再取一次本地安全上限，Web 配置错误也不能放宽沙箱。

### 8.2 自动评测

- 每个测试点新建容器，避免文件、模块缓存和后台进程跨测试点污染。
- 当前容器只获得当前测试输入，不获得完整测试集。
- 每项结束立即删除容器，同时受单测试点 5 秒和整任务 30 秒限制。
- 比对规则保持 `stdout.strip() == expected_output`。
- Runner 返回结构化结果，Web 生成中文报告，避免信任任意报告文本。

### 8.3 镜像

- 固定 Python 3.13 slim 版本与 digest，不使用 `latest`。
- 固定非 root UID/GID 10001。
- 不安装编译器、SSH、curl、数据库客户端或无关工具。
- 不将 Controller 代码和任何服务密钥放入沙箱镜像。

### 8.4 Docker 强制参数

Controller 使用 Docker Engine API，至少设置：

```text
user=10001:10001
network_disabled=true
read_only=true
cap_drop=ALL
security_opt=no-new-privileges:true
mem_limit=128m
memswap_limit=128m
nano_cpus=1000000000
pids_limit=16
tmpfs=/work:rw,nosuid,nodev,noexec,size=16m
```

禁止 privileged、host network/PID/IPC、宿主机目录、设备和 Docker socket 挂载。学生代码通过 Docker archive/stdin 放入 `/work`，绝不拼接到 shell 命令。

### 8.5 输出和清理

- 流式读取 stdout/stderr，只保留上限内字节。
- 达到上限标记截断；持续输出则停止任务。
- 超时必须 stop/kill 全容器并最终强制 remove。
- 容器退出后仍按任务标签确认无残留。
- 清理失败时暂停对应执行槽并产生高优先级日志。

## 9. 前端改造

### 9.1 API 层

修改 `frontend/src/api/index.js`：

- `runCode()` 和 `submitCode()` 返回 task ID。
- 新增 `getExecutionTask()` 和支持 `AbortSignal` 的有限轮询。
- 创建请求生成并复用 `Idempotency-Key`。
- 轮询从 500ms 开始，最高增加到 2 秒；页面卸载时停止。

### 9.2 `ProblemDetail.jsx`

```text
idle -> queueing -> queued -> running -> completed/error
```

- 排队显示“排队中…”，执行显示“运行中…”或“评测中…”。
- “运行”和“提交”各只允许一个活动任务。
- 编辑器可继续编辑，但结果属于创建任务时的代码快照。
- 系统错误不显示为 0 分；资源超限按时间、内存、进程和输出分别提示。
- 轮询有限重试，页面刷新后通过 active 接口恢复。
- 旧任务迟到结果不得覆盖更新任务的页面状态。

## 10. 配置

### 10.1 Web

```text
CODE_EXECUTION_ENABLED=true
RUNNER_SERVICE_SECRET=<独立随机密钥>
RUNNER_PROTOCOL_VERSION=runner.v1
EXECUTION_CODE_MAX_BYTES=65536
EXECUTION_STDIN_MAX_BYTES=65536
EXECUTION_USER_RUNNING_LIMIT=1
EXECUTION_USER_QUEUED_LIMIT=2
EXECUTION_QUEUE_TTL_SECONDS=120
EXECUTION_LEASE_SECONDS=30
EXECUTION_MAX_ATTEMPTS=2
```

`CODE_EXECUTION_ENABLED=false` 时返回 503；不提供 `local/subprocess` 执行模式。生产缺少密钥或使用示例值时拒绝启用代码执行。

### 10.2 Runner

```text
RUNNER_ID=<实例唯一名称>
RUNNER_WEB_INTERNAL_URL=<仅内网地址>
RUNNER_SERVICE_SECRET=<与Web对应>
RUNNER_CONCURRENCY=2
RUNNER_SANDBOX_IMAGE=<固定镜像及digest>
RUNNER_HEARTBEAT_SECONDS=5
RUNNER_MAX_CPU=1
RUNNER_MAX_MEMORY_MB=128
RUNNER_MAX_PIDS=16
RUNNER_MAX_TMP_MB=16
RUNNER_MAX_OUTPUT_BYTES=131072
```

Controller 环境变量不传入学生沙箱，日志不打印密钥或完整任务信封。

## 11. 网络边界

```text
公网 -> Nginx/Web ECS -> RDS
                   ▲
                   │ 私网 internal API，仅 Runner 安全组
             Runner ECS
                   └─ 学生沙箱无网络
```

- Runner ECS 不具备 RDS 出站权限，RDS 白名单不包含 Runner。
- 公网 Nginx 拒绝 `/internal/runner/`。
- Runner 管理端口不开放公网。
- 本阶段在本地 Compose 验证；阿里云安全组在阶段 10 实施。

## 12. 测试策略

### 12.1 Django 测试

- run/grade 入队参数、权限、大小、幂等和每用户上限。
- 测试快照不随题目修改变化。
- 学生只能查询自己的任务，响应不含隐藏测试和租约。
- 状态机、HMAC、迟到结果、伪造 Runner 和异常结果。
- claim 公平性、锁、租约、回收和最大重试。
- 任务完成与 Submission 更新的事务一致性。
- Runner 关闭时返回 503，且绝不调用本机执行。

普通测试使用 fixture，不依赖 Docker。

### 12.2 Runner 测试

- 签名、时间窗口、schema 与 Web 故障重试。
- 任务不能放宽 Controller 安全上限。
- UTF-8 输出安全截断，所有退出路径均清理容器。
- 自动评测每测试点独立沙箱并受总预算限制。

### 12.3 真实安全测试

执行 `./scripts/verify_runner_isolation.sh`，覆盖：无限循环、内存耗尽、进程/线程炸弹、持续输出、后台子进程、网络/DNS/RDS 访问、宿主机与密钥读取、路径/符号链接逃逸、任务间文件残留、超大/伪造结果。

每项结束必须确认无任务容器和学生进程残留。安全测试不得用 mock 替代。

### 12.4 前端与并发

- 测试 202、queued/running/final 状态、各种资源错误和服务不可用。
- 测试重复点击、网络重试、卸载停止轮询、刷新恢复及迟到结果。
- 模拟 30 名学生集中创建任务，记录吞吐、P50/P95 等待、拒绝数和 Web 响应时间。
- SQLite 完成功能测试；MySQL 8.0 验证 migration、claim 锁和并发。
- 最终运行后端、Vitest、ESLint 和 Vite build 全量验证。

## 13. 实施步骤

### Step 0：基线与备份（已完成，2026-09-03）

- 记录现有测试基线并备份 SQLite/MySQL 演练数据。
- 增加配置开关；关闭时只返回 503。
- 建立“禁止本机回退”测试和旧执行路径扫描基线。

### Step 1：任务模型（已完成，2026-09-03）

- 新建 `execution` app、模型、约束、索引和 migration。
- 调整 Submission nullable score 与任务关联。
- 验证旧记录在 SQLite/MySQL 无损。

### Step 2：公共入队 API（已完成，2026-09-03）

- 实现快照、幂等、限流、run/grade 202 响应。
- 新增任务查询和活动任务恢复。
- 完成权限、泄露和事务测试。

### Step 3：私有协议和队列（已完成，2026-09-03）

- 实现 HMAC、claim、续租、完成、Runner 心跳和过期恢复。
- 实现公平领取、结果校验和 Submission 原子更新。
- 完成 MySQL 并发领取与重复结果测试。

### Step 4：Runner 沙箱（暂缓）

- 实现 Controller、Docker 沙箱和逐测试点评测。
- 落实全部限制、流式输出、强制终止和清理。
- 通过 Runner 单元测试与真实恶意代码测试。

### Step 5：前端异步体验（已完成，2026-09-04）

- 改造 API、轮询、恢复、任务状态和错误提示。
- 防止重复请求与旧任务覆盖。
- 更新相关 Vitest。

### Step 6：切断旧执行（已完成，2026-09-04）

- 删除 `run_code_interactive()` 和 `grade_submission()` 的本机执行。
- 删除 Web 写共享 `submissions/*.py` 的逻辑。
- 静态扫描 Django 业务代码中的学生代码执行路径归零。
- 历史 `.py` 仅核对和列清单，不在本阶段未经确认删除。

### Step 7：全量验收（未开始，依赖 Step 4）

- SQLite、MySQL、前后端全量测试、Lint 和生产构建。
- 30 学生并发测试及真实安全测试报告。
- 更新启动、排障、密钥轮换、手工验收和路线图文档。

每个 Step 完成并记录证据后再进入下一步。

## 14. 关键文件改动预估

| 范围 | 文件 | 改动 |
| --- | --- | --- |
| 配置 | `backend/school_platform/settings.py`、`urls.py` | 注册 execution、内部路由和配置 |
| 任务 | `backend/execution/*` | 模型、队列、鉴权、接口、测试 |
| AI 业务 | `backend/ai_courses/views.py`、`models.py` | 入队、Submission 关联、移除直接执行 |
| Runner | `runner/*` | Controller、Docker 沙箱、评测和测试 |
| 编排 | `compose.runner.dev.yml`、`.env.runner.example` | 本地隔离联调 |
| 前端 | `frontend/src/api/index.js`、`ProblemDetail.jsx` 及测试 | 异步状态和轮询 |
| 验收 | `scripts/verify_runner_isolation.sh`、并发脚本 | 安全与负载测试 |
| 文档 | `docs/deployment/*`、`docs/reports/*`、路线图 | 操作步骤与证据 |

## 15. 回滚与故障处理

- 开发未完成时可设置 `CODE_EXECUTION_ENABLED=false`，不能恢复本机执行。
- migration 前生成带 manifest 的备份；回滚任务表不得级联删除旧 Submission。
- nullable score 回滚前必须处理 pending 记录并确认无 NULL。
- Runner 故障只关闭新代码任务，课程、小测和历史成绩继续服务。
- 队列满时明确拒绝，不提高资源限制或允许无界队列。
- 清理失败时暂停对应槽位并告警，人工确认后恢复。
- Runner 密钥泄露时轮换密钥、使租约失效并审计异常请求。

## 16. DEV 确认项

确认本 DEV 即表示同意：

1. 使用现有数据库作持久化队列，首版不引入 Redis/Celery。
2. Runner 主动从 Django 私有接口领取任务，但不拥有数据库权限。
3. 自由运行一个沙箱；自动评测每测试点一个独立沙箱。
4. 公共接口改为 HTTP 202 + 前端轮询，同时保持页面入口和最终成绩体验。
5. Runner 失败只关闭代码执行，不回退到 Web 本机运行。
6. 默认限制采用 PRD 基线，只能由服务端在安全上限内调整。
7. 历史 `submissions/*.py` 先核对和列清单，不未经确认直接删除。

用户确认 DEV 后，从 Step 0 开始实施。
