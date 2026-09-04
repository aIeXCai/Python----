# 阶段 2 完成报告：MySQL 接入与数据迁移

完成日期：2026-09-01
关联 PRD：`docs/prd/2026-09-01-mysql-migration-prd.md`
关联 DEV：`docs/dev/2026-09-01-mysql-migration-dev.md`

## 1. 完成内容

1. Django 支持 `DJANGO_DB_ENGINE=sqlite|mysql`，development/test 默认 SQLite，production 强制 MySQL。
2. MySQL 名称、用户、密码、主机、端口、连接复用、连接超时和测试库均可通过环境变量配置。
3. 安装 Homebrew keg-only MySQL 8.0.46，没有强制链接替换现有 MySQL 9.4 客户端，没有注册开机服务。
4. 安装并验证 `mysqlclient 2.2.8`，编译时使用 MySQL 8.0 pkg-config。
5. 建立隔离实例脚本，固定监听 `127.0.0.1:3308`，固定 stage2 数据库名，并加入删除保护。
6. 建立最小权限 `python_stage2@127.0.0.1` 用户；随机密码仅保存在权限 0600、被 Git 忽略的本地环境文件。
7. 新增 SQLite 在线一致性备份、业务 fixture 导出、空 MySQL 安全导入和摘要验证命令。
8. 迁移覆盖用户/权限关系、Token、AI 题目与提交、信息课单元/题目/小测/成绩、多对多关系和 AI 对话。
9. 完成两轮“重建空库 → 全部 migration → import → verify”，两轮目标摘要完全一致。
10. 修复一个既有测试中硬编码 `problem_id=1` 的跨数据库问题，改为引用实际创建的题目对象。
11. 完成 SQLite/MySQL 阶段测试、两个数据库的全量回归、生产部署检查和 API 抽查。
12. 验证完成后已停止 MySQL，端口 3308 不再监听；MySQL 数据和凭据保留供用户复验。

## 2. 关键改动文件

### 数据库配置

- `backend/school_platform/database.py`：SQLite/MySQL 配置解析及安全校验。
- `backend/school_platform/settings.py`：接入动态 DATABASES，注册运维 app。
- `backend/school_platform/environment.py`：production 强制 MySQL。
- `backend/.env.example`、`backend/.env.mysql.example`：配置模板。
- `requirements.txt`：加入 `mysqlclient>=2.2.7`。

### 迁移工具

- `backend/platform_ops/migration_data.py`：权威模型顺序、规范化序列化、摘要和安全守卫。
- `backup_platform_sqlite`：在线备份、SQLite 完整性/外键及源文件前后 SHA-256。
- `export_platform_data`：从快照导出有序 fixture 和脱敏 manifest。
- `import_platform_data`：只允许空的本地固定 MySQL 库，事务导入、约束检查、序列重置和即时摘要比较。
- `verify_platform_migration`：MySQL 版本、模型、主键、内容、关系、密码哈希和 Token 校验及脱敏报告。
- `scripts/stage2_mysql_local.sh`：隔离实例生命周期和固定库重建。

### 测试与文档

- `backend/school_platform/tests/test_database.py`
- `backend/platform_ops/tests/test_migration_data.py`
- `backend/ai_courses/tests.py`：移除测试中的固定主键假设。
- `docs/deployment/stage-2-mysql-migration.md`
- 阶段 2 PRD、DEV、总路线图和本报告。

仓库中另有阶段 1 以及用户既存/并行改动，本阶段没有覆盖或回退无关内容。

## 3. 系统环境变化

- Homebrew 新增 `mysql@8.0 8.0.46_4`，约 317MB。
- Homebrew 为安装 MySQL 更新了若干依赖，包括 abseil、CA certificates、libevent、libcbor、libfido2 和 protobuf，并新增 zlib-ng-compat。
- Homebrew 安装过程初始化了它自己的默认 `/opt/homebrew/var/mysql` 目录，但本项目不启动或使用该默认实例；项目使用独立忽略目录。
- 当前 Python 环境新增 `mysqlclient 2.2.8`。
- 没有配置 Homebrew 开机服务，没有覆盖 `/opt/homebrew/opt/mysql-client/bin/mysql`。

## 4. 数据迁移结果

### 4.1 源库

- SQLite 大小约 280KB。
- integrity check：通过。
- foreign key violations：0。
- 备份前后及最终源 SQLite SHA-256：一致，源业务数据未被本阶段修改。

### 4.2 迁移数据

| 模型 | 行数 |
|---|---:|
| 用户 | 4 |
| Token | 3 |
| AI 题目 | 9 |
| AI 提交 | 9 |
| 信息课单元 | 58 |
| 信息课题目 | 17 |
| 小测 | 1 |
| 小测提交 | 2 |
| 对话会话 | 1 |
| 对话消息 | 2 |

Group 当前为 0；小测与单元多对多关系已包含在摘要校验中。

### 4.3 两轮演练

| 检查 | Round 1 | Round 2 |
|---|---|---|
| 空库全部 migration | 通过 | 通过 |
| fixture SHA-256 | 通过 | 通过 |
| 模型行数/PK/内容摘要 | 通过 | 通过 |
| M2M 关系摘要 | 通过 | 通过 |
| 外键约束 | 通过 | 通过 |
| MySQL 服务端版本 | 8.0.46 | 8.0.46 |
| 密码哈希抽查 | 2/2 | 2/2 |
| Token 非空抽查 | 3/3 | 3/3 |
| 最终状态 | ok | ok |

