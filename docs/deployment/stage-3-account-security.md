# 阶段 3：账号与学生数据安全运维手册

文档日期：2026-09-01
适用范围：本地开发、SQLite、隔离 MySQL 8.0，以及后续阿里云生产环境

## 1. 安全模型

- 学生登录仍使用 Django `password` 不可逆哈希。
- 教师查看使用 `encrypted_password` 认证加密密文；数据库本身不保存可直接读取的学生密码。
- 教师密码没有可恢复副本。
- 普通学生详情、列表、统计、日志和审计均不返回密码或密文。
- 只有有效教师 Token 可以调用单学生密码揭示/重置接口。
- Token 默认最长有效 12 小时；注销、学生改密/重置、账号停用后旧 Token 失效。

可恢复密码仍比纯哈希方案风险更高。生产密钥必须和数据库分开保存，并限制只有 Django 运行身份可以读取。

## 2. 环境变量

```dotenv
DJANGO_STUDENT_PASSWORD_KEYS=stage3-v1:<generated-fernet-key>
DJANGO_STUDENT_PASSWORD_PRIMARY_KEY_ID=stage3-v1
DJANGO_TOKEN_TTL_HOURS=12
DJANGO_PASSWORD_REVEAL_LIMIT=30
DJANGO_PASSWORD_REVEAL_SECONDS=30
```

规则：

- 不把真实 key 写入仓库、部署文档、日志或数据库。
- `DJANGO_STUDENT_PASSWORD_KEYS` 支持多个 `key_id:key`，使用英文逗号分隔。
- primary key 用于新注册、新重置和密钥轮换后的写入。
- production 缺少有效配置时拒绝启动。
- key 与 `DJANGO_SECRET_KEY`、数据库密码必须不同。

## 3. 本地密钥

在项目根目录执行：

```bash
scripts/stage3_security_local.sh init
scripts/stage3_security_local.sh status
```

`init` 只在文件不存在时生成 `backend/.env.security.local`，不会覆盖已有 key，也不会打印 key。预期权限：

```text
-rw------- backend/.env.security.local
```

不要随意执行 `destroy`。删除 key 后，使用该 key 的密文无法查看；学生登录哈希仍有效，教师可以逐账号重置生成新密文。

## 4. 数据库升级

升级前先停止业务写入，并创建一致性备份。SQLite：

```bash
python backend/manage.py backup_platform_sqlite \
  --output-dir backend/migration_artifacts/<stage3-pre-upgrade>
```

确认密钥状态后执行：

```bash
scripts/stage3_security_local.sh status
python backend/manage.py migrate
python backend/manage.py verify_stage3_password_migration \
  --report migration_artifacts/<stage3-report-dir>/security-report.json
```

成功标准：

- `users.0006` 和 `users.0007` 均为 applied。
- 报告 `status=ok`。
- `plain_password_column_removed=true`。
- 可恢复密码 checked/valid 相等。
- 教师密文数量为 0。

报告只包含数量和状态，不包含用户、密码、哈希、密文、key ID 或 Token。

## 5. MySQL 8.0 本地复核

```bash
scripts/stage2_mysql_local.sh start
set -a
source backend/.env.mysql.local
set +a
python backend/manage.py migrate
python backend/manage.py check --database default
python backend/manage.py verify_stage3_password_migration \
  --report migration_artifacts/<stage3-report-dir>/mysql-security-report.json
scripts/stage2_mysql_local.sh stop
```

不要把 `source backend/.env.mysql.local` 替换成打印文件内容。验证结束确认 3308 未监听。

## 6. 教师操作

### 查看密码

1. 进入“教师后台 → 学生管理”。
2. 学生密码默认显示 `••••••••`。
3. 点击“显示”，确认用途提示。
4. 当前密码显示 30 秒后自动隐藏；也可立即点击“隐藏”。
5. 页面离开、弹窗关闭或退出登录会清除页面内存中的显示值。

每次成功、拒绝、目标不存在、不可恢复或限流都会产生不含密码的审计记录。默认单教师每分钟最多 30 次查看。

### 重置密码

