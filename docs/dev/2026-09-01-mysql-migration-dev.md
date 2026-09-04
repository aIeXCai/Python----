# 阶段 2：MySQL 接入与数据迁移 DEV

关联 PRD：`docs/prd/2026-09-01-mysql-migration-prd.md`
版本：v1.0
日期：2026-09-01
状态：已完成（2026-09-01）

## 1. 实施目标

在不修改当前 `backend/db.sqlite3` 业务数据的前提下，为 Django 增加 MySQL 配置，建立只监听本机的 MySQL 8.0 测试实例，开发安全、可重复的数据备份/导出/导入/校验命令，并完成两轮从同一 SQLite 备份到空 MySQL 的完整演练。

## 2. 技术架构

```text
backend/db.sqlite3（原始源库，只读参与）
          │
          │ backup_platform_sqlite
          ▼
backend/migration_artifacts/<run-id>/
  ├─ source.sqlite3        一致性快照，0600
  ├─ backup-manifest.json  SQLite 完整性与文件 SHA-256
  ├─ platform-data.json    有序 Django fixture，0600
  └─ data-manifest.json    模型计数、PK/内容摘要、关系计数
          │
          │ import_platform_data
          ▼
本地 MySQL 8.0 :3308
  ├─ python_learning_stage2       迁移演练库
  └─ python_learning_stage2_test  Django 集成测试库
          │
          │ verify_platform_migration
          ▼
脱敏验证报告（只含模型、数量、摘要和通过/失败）
```

数据流只有 SQLite → 快照 → MySQL，不提供 MySQL 反写 SQLite 的路径。

## 3. 本地 MySQL 8.0 方案

### 3.1 安装

执行：

```bash
brew install mysql@8.0
```

约束：

- 使用 `/opt/homebrew/opt/mysql@8.0/bin/` 下的绝对工具路径。
- 不执行 `brew link --force`，不替换现有 MySQL 9.4 客户端。
- 不使用 `brew services`，避免开机自动启动。

### 3.2 隔离实例

新增 `scripts/stage2_mysql_local.sh`，支持：

```text
install-check  检查版本和必需工具
init           初始化隔离 data 目录并生成配置
start          在后台启动 MySQL 8.0
status         检查 PID、端口和 SELECT VERSION()
provision      创建两个数据库、最小权限用户和本地环境文件
reset-target   仅重建 python_learning_stage2
reset-test     仅重建 python_learning_stage2_test
stop           优雅停止实例
destroy        停止并删除本阶段隔离实例（不卸载 Homebrew 软件）
```

固定参数：

| 项目 | 值 |
|---|---|
| 数据目录 | `backend/.local/mysql-stage2/data` |
| socket | `/tmp/python-site-stage2-mysql-<uid>/mysql.sock`（项目绝对路径超过 macOS socket 长度限制） |
| 端口 | `3308` |
| 监听地址 | `127.0.0.1` |
| 迁移库 | `python_learning_stage2` |
| 测试库 | `python_learning_stage2_test` |
| 应用用户 | `python_stage2@127.0.0.1` |
| 字符集 | `utf8mb4` |
| 排序规则 | `utf8mb4_0900_ai_ci` |

脚本安全要求：

- 开头使用严格 shell 选项。
- 所有删除前解析并检查绝对路径，目标必须位于 `backend/.local/mysql-stage2`。
- 数据库重建只允许上述两个固定名称，拒绝参数传入任意库名。
- 随机密码使用 `openssl rand` 生成，只写入权限 0600 的 `backend/.env.mysql.local`，不打印到终端。
- MySQL 配置只监听回环地址，禁用 MySQL X Plugin 和 `local_infile`。
- 本地 root 只经私有 socket 做实例管理；Django 只使用最小权限应用用户。

### 3.3 Git 忽略

新增忽略项：

- `backend/.local/`
- `backend/.env.mysql.local`
- `backend/migration_artifacts/`

示例配置仍允许提交。

## 4. Django 数据库配置

### 4.1 新增 `backend/school_platform/database.py`

提供：

- `get_database_engine(environ=None)`：只接受 `sqlite`、`mysql`。
- `get_positive_int(name, default, ...)`：解析端口、连接超时和连接复用时间。
- `build_database_settings(base_dir, environment, environ=None)`：返回完整 `DATABASES['default']`。
- `validate_database_settings(environment, engine, config)`：生产环境和必填项校验。

SQLite：

```python
{
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': DJANGO_DB_NAME or BASE_DIR / 'db.sqlite3',
}
```

MySQL：

