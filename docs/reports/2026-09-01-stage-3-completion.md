# 阶段 3：账号与学生数据安全完成报告

文档日期：2026-09-01
文档状态：阶段 3 已完成
对应 PRD：`docs/prd/2026-09-01-account-student-data-security-prd.md`
对应 DEV：`docs/dev/2026-09-01-account-student-data-security-dev.md`

## 1. 完成内容

1. 删除当前 `CustomUser.plain_password` 模型和数据库列。
2. 学生可恢复密码改为 Fernet 认证加密密文，并记录 key ID 与恢复状态。
3. Django 登录哈希继续作为登录验证的唯一依据；教师账号不保存可恢复密文。
4. 历史数据按哈希核验后加密回填，SQLite 和 MySQL 8.0 均为 2/2 有效。
5. 学生注册、教师手工重置和随机临时密码统一通过事务服务写入哈希与密文。
6. 教师密码查看改为单学生专用 POST 接口，普通详情/列表不返回密码或密文。
7. 查看接口使用有效教师 Token、数据库事务限流、no-store 响应和安全审计。
8. 教师前端默认遮罩，确认后短时显示 30 秒，可立即隐藏，页面卸载/弹窗关闭时清理。
9. 支持教师手工重置和服务端生成至少 12 位随机临时密码。
10. Token 默认最长有效 12 小时；注销、密码重置和账号停用后旧 Token 失效。
11. 前端注销会请求后端，再在 finally 中清理本地 Token/user；网络失败仍清理和导航。
12. 增加不含密码、密文、Token 或请求正文的查看/重置审计模型和只读 admin。
13. 增加密钥配置检查、本地密钥工具、脱敏迁移核验和 primary key 轮换命令。
14. 阶段 2 导出 manifest 升级为 v2，未来 fixture 包含密文而不包含历史明文字段。

## 2. 关键实现

### 配置与加密

- `backend/users/security.py`
- `backend/users/checks.py`
- `backend/.env.security.example`
- `scripts/stage3_security_local.sh`
- `requirements.txt`

真实本地 key 保存于被 Git 忽略、权限 0600 的 `backend/.env.security.local`，未写入报告或可提交文件。

### 模型与迁移

- `backend/users/models.py`
- `backend/users/migrations/0006_add_encrypted_password_and_audit.py`
- `backend/users/migrations/0007_remove_plain_password.py`
- `backend/users/management/commands/verify_stage3_password_migration.py`
- `backend/users/management/commands/rotate_student_password_keys.py`

### 后端安全链路

- `backend/users/services.py`
- `backend/users/authentication.py`
- `backend/users/permissions.py`
- `backend/users/views.py`
- `backend/users/serializers.py`
- `backend/users/urls.py`
- `backend/users/admin.py`

### 前端

- `frontend/src/api/index.js`
- `frontend/src/contexts/AuthContext.jsx`
- `frontend/src/components/Navbar.jsx`
- `frontend/src/pages/teacher/TeacherDashboard.jsx`
- `frontend/src/pages/teacher/StudentManagement.jsx`
- 对应 API、Context、教师页面测试文件

### 数据迁移工具

- `backend/platform_ops/migration_data.py`
- `backend/platform_ops/management/commands/verify_platform_migration.py`
- `backend/platform_ops/tests/test_migration_data.py`

## 3. SQLite 迁移结果

- 迁移前一致性备份：完成，文件权限 0600。
- `users.0006`：成功。
- `users.0007`：成功。
- 当前 schema 的 `plain_password` 列：不存在。
- 历史可恢复密码：2/2 解密后与 Django 哈希匹配。
- 教师密文记录：0。
- 数据库约束：通过。
- 脱敏报告：`backend/migration_artifacts/stage3-20260901/sqlite-report.json`。

## 4. MySQL 8.0 结果

服务端实际版本：MySQL 8.0.46。

### 从阶段 2 旧库升级

- 起点：users migration 0005，有历史业务数据。
- 0006/0007：成功。
- 可恢复密码：2/2。
- 安全核验报告：`mysql-upgrade-report.json`，状态 ok。

### 从空库重建并导入新版 fixture

- 全部 Django migration：成功。
- v2 fixture 导入与即时摘要：成功。
- 业务模型、主键、关系和内容摘要：一致。
- 可恢复密码：2/2。
- Token 非空：3/3。
- 普通详情敏感字段数量：0。
- 迁移学生登录：HTTP 200。
- 教师揭示密码：HTTP 200，解密值与登录哈希匹配。

本地 MySQL 已停止，`127.0.0.1:3308` 当前未监听。

## 5. 自动测试结果

### 后端 SQLite

- 当前全量：346 项，344 项通过，2 项失败。
- 失败仍为阶段前相同的：
  - `ai_courses.tests.ProblemDetailViewTest.test_detail_includes_template_code`
  - `ai_courses.tests_model.ProblemDetailSerializerTest.test_serializer_includes_template_code`
- 阶段 3 新增失败：0。

### 后端 MySQL

- 全量（增加最终轮换测试前）：345 项，343 项通过，同样 2 项既有失败。
- 当前 users + platform_ops 定向：72/72 通过，包含最终密钥轮换测试。
- SQLite/MySQL 阶段 3 行为无差异。

