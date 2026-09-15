# 跨平台本机 Runner 过渡方案 DEV 技术设计

日期：2026-09-15
状态：用户已确认（2026-09-15）；Step 0–6 已完成，等待进入 Step 7
对应 PRD：`docs/prd/2026-09-15-cross-platform-local-runner-prd.md`

## 1. 实施边界

本阶段在不恢复 Django 同步执行、不接入 Docker 的前提下，实现独立的跨平台本机 Runner。公共运行/提交 API、`ExecutionTask`、Runner HMAC 私有协议、Submission 回写和前端异步轮询保持不变。

实现顺序严格遵循：先在 `MacBook` 分支完成代码与自动测试，再做当前 macOS 本机端到端验证；形成独立提交后迁移到 `jifang3`，最后在真实 Windows 机房电脑执行专项验收。

## 2. 总体架构

```text
React 学生端
  │ POST run / submit
  ▼
Django Web
  │ transaction: ExecutionTask + Submission
  ▼
数据库持久队列
  ▲                         独立进程
  │ HMAC claim/heartbeat       │
  └──────────────────── Local Runner Controller
                                │ fixed worker slots
                                ▼
                         LocalProcessExecutor
                                │
                                ▼
                    临时目录中的独立 Python 子进程
```

### 2.1 保持不变

- 学生公共 API 路径与 HTTP 202 合同。
- 任务状态机、每学生队列上限、公平领取和租约。
- 服务端冻结测试快照与隐藏测试保护。
- `complete_task()` 的结果复核、Submission 原子更新和小测结算钩子。
- 前端排队/运行/终态展示、有限轮询、刷新恢复和幂等键。

### 2.2 新增

- `runner` 独立 Python 包。
- 跨平台受控子进程执行器和自动评测器。
- Runner 本地配置初始化工具。
- Runner 可用性门控。
- macOS/Linux 与 Windows 启停集成。
- Runner 单元、协议集成、端到端和并发验收。

## 3. 模块设计

### 3.1 配置 `runner/config.py`

使用不可变配置对象读取环境变量并在进程启动时一次性校验：

```text
RUNNER_ID=local-runner-01
RUNNER_WEB_INTERNAL_URL=http://127.0.0.1:8080
RUNNER_SERVICE_SECRET=<至少 32 位>
RUNNER_PROTOCOL_VERSION=runner.v1
RUNNER_CONCURRENCY=2
RUNNER_HEARTBEAT_SECONDS=5
RUNNER_CLAIM_IDLE_SECONDS=0.5
RUNNER_HTTP_TIMEOUT_SECONDS=5
RUNNER_PYTHON_EXECUTABLE=<默认 sys.executable>
RUNNER_MAX_MEMORY_MB=128
RUNNER_MAX_PIDS=16
RUNNER_MAX_OUTPUT_BYTES=131072
RUNNER_MAX_CASE_SECONDS=5
RUNNER_MAX_TASK_SECONDS=30
RUNNER_SHUTDOWN_GRACE_SECONDS=10
```

规则：

- Web 下发限制与 Runner 本地上限取更严格值，任务不能放宽 Runner 限制。
- URL 只接受 `http://127.0.0.1`、`http://localhost` 或显式允许的内网地址；本阶段默认回环地址。
- Runner 标识长度和协议版本与现有服务端 serializer 对齐。
- 真实配置保存在项目根目录 `.env.runner.local` 并由 Git 忽略。
- `backend/settings.py` 在已有环境文件之后补读 `.env.runner.local`，仅补齐未设置变量，不覆盖 shell 或后端显式配置。

### 3.2 HMAC 客户端 `runner/api_client.py`

请求序列化必须与服务端签名完全一致：

```text
body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
signature = HMAC-SHA256(method + path + timestamp + request_id + SHA256(body))
```

提供四个领域方法：

- `node_heartbeat(active_slots, status, last_error)`
- `claim_task()`
- `task_heartbeat(task_id, lease_token)`
- `complete_task(task_id, lease_token, result)`

网络策略：

- 每次请求使用唯一 UUID。
- 心跳和 complete 遇到连接中断时，使用相同请求 ID、相同 body 有限重试，利用现有 receipt 幂等返回。
- claim 是不可重放操作；响应不确定时不使用新请求立即反复领取，等待租约恢复，避免一个槽位失去明文 lease 后继续堆积任务。
- 4xx 协议/签名错误立即失败并记录安全摘要；5xx/连接失败指数退避。
- 日志不得打印 Header、secret、完整 envelope、代码和测试快照。