```python
{
    'ENGINE': 'django.db.backends.mysql',
    'NAME': DJANGO_DB_NAME,
    'USER': DJANGO_DB_USER,
    'PASSWORD': DJANGO_DB_PASSWORD,
    'HOST': DJANGO_DB_HOST,
    'PORT': DJANGO_DB_PORT,
    'CONN_MAX_AGE': DJANGO_DB_CONN_MAX_AGE,
    'OPTIONS': {
        'charset': 'utf8mb4',
        'connect_timeout': DJANGO_DB_CONNECT_TIMEOUT,
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'",
        'isolation_level': 'read committed',
    },
    'TEST': {'NAME': DJANGO_DB_TEST_NAME},
}
```

校验规则：

- production 非 MySQL 直接拒绝启动。
- MySQL 的 name/user/password/host 均不能为空。
- port 必须为 1–65535；超时和连接复用时间必须为非负整数。
- `DJANGO_DB_TEST_NAME` 为空时使用 `test_<DJANGO_DB_NAME>`；本地环境显式指定固定测试库。

### 4.2 修改 settings 与环境示例

- `backend/school_platform/settings.py` 使用 `build_database_settings()` 替换固定 SQLite 字典。
- `validate_production_settings()` 增加数据库引擎参数，production 必须为 MySQL。
- `backend/.env.example` 补全数据库变量，继续使用占位值。
- 新增 `backend/.env.mysql.example`，对应本地 3308 测试实例，不包含密码。
- `requirements.txt` 增加 `mysqlclient>=2.2.7`。

安装 Python 驱动时使用 MySQL 8.0 的 pkg-config 路径，避免错误链接 9.4 客户端：

```bash
PKG_CONFIG_PATH="/opt/homebrew/opt/mysql@8.0/lib/pkgconfig" \
python -m pip install 'mysqlclient>=2.2.7'
```

## 5. 迁移工具 app

新增无数据模型的 Django app：

```text
backend/platform_ops/
  ├─ __init__.py
  ├─ apps.py
  ├─ migration_data.py
  ├─ tests/
  └─ management/commands/
       ├─ backup_platform_sqlite.py
       ├─ export_platform_data.py
       ├─ import_platform_data.py
       └─ verify_platform_migration.py
```

将 `platform_ops` 加入 `INSTALLED_APPS`，不新增数据库表或 migration。

### 5.1 统一模型清单与顺序

`migration_data.py` 定义唯一权威顺序：

1. `auth.Group`
2. `users.CustomUser`
3. `authtoken.Token`
4. `ai_courses.Problem`
5. `info_tech.Unit`
6. `ai_courses.Submission`
7. `info_tech.Question`
8. `info_tech.QuizSession`
9. `info_tech.QuizSubmission`
10. `chat.ChatSession`
11. `chat.ChatMessage`

系统 `ContentType` 和 `Permission` 由 MySQL migration 生成；Group 权限和用户权限使用 Django natural foreign key 表达。admin log 和 session 不进入业务迁移。

### 5.2 规范化摘要

每个模型：

1. 按主键排序。
2. 使用 Django JSON serializer，开启 natural foreign keys，保留业务主键。
3. JSON 规范化为 UTF-8、key 排序、无多余空格。
4. 分别生成：`count`、主键列表 SHA-256、内容 SHA-256。

额外关系计数：

- `auth.Group.permissions`
- `users.CustomUser.groups`
- `users.CustomUser.user_permissions`
- `info_tech.QuizSession.units`

manifest 只包含计数和摘要，不包含业务值。

### 5.3 `backup_platform_sqlite`

用法：

```bash
DJANGO_DB_ENGINE=sqlite python manage.py backup_platform_sqlite \
  --output-dir migration_artifacts/<run-id>
```

流程：

1. 拒绝非 SQLite 引擎。
2. 以只读连接执行源库 `integrity_check`、`foreign_key_check`。
3. 使用 Python sqlite3 backup API 生成 `source.sqlite3`。
4. 再次检查备份完整性。
5. 计算源库和备份 SHA-256，记录源文件 stat 和模型行数。
6. 设置目录 0700、文件 0600，原子写入 `backup-manifest.json`。

### 5.4 `export_platform_data`

用法：

```bash
DJANGO_DB_ENGINE=sqlite \
DJANGO_DB_NAME=/absolute/path/source.sqlite3 \
python manage.py export_platform_data --output-dir /absolute/path/run
```

流程：