### 配置与静态检查

- `python manage.py check`：0 问题。
- production `check --deploy`：0 问题。
- production 缺少学生密码 key：正确拒绝启动。
- `makemigrations --check --dry-run`：No changes detected。
- Django 源码目录 compileall：通过；学生提交目录不属于项目源码，未纳入 compileall。
- `git diff --check`：通过。
- 本地真实 key/数据库密码在可提交文件中的命中：0。
- 本地真实 key/数据库密码在阶段 3 报告中的命中：0。
- 运行时代码（排除历史 migration、迁移测试和核验字段名）的 `plain_password` 引用：0。
- 前端密文字段、本地密码存储或密码 console 输出引用：0。

### 前端

- 9 个阶段 3 JS/JSX 文件通过 Babel parser 语法解析。
- API Node smoke：专用 reveal/reset/generated/logout 路径与 POST 行为通过，本地凭据在 logout 后清除。
- 首次验证时 Vitest/Vite/ESLint 曾因本地依赖文件读取不稳定而挂起。
- 2026-09-02 复测：Vitest 22/22 个测试文件通过，277 个测试通过，2 个跳过，未处理错误为 0。
- 2026-09-02 复测：Vite 生产构建通过，2,975 个模块完成转换。
- 2026-09-02 治理：ESLint 已排除 `.vite`/`dist`/`coverage` 生成目录，补齐 Vitest/Node 全局变量配置并清理死代码；全仓库结果为 0 errors、48 warnings，`npm run lint` 成功退出。

前端行为测试、正式构建和全仓库 lint 现已通过。lint 仍保留 48 条不阻断的 React Hooks/Fast Refresh 架构迁移警告。

## 6. 安全验证

- 匿名揭示：401。
- 学生揭示/重置：403。
- 教师查看教师或不存在目标：404。
- 密码不可恢复：409，不返回密码字段。
- 每分钟超过配置次数：429。
- 揭示成功：200 + no-store + 审计。
- 手工重置：新密码成功、旧密码失败、旧 Token 401。
- 随机重置：随机密码成功登录、旧 Token 401。
- Token 超过 12 小时：401 并删除。
- 停用账号 Token：401 并删除。
- 审计 schema 不含 password/plaintext/ciphertext/token/request_body 字段。
- 密钥轮换：旧 key 密文成功重加密到 primary key，登录哈希不变。

## 7. 用户验证步骤

### 后端

```bash
cd backend
python manage.py check
python manage.py verify_stage3_password_migration \
  --report migration_artifacts/<new-directory>/manual-check.json
python manage.py test users platform_ops.tests
```

报告名必须是不存在的新路径，命令拒绝覆盖。

### 教师页面

1. 使用教师账号登录。
2. 打开“教师后台 → 学生管理”。
3. 确认学生密码默认遮罩。
4. 点击一个可恢复学生的“显示”，确认提示后应显示密码。
5. 点击隐藏；再次显示后等待 30 秒，应自动隐藏。
6. 编辑学生，设置至少 8 位新密码。
7. 旧学生会话应失效，新密码应能登录。
8. 点击生成随机临时密码，记录后用该密码登录。

### 密钥轮换预演

```bash
python backend/manage.py rotate_student_password_keys
```

只应显示校验数量，不应显示密码、密文或 key。

## 8. 已完成的旧明文备份清理

用户于 2026-09-02 明确确认后，已删除以下两个含历史明文字段的精确目录：

1. `backend/migration_artifacts/stage2-20260901/`
   - 6 个文件；其中 `source.sqlite3` 和 `platform-data.json` 含明文字段。
2. `backend/migration_artifacts/stage3-20260901-pre/`
   - 2 个文件；其中 `source.sqlite3` 含明文字段。

已保留：

- `backend/migration_artifacts/stage3-20260901-final/`：最终加密 schema 备份与 v2 fixture。
- `backend/migration_artifacts/stage3-20260901/`：脱敏核验报告。

清理时已逐文件核对并删除，未使用宽泛递归路径；两个空目录也已移除。该操作不可通过项目恢复，文件系统快照或系统备份仍可能保留旧副本。

## 9. 已知限制

1. 教师可恢复密码是已确认的业务取舍；应用服务器与 key 同时失陷时仍可解密。
2. 前端 Token 仍保存在 localStorage，Cookie 化不属于本阶段。
3. 所有教师仍可管理全部学生，`managed_grade` 范围限制尚未启用。
4. 新注册/重置最低 8 位；两个历史 3 位密码继续有效，避免强制课堂账号立即改密。
5. 前端 Vitest、Vite 构建和 ESLint 均已通过；ESLint 的 48 条非阻断 React Hooks/Fast Refresh 警告可在后续架构整理时分批清理。
6. 两项 `template_code` 后端基线失败仍待阶段 9 处理。
7. requests 依赖版本警告仍存在，不影响本阶段测试结果。

## 10. 当前结论

数据库、后端 API、Token、权限、审计、SQLite/MySQL 数据迁移、密钥轮换和旧明文备份清理均已达到阶段 3 PRD/DEV 要求。阶段 3 正式完成。前端 Vitest、生产构建与全仓库 ESLint 已在 2026-09-02 补验通过。