### 3.3 Controller `runner/controller.py`

- 一个主协调线程维护节点心跳、停止状态和活动任务集合。
- `RUNNER_CONCURRENCY` 个固定 worker 线程；每个 worker 一次只持有一个任务。
- 空闲 worker 通过现有公平 claim 接口领取任务；空队列按配置退避。
- worker 执行期间启动租约心跳循环，间隔小于服务端 lease 的一半。
- 执行结束后先停止任务心跳，再回传结构化结果；只有 Web 确认后释放槽位。
- 收到 `SIGINT`/`SIGTERM` 或 Windows 控制台中断后，节点切换 `draining`，停止领取，按 grace period 收尾并清理活动子进程。
- Controller 不导入 Django、不连接数据库、不持有用户 Token。

### 3.4 本机执行器 `runner/local_executor.py`

每次执行：

1. 使用 `tempfile.TemporaryDirectory()` 创建任务目录。
2. 以 UTF-8 写入随机文件名的 `main.py`。
3. 使用绝对解释器路径和参数 `-I -B` 启动学生程序。
4. `cwd` 指向任务临时目录；传入最小化环境，剔除数据库、AI、Runner 和 Django 密钥。
5. 用二进制管道传递 stdin 并并发读取 stdout/stderr。
6. 读取缓冲区有硬上限，达到上限立即结束任务，不能先无限缓存再截断。
7. 监控墙钟时间、进程树数量与进程树总常驻内存。
8. 结束或异常时终止完整进程树并等待退出。
9. 离开上下文时删除任务目录。

使用 `psutil` 提供 macOS/Windows 一致的子进程树、RSS 和进程数量观察；加入 `requirements.txt` 并固定兼容范围。它属于过渡可用性护栏，不声明为内核级安全限制。

#### Unix/macOS

- `start_new_session=True` 创建独立进程组。
- 清理时先通过 psutil 终止后代，再对进程组发送终止/强杀信号。

#### Windows

- 使用 `CREATE_NEW_PROCESS_GROUP` 启动。
- 使用 psutil 递归获取后代，按子到父顺序 terminate/kill。
- 必要时使用系统 `taskkill /PID <pid> /T /F` 作为清理兜底，参数以列表传递，不通过 shell 拼接。

#### 最小环境

保留 Python 正常启动所需的平台变量，例如 `SystemRoot`、`WINDIR`、临时目录和 UTF-8 设置；明确删除名称匹配以下类别的变量：

```text
*SECRET*、*TOKEN*、*PASSWORD*、*API_KEY*、DJANGO_*、RUNNER_*、DATABASE_*、MYSQL_*
```

### 3.5 结果模型 `runner/results.py`

执行器内部返回统一对象：

```text
status
stdout
stderr
execution_ms
termination_reason
output_truncated
```

映射规则：

- 退出码 0：`succeeded`
- 非零退出码：`runtime_error`
- 墙钟超限：`timed_out`
- 内存、进程或输出超限：`resource_limited`
- Runner 自身异常：`system_error`

所有文本使用 UTF-8 `errors="replace"` 解码，保证任意字节输出均可安全形成 JSON。

### 3.6 自动评测 `runner/grader.py`

- 仅使用 claim envelope 中的服务端冻结 `test_snapshot`。
- 每个测试点创建全新的临时目录和 Python 子进程，测试之间不共享文件和模块缓存。
- 比对规则保持现有设计：`stdout.strip() == expected_output`。
- 每个测试点受 `case_wall_seconds` 限制，全部测试受 `task_wall_seconds` 总预算限制。
- stdout/stderr 使用整个任务共享的输出预算，避免测试点数量放大回传 JSON。
- 逐项形成 `{number, status, actual_output, stderr, execution_ms}`。
- 全部通过返回 `succeeded, score=100`；否则按通过数量计算分数，并根据超时、资源超限、运行错误、答案错误的优先级确定任务终态。
- Runner 不回传可信标准答案；标准答案仍由 Web 从自身快照填充。

### 3.7 Runner 可用性门控

新增 Web 配置：

```text
EXECUTION_REQUIRE_HEALTHY_RUNNER=true
```

创建运行/评测任务前检查是否存在 `online` 且心跳未过期的 Runner：

