# 阶段 2：MySQL 配置、迁移与回滚手册

日期：2026-09-01

## 1. 结果概览

- 本地安装：Homebrew keg-only MySQL 8.0.46。
- 隔离端口：`127.0.0.1:3308`。
- 迁移库：`python_learning_stage2`。
- 测试库：`python_learning_stage2_test`。
- SQLite 保持为 development/test 默认数据库。
- production 强制 `DJANGO_DB_ENGINE=mysql`。
- 已完成两轮从同一 SQLite 一致性备份到空 MySQL 的迁移演练。

MySQL 当前应处于停止状态；数据目录、迁移目标和本地凭据保留，便于复验。

## 2. 文件与安全边界

以下内容包含敏感数据，不提交 Git：

- `backend/.env.mysql.local`
- `backend/.local/mysql-stage2/`
- `backend/migration_artifacts/`

凭据、SQLite 快照、fixture、manifest 和报告权限均应为 0600；目录权限应为 0700。不要把 `platform-data.json`、SQLite 快照或本地环境文件发送到聊天、邮件或公共云盘。

## 3. 启动和检查 MySQL 8.0

在项目根目录执行：

```bash
cd "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1"
scripts/stage2_mysql_local.sh start
scripts/stage2_mysql_local.sh status
```

预期显示服务端 `8.0.46` 和 `127.0.0.1:3308`。

如果隔离实例尚未初始化：

```bash
scripts/stage2_mysql_local.sh install-check
scripts/stage2_mysql_local.sh init
scripts/stage2_mysql_local.sh start
scripts/stage2_mysql_local.sh provision
```

`provision` 会生成随机密码并写入被 Git 忽略的 `backend/.env.mysql.local`，不会打印密码。

## 4. Django 使用 SQLite 或 MySQL

### 4.1 默认 SQLite

```bash
cd backend
DJANGO_ENV=development DJANGO_DB_ENGINE=sqlite python manage.py check
```

不设置 `DJANGO_DB_NAME` 时使用 `backend/db.sqlite3`。

### 4.2 本地 MySQL

```bash
cd backend
set -a
source .env.mysql.local
set +a
python manage.py check --database default
```

预期：`System check identified no issues`。

不要执行 `cat .env.mysql.local`，也不要把 source 后的环境变量输出到日志。

## 5. 生成新的 SQLite 一致性备份

先确保没有课堂或人工写入正在进行，然后选择一个从未使用过的运行目录名：

```bash
cd "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/backend"
DJANGO_ENV=development DJANGO_DB_ENGINE=sqlite \
python manage.py backup_platform_sqlite \
  --output-dir migration_artifacts/manual-check-01
```

预期生成：

- `source.sqlite3`
- `backup-manifest.json`

命令会检查 SQLite integrity、外键、源文件前后 SHA-256 和文件权限。目录已存在时拒绝覆盖。

## 6. 从快照导出

必须指向上一步快照，直接指向原始 `backend/db.sqlite3` 会被拒绝：

```bash
DJANGO_ENV=development \
DJANGO_DB_ENGINE=sqlite \
DJANGO_DB_NAME="/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/backend/migration_artifacts/manual-check-01/source.sqlite3" \
python manage.py export_platform_data \
  --output-dir "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/backend/migration_artifacts/manual-check-01"
```

预期生成权限 0600 的：

- `platform-data.json`：敏感业务 fixture，不要打开或传播。
- `data-manifest.json`：只含计数、迁移集合和 SHA-256。

## 7. 重建目标并执行 migration

以下操作只会重建固定本地库 `python_learning_stage2`：

```bash
cd "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1"
scripts/stage2_mysql_local.sh reset-target

set -a
source backend/.env.mysql.local
set +a
python backend/manage.py migrate --noinput
python backend/manage.py check --database default
```

脚本不接受任意数据库名；主机、端口或库名不符合固定 stage2 目标时，导入命令也会拒绝执行。

## 8. 导入和验证

```bash
python backend/manage.py import_platform_data \
  --fixture "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/backend/migration_artifacts/manual-check-01/platform-data.json" \
  --manifest "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/backend/migration_artifacts/manual-check-01/data-manifest.json"

python backend/manage.py verify_platform_migration \
  --manifest "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/backend/migration_artifacts/manual-check-01/data-manifest.json" \
  --report "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1/backend/migration_artifacts/manual-check-01/manual-report.json"
```

预期：

- 导入即时摘要校验通过。
- 服务端版本为 MySQL 8.0.x。
- 行数、主键、内容和关系摘要一致。
- 密码哈希与 Token 抽查通过。
- 报告 `status` 为 `ok`。

目标库非空、fixture 被修改、目标不是本地固定库或摘要不一致时，命令必须失败。

## 9. 测试

### SQLite 阶段测试

```bash
cd backend
DJANGO_ENV=test python manage.py test school_platform.tests platform_ops.tests -v 1
```

预期：37 项全部通过。

### MySQL 阶段测试

```bash
cd backend
set -a
source .env.mysql.local
set +a
DJANGO_ENV=test \
DJANGO_DB_NAME=python_learning_stage2_test \
DJANGO_DB_TEST_NAME=python_learning_stage2_test \
python manage.py test school_platform.tests platform_ops.tests --keepdb -v 1
```

预期：37 项全部通过。

## 10. 停止、回滚和清理

停止服务但保留数据：

```bash
cd "/Users/caijinbin/Desktop/白实/信息/python学习网站/Python-----1"
scripts/stage2_mysql_local.sh stop
```

应用回滚到 SQLite：

```bash
cd backend
DJANGO_ENV=development DJANGO_DB_ENGINE=sqlite python manage.py check
```

删除隔离 MySQL 数据和本地凭据属于破坏性操作，不在阶段完成时自动执行。确认不再需要复验后才运行：

```bash
scripts/stage2_mysql_local.sh destroy
```

该命令不会删除 `backend/db.sqlite3` 或 `backend/migration_artifacts/`。

如还要卸载 Homebrew MySQL 8.0，应另行确认后执行：

```bash
brew uninstall mysql@8.0
```