1. 拒绝非 SQLite 源或指向原始 `backend/db.sqlite3`，确保只从快照导出。
2. 按权威顺序序列化为 `platform-data.json`。
3. 写入 `data-manifest.json`：格式版本、生成时间、已应用 migration、文件 SHA-256、模型摘要和关系计数。
4. 文件权限设为 0600，输出只显示路径、模型名和计数。

### 5.5 `import_platform_data`

用法：

```bash
python manage.py import_platform_data \
  --fixture /absolute/path/platform-data.json \
  --manifest /absolute/path/data-manifest.json
```

流程：

1. 拒绝非 MySQL、非本机演练库或非空业务表。
2. 校验 fixture SHA-256 和 manifest 版本。
3. 校验目标 migration 集合与源 manifest 一致。
4. 在 `transaction.atomic()` 和数据库约束保护内按 fixture 顺序保存对象及 deferred M2M。
5. 执行外键约束检查。
6. 使用 Django sequence reset SQL 重置自增值。
7. 立即计算目标摘要；不一致则抛错，整轮不得生成成功标记。

RDS 复用时将通过显式 `--allow-remote-target` 和二次确认机制扩展；本阶段命令默认只允许 `127.0.0.1:3308` 及固定 stage2 库。

### 5.6 `verify_platform_migration`

用法：

```bash
python manage.py verify_platform_migration \
  --manifest /absolute/path/data-manifest.json \
  --report /absolute/path/round-1-report.json
```

检查：

- 当前 vendor 为 mysql，`SELECT VERSION()` 为 8.0.x。
- migration 集合一致。
- 每个模型 count、PK SHA-256、内容 SHA-256 一致。
- 四类 M2M 关系计数一致。
- `connection.check_constraints()` 通过。
- 用户密码哈希、Token 非空及历史 `plain_password` 的 `check_password` 只输出通过数量。
- 生成不含敏感值的 JSON 报告；任一失败退出码非 0。

## 6. 测试设计

### 6.1 配置单元测试

新增 `backend/school_platform/tests/test_database.py`：

1. development/test 默认 SQLite。
2. 自定义 SQLite 快照路径生效。
3. MySQL 参数正确生成。
4. 非法引擎、端口、连接时间被拒绝。
5. MySQL 缺少 name/user/password/host 被拒绝。
6. production + SQLite 被拒绝。
7. production + 完整 MySQL 配置通过。

同步修改阶段 1 production 测试和 `check --deploy` 命令，补充 MySQL 变量。

### 6.2 迁移工具单元测试

新增 `backend/platform_ops/tests/`：

- 模型顺序和覆盖范围固定。
- manifest 不包含密码、Token、代码或对话正文。
- 同一数据两次摘要一致，字段变化会导致摘要变化。
- SQLite 完整性/外键失败会中止备份。
- 备份和导出文件权限正确。
- 导出拒绝原始 SQLite 文件。
- 导入拒绝 SQLite、远程主机、错误库名、非空目标和损坏 checksum。
- 验证失败返回非零并且报告不泄露敏感字段。

### 6.3 MySQL 集成测试

在 `python_learning_stage2_test` 上执行：

```bash
set -a
source backend/.env.mysql.local
set +a
DJANGO_ENV=test DJANGO_DB_NAME=python_learning_stage2_test \
DJANGO_DB_TEST_NAME=python_learning_stage2_test \
python backend/manage.py test school_platform.tests platform_ops.tests --keepdb -v 2
```

额外创建测试数据，覆盖：用户、Token、JSONField、Unit 自关联、QuizSession.units、多级外键和级联删除。

### 6.4 全量回归

- SQLite 全量测试记录与阶段 1 基线对比。
- MySQL 至少运行数据库配置、迁移工具和模型/API 核心测试。
- 既有 `template_code` 两项失败单独记录，不计为本阶段新增失败。

## 7. 两轮迁移演练

### Round 1

1. 记录原始 SQLite 文件 SHA-256、完整性和业务计数。
2. 生成一次一致性备份和 fixture/manifest。
3. `reset-target` 重建空 MySQL 库。
4. 对 MySQL 执行 `migrate --noinput` 和 `check --database default`。
5. 导入 fixture。
6. 运行完整验证，生成 `round-1-report.json`。
7. 使用 Django shell/API 内部抽查登录哈希、题库、成绩和对话关系，不输出敏感值。

### Round 2

1. 使用同一份备份和 fixture。
2. 再次 `reset-target`、migrate、import、verify。
3. 生成 `round-2-report.json`。
4. 比较两轮目标总摘要，必须完全一致。
5. 再次计算原始 SQLite SHA-256，确认未被本阶段改变。