- 有在线 Runner：允许入队；即使槽位已满也允许正常排队。
- 无在线 Runner：返回 HTTP 503 和稳定错误码 `runner_unavailable`，不创建 Task/Submission。
- `test` 环境默认关闭该门控，现有纯 API 测试不被运行时依赖污染；端到端测试显式开启。
- development/production 的本地 Runner 配置显式开启。

该门控解决“明知没有执行者仍不断创建 queued 任务”的问题。已经入队后 Runner 异常的任务仍由现有租约和 `recover_expired_tasks()` 恢复；存活 Runner 的持续 claim 会周期性触发恢复。

## 4. 配置与启停

### 4.1 初始化工具

新增 `scripts/init_local_runner.py`：

- 首次运行生成至少 32 字节随机 secret。
- 创建 `.env.runner.local`，已存在时不覆盖。
- 支持 `--check` 只读检查。
- 不显示 secret，只报告配置文件路径和有效性。
- 使用纯 Python，macOS 和 Windows 共用。

`.env.runner.example` 提供不含真实密钥的完整模板。

### 4.2 macOS/Linux 脚本

`start_all.sh`：

1. 选择项目 Python。
2. 初始化或检查本机 Runner 配置。
3. 清理 PID 文件记录的旧 Django、Vite、Runner。
4. 启动 Django。
5. 启动 Runner，日志写入 `logs/runner.log`。
6. 启动 Vite。
7. 检查 Web、前端和 Runner 心跳状态。
8. PID 文件保存三个服务 PID。

`stop_all.sh`：先停止 Runner 领取，再停止 Django/Vite；最后只清理本项目明确匹配的遗留进程。

### 4.3 Windows 脚本

重写当前乱码批处理为 UTF-8/可读中文，并保持现有 Python 选择顺序：

1. 项目 `.venv`。
2. 机房已知 Conda 环境。
3. 系统 `python`。

`start_all.bat` 调用同一个初始化脚本，分别启动 Django、Runner 和 Vite并写日志。`stop_all.bat` 使用 PowerShell/CIM 精确匹配本项目命令行并递归停止进程树，不能误杀其他 Python/Node 程序。

## 5. 数据与 Migration

- 不新增数据库表。
- 不修改已有 `ExecutionTask`、`RunnerNode`、receipt 或 Submission schema。
- 不需要 Django migration。
- 调整配置默认值和示例文件，不修改真实 `.env`。
- 当前数据库里的历史过期 queued 任务在本机 Runner 首次 claim 时由现有恢复逻辑取消。

## 6. 实施步骤

### Step 0：基线与文档（✅ 已完成，2026-09-15）

- 保存当前 Git 状态、分支共同基线和已有测试结果。
- 把 PRD 状态更新为已确认。
- 确认 Python、Django、前端和当前 SQLite 数据不被重置。

验证：`git diff --check`、Django system check、execution/AI 编程相关现有测试。

完成记录：

- 开发分支为 `MacBook`，HEAD 为 `12bb081`；`origin/jifang3` 为 `df140c5`，两者共同基线为 `12bb081`。
- 实施前工作区没有用户遗留修改；仅新增本功能 PRD/DEV 文档。
- `DJANGO_ENV=test DJANGO_DB_ENGINE=sqlite python manage.py check`：0 问题。
- Django 定向基线：`execution.tests`、普通 AI 编程、AI 小测编程执行与结算共 83 项通过、3 项按设计跳过、0 失败。
- 前端定向基线：API 异步轮询、`ProblemDetail`、`ProgrammingWorkspace` 共 45 项通过、0 失败。
- `git diff --check`：通过。

### Step 1：Runner 配置、HMAC 客户端与协议测试（✅ 已完成，2026-09-15）

- 新建 Runner 包、配置加载、签名和 API client。
- 新增共享本地配置初始化工具和示例。
- 使用伪 HTTP 服务及现有 Django internal API 验证签名、Unicode body、重试、防重放和错误处理。

验证：Runner 配置/客户端单元测试、`execution.tests.test_internal_api`。

完成记录：