- 手工方式：输入至少 8 位且符合 Django 验证规则的新密码。
- 随机方式：点击“生成随机临时密码”，服务端生成至少 12 位密码并短时显示。
- 两种方式都会撤销学生旧 Token；旧密码不能再登录。
- 当前不强制学生首次登录修改临时密码。

## 7. Token 行为

- 前端退出会先请求 `POST /api/auth/logout/`，再清理本地状态。
- 网络失败仍清理本地状态；服务端 Token 最迟在最长有效期后失效。
- 超过 `DJANGO_TOKEN_TTL_HOURS` 后接口返回 401，重新登录签发新 Token。
- 教师重置学生密码时，学生全部旧 Token 在同一事务中删除。
- 已停用账号使用旧 Token 时返回 401，并删除该 Token。

调整有效期后必须重新运行过期边界、登录、注销和密码重置测试。

## 8. 密钥轮换

假设现有 key ID 为 `stage3-v1`，新 key ID 为 `stage3-v2`：

1. 使用安全方式生成新的 Fernet key，不打印到共享日志。
2. 环境中同时保留旧、新 key，并把 primary 指向新 key：

```dotenv
DJANGO_STUDENT_PASSWORD_KEYS=stage3-v1:<old-key>,stage3-v2:<new-key>
DJANGO_STUDENT_PASSWORD_PRIMARY_KEY_ID=stage3-v2
```

3. 重启/滚动发布应用，先执行只读预演：

```bash
python backend/manage.py rotate_student_password_keys
```

4. 创建数据库备份，再应用轮换：

```bash
python backend/manage.py rotate_student_password_keys --apply
python backend/manage.py verify_stage3_password_migration \
  --report migration_artifacts/<new-report-dir>/key-rotation-report.json
```

5. 查询所有 `available` 记录的 key ID 均为新 ID后，才可从环境移除旧 key。
6. 再次重启应用并验证教师查看、学生登录和重置。

轮换命令只输出校验/轮换数量，不输出密码、密文或 key。

## 9. 故障处理

### 密钥缺失或配置错误

- production 会拒绝启动。
- 学生登录哈希不受影响。
- 密码查看返回安全失败，不应改回数据库明文。
- 恢复正确 key 后重启；无法恢复旧 key 时由教师重置对应学生密码。

### 密文损坏或哈希不一致

- 揭示接口返回 409“密码不可查看，请重置”。
- 记录 `decrypt_failed` 或 `hash_mismatch_runtime`，不记录原始异常材料。
- 教师执行密码重置后生成当前 primary key 密文。

### Token 异常

- 检查服务器时间和 `DJANGO_TOKEN_TTL_HOURS`。
- 不在日志中打印 Token 排查；使用用户 ID、时间和 HTTP 状态定位。
- 必要时删除该用户 Token，让其重新登录。

## 10. 备份与敏感产物

即使新版 fixture 不含明文字段，仍包含密码哈希、密码密文、Token 和业务数据，必须：

- 位于 Git 忽略目录。
- 目录权限 `0700`，文件权限 `0600`。
- 不通过聊天、邮件或公共网盘传播。
- 超过恢复需要后按精确路径删除。

阶段 2 旧 fixture/SQLite 和阶段 3 迁移前 SQLite 含历史明文字段。阶段 3 完成前会列出精确目录，取得用户确认后删除；不执行宽泛路径递归删除。

## 11. 验证命令

```bash
python backend/manage.py check
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py test users platform_ops.tests
```

完整后端回归必须在 `backend` 目录执行无标签发现：

```bash
cd backend
python manage.py test
```

从仓库根目录执行 `python backend/manage.py test` 会发现 0 项，不能作为有效全量测试结果。

前端正常验证：

```bash
cd frontend
npm test -- src/api/index.test.js src/contexts/AuthContext.test.jsx \
  src/pages/teacher/StudentManagement.test.jsx
npm run build
npm run lint
```

如果本机 Vitest/Vite/ESLint 在 worker 或 transform 阶段挂起，必须记录为未验证，不得表述为通过；可额外用 Babel parser 做语法检查，但不能替代行为测试。