演练完成后停止 MySQL；保留加密边界内的本地敏感 artifacts，完成报告只引用脱敏结果。用户可按文档选择保留或删除 artifacts。

## 8. 文件改动清单

### 新增

- `backend/school_platform/database.py`
- `backend/school_platform/tests/test_database.py`
- `backend/platform_ops/` 及管理命令、测试
- `scripts/stage2_mysql_local.sh`
- `backend/.env.mysql.example`
- `docs/deployment/stage-2-mysql-migration.md`
- `docs/reports/2026-09-01-stage-2-completion.md`

### 修改

- `backend/school_platform/settings.py`
- `backend/school_platform/environment.py`
- `backend/school_platform/tests/test_environment.py`
- `backend/.env.example`
- `.gitignore`
- `requirements.txt`
- 阶段 2 PRD、DEV 和总路线图状态

### 运行时生成且不提交

- `backend/.local/mysql-stage2/`
- `backend/.env.mysql.local`
- `backend/migration_artifacts/<run-id>/`

## 9. 实施步骤与状态

### Step 1：数据库配置与测试 ✅ 已完成

- [x] 新增 database 配置模块。
- [x] 修改 settings、生产校验和环境示例。
- [x] 增加 mysqlclient 依赖。
- [x] 完成 SQLite/MySQL/production 配置测试。

### Step 2：本地 MySQL 8.0 ✅ 已完成

- [x] 安装 keg-only MySQL 8.0，不覆盖现有客户端。
- [x] 实现并审查隔离实例脚本。
- [x] 初始化、启动并确认服务端版本为 8.0.x。
- [x] 创建固定测试库、最小权限用户和本地凭据文件。

### Step 3：备份、导出、导入和验证工具 ✅ 已完成

- [x] 新增 platform_ops app 和权威模型清单。
- [x] 实现一致性 SQLite 备份及 manifest。
- [x] 实现有序 fixture 导出及内容摘要。
- [x] 实现空 MySQL 安全导入、约束检查和序列重置。
- [x] 实现迁移验证与脱敏报告。
- [x] 完成管理命令单元测试和负向安全测试。

### Step 4：MySQL migration 与集成测试 ✅ 已完成

- [x] 在空 MySQL 8.0 库执行全部 migration。
- [x] 运行 `check --database default`。
- [x] 完成 MySQL 关键数据类型和关系集成测试。
- [x] 执行 SQLite 全量回归并对比阶段 1 基线。

### Step 5：两轮数据迁移演练 ✅ 已完成

- [x] 生成源 SQLite 一致性备份和数据 manifest。
- [x] 完成 Round 1 导入、验证和脱敏报告。
- [x] 完成 Round 2 重建、导入、验证和脱敏报告。
- [x] 对比两轮摘要并确认源 SQLite 未被修改。
- [x] 停止本地 MySQL 服务。

### Step 6：文档与阶段汇报 ✅ 已完成

- [x] 编写配置、迁移、回滚和清理手册。
- [x] 更新 PRD、DEV、路线图状态。
- [x] 生成阶段 2 完成报告。
- [x] 提供用户可复制的验证步骤和预期结果。

## 10. 完成门槛

只有以下证据全部存在，阶段 2 才标记完成：

- 实际 MySQL 服务端版本为 8.0.x。
- 全部 Django migration 在空 MySQL 执行成功。
- 阶段 2 新增测试全部通过，后端回归无新增失败。
- 备份文件和 manifest 完整性通过，源 SQLite 前后 SHA-256 一致。
- 两轮迁移的模型计数、PK 摘要、内容摘要、关系计数全部一致。
- 密码哈希、Token、题库、提交、小测和对话抽查通过且无敏感输出。
- MySQL 已停止，端口 3308 不再监听。
- 运行时凭据和迁移 artifacts 均未被 Git 跟踪。
- 路线图、DEV 和阶段完成报告已更新。

## 11. 回滚与清理

- 应用回滚：设置 `DJANGO_DB_ENGINE=sqlite` 并指向原 `backend/db.sqlite3`。
- 演练回滚：执行脚本 `reset-target` 后从同一 fixture 重试。
- 服务停止：`scripts/stage2_mysql_local.sh stop`。
- 删除隔离实例：用户确认后执行 `destroy`；该操作会删除本阶段生成的 MySQL data 目录，不删除源 SQLite 或迁移 artifacts。
- 卸载 Homebrew 软件不是自动步骤；如用户决定卸载，文档提供 `brew uninstall mysql@8.0`，执行前再次确认。