- 新增独立 `runner` 包的不可变配置、runner.v1 HMAC 签名和四个私有 API 客户端方法。
- 配置校验覆盖本地/显式远程地址、密钥、协议、Python 解释器、并发和资源上下限。
- retryable 请求复用同一 request ID/body；claim 遇到不确定网络失败不盲目重试。
- 新增跨平台 `scripts/init_local_runner.py`，首次生成 `.env.runner.local`，已有配置不覆盖且不打印密钥。
- Django 以不覆盖显式环境的方式补读共享本地 Runner 配置；新增 `.env.runner.example`。
- Runner 配置、API client、初始化工具共 11 项单元测试通过。
- Django `execution.tests.test_internal_api` 17 项通过，确认服务端签名、防重放、租约与回写合同无回归。
- Python compileall、Django system check、`git diff --check` 均通过。

### Step 2：跨平台本机执行器（✅ 已完成，2026-09-15）

- 实现有限输出读取、超时、资源观察、最小环境和进程树清理。
- 实现 macOS 与 Windows adapter。
- 新增正常、stdin、语法错误、运行错误、死循环、持续输出、内存与子进程测试。

验证：Runner executor 单元测试；测试结束确认无遗留进程和临时目录。

完成记录：

- 新增 `LocalProcessExecutor`：独立 UTF-8 临时源码、绝对 Python 路径、`-I -B`、独立 cwd 和最小环境。
- stdout/stderr 使用共享硬上限的并发 byte reader；刚好达到上限允许，超过一个字节也稳定转为 `resource_limited`，不使用无界 `communicate()`。
- stdin 使用独立 writer，避免学生程序先输出后读取输入时管道互锁。
- 使用墙钟、进程树 RSS、进程树数量和本地硬上限监控；Web 下发值只能收紧，不能放宽 Runner 上限。
- macOS/Unix 使用新进程组和 TERM/KILL 清理；Windows 使用新进程组、psutil 递归清理及参数化 `taskkill /T /F` 兜底。
- 正常退出后仍清理后台后代；任务结束删除临时目录。
- 子进程环境剔除 Django、Runner、数据库、Token、密码和 API Key 类变量。
- `requirements.txt` 新增 `psutil>=6.1,<8`；当前 Mac 环境安装并验证 psutil 7.2.2。
- 执行器测试覆盖 stdin/stdout/stderr、运行错误、非 UTF-8、死循环、快速/持续超大输出、精确输出边界、内存、进程数、后台子进程、环境脱敏和双平台启动参数。
- Step 2 执行器测试连续 3 轮通过；当前 Runner 全部 24 项测试通过。
- Django相关83项基线测试继续通过（3项按设计跳过）；compileall、system check、`git diff --check` 通过。
- Windows真实进程树效果按计划保留到 Step 8 机房设备验收，macOS结果不代替Windows结论。

### Step 3：自动评测与 Controller 生命周期（✅ 已完成，2026-09-15）

- 实现 run/grade 结果生成。
- 实现固定 worker、节点心跳、任务续租、领取、完成和优雅退出。
- 验证每测试点独立执行、总时间/输出预算和 Web 回写合同。

验证：Runner grader/controller 测试、真实 Django internal API 集成测试。

完成记录：

- 新增 `TaskEvaluator`，统一生成现有 runner.v1 接受的 run/grade 结构化结果。
- 自动评测只使用任务 envelope 的冻结测试快照；每个测试点由执行器创建全新临时目录和子进程。
- 保持 `stdout.strip() == expected_output` 规则；结果不回传标准答案，由 Web 使用自身快照补齐。
- 实现单测试点/整任务双重时间预算、整个任务共享输出预算、通过比例计分和终态严重级映射。
- `system_error` 保持 `score=None`；资源、超时、运行错误和答案错误形成服务端允许的逐测试点状态。
- 新增固定 worker 数的 `LocalRunnerController`、首次注册、周期节点心跳、任务领取、执行期间租约心跳、幂等完成回写、draining 和限时停止。
- 节点/任务日志只包含 Runner ID、任务 ID、类型、状态和安全错误码，不打印代码、租约、密钥或隐藏测试。
- 新增 `python -m runner` 入口；缺失有效密钥时以退出码 2 安全拒绝启动。
- Grader/Controller 覆盖全对、部分错、异常、超时、测试隔离、共享输出预算、固定并发2槽、续租和无效信封。
- Runner 全部 35 项测试通过。
- 新增真实 Django 协议集成测试2项：完整注册/claim/续租/complete，以及真实执行两测试点并回写 Task、Submission 100分。
- execution、普通 AI 编程、混合小测执行与结算定向回归共 85 项通过、3项按设计跳过、0失败。
- 结束后未发现本机 Runner 学生进程或临时目录残留；compileall、system check、`git diff --check` 通过。