两轮 `actual_overall_sha256` 完全一致。重复向非空目标导入时命令以非零状态拒绝，没有覆盖数据。

## 5. 测试与检查结果

### 5.1 阶段测试

- SQLite：37/37 通过。
- MySQL 8.0：37/37 通过。
- 覆盖配置、健康检查、摘要、敏感信息保护、文件权限、目标安全守卫、JSONField、自关联、多对多和级联删除。

### 5.2 全量回归

- SQLite：323 项，321 通过、2 项既有失败。
- MySQL：323 项，321 通过、2 项同样的既有失败，无 MySQL 新增错误。
- 两项既有失败：
  - `ProblemDetailViewTest.test_detail_includes_template_code`
  - `ProblemDetailSerializerTest.test_serializer_includes_template_code`

初次 MySQL 全量测试暴露的 3 个固定主键错误已修复；修复后 SQLite 与 MySQL 失败集合完全相同。

### 5.3 生产与代码检查

- MySQL production `check --deploy`：0 个问题。
- `makemigrations --check --dry-run`：No changes detected。
- Python compileall、bash 语法、`git diff --check`：通过。
- 生成的随机数据库密码出现在可被 Git 跟踪文件中的数量：0。
- 本地凭据、MySQL data 和 migration artifacts：均由 Git ignore 命中。
- 所有敏感文件权限：0600。
- 完成后端口 3308 监听：false。

### 5.4 MySQL 业务 API 抽查

- 学生 Token 访问题目 API：200。
- 教师 Token 访问后台统计 API：200。
- 迁移后的学生账号登录 API：200。
- 题目、成绩、小测、对话列表：全部 200。
- 现有教师没有可用于自动抽查的 `plain_password`，因此未读取或重置教师密码；教师迁移 Token 已验证可用。

## 6. 用户验证步骤

### 步骤 1：启动并检查 MySQL

```bash
cd "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1"
scripts/stage2_mysql_local.sh start
scripts/stage2_mysql_local.sh status
```

预期显示 MySQL `8.0.46`、`127.0.0.1:3308`。

### 步骤 2：检查 Django MySQL 连接

```bash
cd backend
set -a
source .env.mysql.local
set +a
python manage.py check --database default
```

预期：`System check identified no issues`。

### 步骤 3：运行阶段测试

SQLite：

```bash
DJANGO_ENV=test DJANGO_DB_ENGINE=sqlite \
python manage.py test school_platform.tests platform_ops.tests -v 1
```

MySQL：

```bash
DJANGO_ENV=test \
DJANGO_DB_NAME=python_learning_stage2_test \
DJANGO_DB_TEST_NAME=python_learning_stage2_test \
python manage.py test school_platform.tests platform_ops.tests --keepdb -v 1
```

两条都应显示 `Ran 37 tests` 和 `OK`。

### 步骤 4：再次校验现有迁移结果

确保已经 source `.env.mysql.local`，然后执行：

```bash
python manage.py verify_platform_migration \
  --manifest "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/backend/migration_artifacts/stage2-20260901/data-manifest.json" \
  --report "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/backend/migration_artifacts/stage2-20260901/user-recheck-report.json"
```

预期显示迁移完整性通过、密码哈希 2/2、Token 3/3。若该报告名已存在，请换一个新的文件名；命令不会覆盖报告。

### 步骤 5：浏览器验证

保持 MySQL 环境变量已加载，启动后端：

```bash
python manage.py runserver 127.0.0.1:8080
```

另开终端启动阶段 1 前端：

```bash
cd "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/frontend"
npm run dev -- --host 127.0.0.1
```

打开 `http://127.0.0.1:5173/`：

1. 使用现有学生账号登录。
2. 查看题目、成绩、小测和 AI 对话历史。
3. 使用现有教师账号登录，查看学生和题库统计。
4. Network 中相关 `/api/...` 请求应返回 200。

### 步骤 6：停止服务

浏览器验证结束后，前后端终端按 `Ctrl+C`，然后：

```bash
cd "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1"
scripts/stage2_mysql_local.sh stop
```

完整备份、导出、重建、导入及回滚步骤见 `docs/deployment/stage-2-mysql-migration.md`。

## 7. 已知限制与下一步

- 当前 MySQL 8.0 只用于本地兼容性验证；正式环境仍需阶段 10 创建 RDS。
- Homebrew MySQL 8.0 已被上游停止支持，只作为匹配目标 RDS 8.0 的短期本地工具。
- `plain_password` 仍存在并被原样迁移；阶段 3 必须优先删除这一设计。
- 本地 migration artifacts 含敏感数据，虽然被忽略且权限受限，仍不应长期无管理地保留。
- 后端仍有 2 项既有 `template_code` 测试失败，前端工具链停滞仍留在阶段 9。
- Python `requests` 依赖版本警告仍存在，但未影响本阶段测试或迁移。

下一步建议：进入阶段 3“账号与学生数据安全”，首先删除明文密码设计。