### Step 4：Web 可用性门控与故障恢复（✅ 已完成，2026-09-15）

- 新增健康 Runner 配置与入队前检查。
- 增加无 Runner 503、有 Runner 202、满槽仍排队、过期恢复测试。
- 确认系统错误不生成假 0 分，混合小测结算保持幂等。

验证：execution、普通 AI 练习、AI 混合小测定向测试。

完成记录：

- 新增 `EXECUTION_REQUIRE_HEALTHY_RUNNER`；默认不影响没有 Local Runner 的现有安装，`.env.runner.local` 和部署配置示例显式开启。
- 四个入队入口（普通 run/grade、小测 run/grade）在创建新记录前统一检查 `RunnerNode`。
- 仅当存在 `online` 且心跳时间在 `RUNNER_NODE_STALE_SECONDS` 内的节点时允许新任务入队。
- 无健康 Runner 时返回 HTTP 503 / `runner_unavailable`，且不创建 Task 或 Submission；心跳过期和 offline 均视为不可用。
- 节点 `active_slots == capacity` 仍允许入队，因为满载是正常排队状态，不是服务中断。
- 幂等重试先查找已有任务；即使 Runner 在重试时暂时离线，也不会把已创建请求误报成新的 503。
- 既有过期恢复用例确认：首次租约过期重排，达到重试上限转 `system_error`，Submission 保持 `score=None`，不产生假 0 分。
- Runner 35 项单元测试通过；execution、普通 AI 编程、混合小测执行与结算共 90 项通过、3 项按设计跳过、0 失败。
- Django system check 和 `git diff --check` 通过。

### Step 5：macOS/Windows 启停与运维文档（✅ 已完成，2026-09-15）

- 集成 shell/batch 启停脚本和 PID/日志。
- 修复 Windows 批处理乱码。
- 更新 README，增加安全边界、配置、排障和回退说明。
- 增加 Runner 状态检查命令。

验证：当前 Mac 一键启动/停止两轮；脚本静态检查；Windows 命令路径测试。

完成记录：

- 重写 `start_all.sh` / `stop_all.sh`：按 Django → Runner 心跳验收 → Vite 顺序启动，保存三个独立 PID，失败时自动回收已启动进程。
- macOS/Linux 停止时先向 Runner 发送 TERM，等待优雅退出，再停 Django/Vite；只操作 `.server_pids` 记录且命令行含本项目绝对路径的进程树，不强杀未知端口占用者或 PID 复用后的其他进程。
- 原 Windows 批处理从 GB18030 解码并重写为 UTF-8 / code page 65001，修复中文乱码。
- Windows 保留 `.venv` → `E:\\Anaconda\\envs\\pylearn` → `PATH python` 选择顺序，用 PowerShell `Start-Process -PassThru` 取得真实 PID，用 `taskkill /T` 回收明确进程树。
- 新增 `runner_status` Django 命令，显示节点健康、槽位与心跳年龄；无健康节点时返回非零退出码，启动脚本支持最多等待 20 秒。
- 测试环境不加载机器本地 `.env.runner.local`，避免本机心跳状态污染可重复的 Django 测试。
- 更新 `README.md`，新增 `docs/deployment/local-runner-classroom.md`，记录首次安装、配置、安全边界、Windows 机房迁移、心跳检查、排障与回退。
- 当前 Mac 完成两轮真实一键启停；每轮均确认三进程存活、Django/Vite HTTP 可达、Runner 心跳健康，停止后 8080/5173 释放、PID 文件删除、Runner 记录为 draining。
- Runner 测试增至 37 项，含 shell 语法、Windows UTF-8/路径/PID 进程树静态验证；`runner_status` 3 项命令测试通过。execution、普通 AI 编程、混合小测执行与结算回归共 93 项通过、3 项按设计跳过、0 失败。
- Windows 真实进程和中文控制台效果仍按计划留到 Step 8 在机房设备验收。

### Step 6：MacBook 端到端与并发验收（✅ 已完成，2026-09-15）

- 学生页面执行普通 run 和正式 grade。
- 执行 AI 混合小测编程题并验证结算。
- 覆盖刷新恢复、Runner 停止/重启、Django短暂重启和任务过期。
- 运行 40 个模拟学生集中创建任务的受控压测，确认固定并发槽和全部终态。
- SQLite 只记录功能与小规模结果；具备 MySQL 环境时补做并发 claim 验证。

验证：记录任务状态、P50/P95 排队时间、总耗时、拒绝数、重复数和残留进程数。

完成记录：

- 真实浏览器登录学生端后发现 Monaco 本地初始化存在异步竞态；改为启动应用前等待本地 Monaco 和 Worker 配置完成，断网机房不再回退到公共 CDN。浏览器复验编辑器可输入，普通运行输出正确。
- 普通正式评测提交后在“评测中”阶段立即刷新，页面重新加载后自动续接活动任务并显示新产生的 100 分记录；浏览器无应用错误和异常覆盖层。
- 使用临时八年级题库、小节、选择题、编程题和学生完成真实混合小测：选择题 40 分、编程题 60 分，Runner 实际评测 100 分，最终结算总分 100 分、评测异常数 0；验收数据和临时测试文件均已清理。
- 40 个临时学生通过真实 HTTP 接口同时提交，每份程序先等待 0.4 秒以形成稳定排队：40/40 HTTP 202、40/40 进入终态且均为 `succeeded`、40/40 得 100 分，重复任务 0、拒绝 0、最大尝试次数 1、Runner 峰值活动槽 2/2、残留子进程 0。
- 本轮 SQLite 数据：排队 P50 4021 ms、P95 7836 ms、全批总耗时 9371 ms。该结果证明当前 Mac 演示与受控 40 人突发可完成，不替代机房 MySQL 和真实硬件容量验证。
- 运行中强制中断已校验命令行的本项目 Runner，并短暂重启 Django/Vite/Runner；租约过期后任务自动重排，第 2 次执行成功并输出 `RECOVERED`。另创建一条已过期排队任务，Runner 将其稳定取消为 `queue_expired`，两项均无残留子进程。
- 新增可重复执行的 `scripts/benchmark_local_runner.py`、`scripts/acceptance_mixed_quiz.py` 和 `scripts/acceptance_runner_recovery.py`，临时账号与数据按精确主键清理。
- Runner 37 项测试全部通过；Django 518 项全部通过、5 项按设计跳过；前端 302 项通过、2 项跳过，生产构建成功。ESLint 为 0 error、33 条既有 React 警告；Django system check、shell 语法与 `git diff --check` 通过。
- 当前环境未配置 MySQL；MySQL/InnoDB 并发测试按设计跳过，并保留到 Step 8 机房环境执行。Windows 真实行为同样仍需 Step 8 验收。

### Step 7：形成迁移提交并转入 `jifang3`（待实施）

- 只提交本功能文件，不夹带其他改动。
- 在 `jifang3` 合并或挑选 MacBook 功能提交，保留机房分支现有7个文件的跨平台/排序修改。
- 解决冲突后重新运行后端和前端测试。
- 不在未授权的情况下推送远端。

验证：`git diff MacBook...jifang3` 审计、测试和文档检查。

### Step 8：真实 Windows 机房验收（待实施，依赖机房电脑）

- 安装依赖并初始化 `.env.runner.local`。
- 一键启动/停止并检查中文日志。
- 验证正常代码、错误代码、死循环、持续输出和创建子进程。
- 使用真实机房硬件确定 4/6/8 槽位中的安全值。
- MySQL 环境下完成 40 人规模压测。

验证通过后才将本机 Runner 标记为可用于课堂；MacBook 验收不替代本 Step。

## 7. 关键文件清单

| 文件 | 动作 | 说明 |
| --- | --- | --- |
| `runner/__init__.py`、`runner/__main__.py` | 新增 | 包入口 |
| `runner/config.py` | 新增 | 跨平台配置与校验 |
| `runner/api_client.py` | 新增 | HMAC internal API client |
| `runner/controller.py` | 新增 | 固定 worker 与生命周期 |
| `runner/local_executor.py` | 新增 | 子进程执行、输出/资源/清理 |
| `runner/grader.py`、`runner/results.py` | 新增 | 评测与结构化结果 |
| `runner/tests/*` | 新增 | Runner 自动测试 |
| `scripts/init_local_runner.py` | 新增 | 本地密钥与配置初始化 |
| `scripts/benchmark_local_runner.py`、`scripts/acceptance_*.py` | 新增 | 40 人容量、混合小测和故障恢复验收 |
| `.env.runner.example` | 新增 | 无密钥配置模板 |
| `requirements.txt` | 修改 | 增加跨平台进程观察依赖 |
| `backend/school_platform/settings.py` | 修改 | 加载共享配置、健康门控设置 |
| `backend/execution/services.py` | 修改 | 入队前 Runner 健康检查 |
| `backend/execution/tests/*` | 修改 | 健康门控和集成回归 |
| `start_all.sh`、`stop_all.sh` | 修改 | macOS/Linux Runner 启停 |
| `start_all.bat`、`stop_all.bat` | 修改 | Windows Runner 启停和编码修复 |
| `README.md`、部署/验收文档 | 修改 | 配置、安全边界、迁移与排障 |

## 8. 测试矩阵

| 层级 | 重点 |
| --- | --- |
| 配置单元 | 缺失/非法 secret、URL、并发、解释器路径、上下限 |
| HMAC 客户端 | 精确 body、Unicode、时间戳、UUID、重试与日志脱敏 |
| 执行器单元 | stdout/stderr/stdin、非 UTF-8、超时、输出、内存、进程树、临时清理 |
| 评测单元 | 全对/部分错/异常/超时、多测试点、总预算、快照不变 |
| Controller | 固定槽位、心跳、claim、lease、complete、draining、网络恢复 |
| Django 集成 | Task/Submission 原子状态、503门控、过期恢复、小测结算 |
| 前端回归 | queued/running/final、刷新恢复、错误提示 |
| 端到端 | 浏览器 run/submit/混合小测、Runner/Django 重启 |
| 容量 | 40学生突发、槽位上限、P50/P95、全部终态、无重复 |
| Windows | 路径、编码、进程树、批处理、真实硬件容量 |

## 9. 风险与处理

### 9.1 本机代码逃逸

风险：学生代码与 Runner 使用同一操作系统内核和账号权限。
处理：独立低权限账号、最小环境、受控校园网、禁止生产密钥、明确过渡模式；公网前必须换 Docker。

### 9.2 Windows 子进程残留

风险：学生程序创建子进程后父进程先退出。
处理：psutil 递归清理、进程组、`taskkill /T /F` 兜底和真实 Windows 验收。

### 9.3 SQLite 高并发

风险：40人写入和轮询产生锁竞争。
处理：Mac 只做功能验证；机房正式并发使用 MySQL，并保留现有 `skip_locked` claim。

### 9.4 输出或内存攻击

风险：`communicate()` 先无限缓存再截断会拖垮 Runner。
处理：独立 reader 线程和有界 byte buffer；监控事件触发立即杀进程树。

### 9.5 Runner 响应丢失

风险：claim 已成功但响应丢失，Runner 不再拥有 lease token。
处理：claim 不盲目重试，等待租约过期由现有恢复逻辑重新入队；complete 使用 receipt 幂等重试。

### 9.6 分支迁移冲突

风险：`jifang3` 有独立 Windows 修复。
处理：MacBook 先形成聚焦提交；迁移时保留 `jifang3` 的增量，逐文件审计，不执行覆盖式 checkout/reset。

## 10. 回退方案

1. 设置 `CODE_EXECUTION_ENABLED=false`，立即停止创建新代码任务。
2. 停止 Local Runner；登录、课程、选择题和历史成绩继续使用。
3. 对活动任务运行现有恢复命令，使其进入取消/系统错误或等待后续 Runner。
4. 回退启停脚本和健康门控配置，不回退数据库 migration，因为本阶段没有 schema 变更。
5. 不恢复 Django 内同步 `subprocess` 旧实现。

## 11. 完成定义

只有以下条件全部满足，MacBook 实施才算完成：

- Step 0–7 均标注完成并有验证记录。
- 当前 MacBook 能一键启动 Django、Runner、Vite并完成真实运行/提交。
- 普通练习和混合小测编程题均能正确回写成绩。
- 故障用例均进入明确终态，无永久 queued 和已知残留进程。
- 40学生模拟请求保持固定执行槽且无任务丢失/重复。
- 全量后端、前端测试和静态检查通过，或明确记录与本功能无关的既有基线问题。
- 形成可安全迁移到 `jifang3` 的聚焦提交和 Windows 验收手册。

Windows 机房可用性只有 Step 8 在真实设备通过后才能确认。
