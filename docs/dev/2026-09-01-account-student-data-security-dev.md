# 阶段 3：账号与学生数据安全 DEV 技术设计

文档日期：2026-09-01
文档状态：已确认（2026-09-01）
对应 PRD：`docs/prd/2026-09-01-account-student-data-security-prd.md`
前置条件：阶段 3 PRD 已于 2026-09-01 确认

## 1. 实施目标

本阶段在保留“教师可快速查看单个学生当前密码”的前提下，完成以下技术闭环：

1. 用带密钥版本的 Fernet 认证加密密文替换 `plain_password` 数据库明文。
2. 统一学生注册、教师手工重置和随机临时密码的哈希/密文写入。
3. 将学生普通详情与密码揭示拆成独立接口，增加教师权限、数据库级限流、短时显示及安全响应头。
4. 记录不含密码、密文和 Token 的查看/重置审计。
5. 增加 12 小时默认 Token 有效期，并在注销、改密、重置、禁用后撤销旧 Token。
6. 在 SQLite 与 MySQL 8.0 上执行历史数据迁移、权限测试和回归验证。
7. 更新阶段 2 迁移/校验工具，使未来迁移包不再依赖明文字段。

## 2. 当前实现基线

### 2.1 数据与密码

- `backend/users/models.py` 的 `CustomUser.plain_password` 直接保存学生密码。
- 学生注册在 `RegisterView` 中手工调用 `set_password` 并写入 `plain_password`。
- 教师编辑学生时，`PUT /api/auth/<user_id>/` 同时更新哈希和 `plain_password`。
- 当前 SQLite 有 2 个非空可恢复学生密码；仅统计到长度均为 3，不读取或记录具体值。
- 阶段 2 已在进程内验证这 2 个明文与 Django 哈希匹配。

### 2.2 密码查看与权限

- `GET /api/auth/<user_id>/` 同时承担学生普通详情和密码返回。
- `StudentManagement.jsx` 点击眼睛图标后调用上述详情接口，并把 `plain_password` 放入组件状态。
- 学生列表本身使用 `UserSerializer`，当前不含 `plain_password`。
- 用户管理视图逐方法判断 `request.user.role != 'teacher'`，尚无 users app 统一教师权限类。

### 2.3 Token

- 登录使用 `Token.objects.get_or_create`，没有最长有效时间。
- 后端注销会删除 Token；前端 `logout()` 只清理 `localStorage`，没有调用后端注销接口。
- 教师重置学生密码不会删除该学生 Token。
- REST framework 默认同时启用 Token 和 Session authentication。

### 2.4 回归基线

- 阶段 2 后端全量测试：323 项中 321 项通过。
- 两项既有失败均为 `template_code` 序列化问题，不属于阶段 3。
- 阶段 2 SQLite/MySQL 相关测试结果一致，没有数据库特有新增失败。

## 3. 总体架构

```text
学生注册 / 教师重置
        │
        ▼
StudentPasswordService
  ├─ validate_password
  ├─ Django make/check password hash
  ├─ StudentPasswordCipher.encrypt
  ├─ 同一事务保存 hash + ciphertext + key_id + status
  └─ 重置时删除学生 Token

教师点击查看
        │
        ▼
POST /api/auth/students/{id}/password/reveal/
  ├─ ExpiringTokenAuthentication
  ├─ IsTeacher
  ├─ 锁定教师行 + 统计最近一分钟审计记录
  ├─ StudentPasswordCipher.decrypt
  ├─ check_password 二次一致性校验
  ├─ 写 PasswordSecurityAudit（不含密码）
  └─ no-store 响应 → 前端仅内存显示 30 秒
```

安全边界：

- Django `password` 哈希仍是登录验证的唯一依据。
- `encrypted_password` 只服务于教师受控查看，不参与 authenticate。
- 数据库只持有密文和 key ID；密钥只存在于进程环境。
- 普通学生列表、详情和统计不调用解密服务。
- 密码揭示和重置接口只接受有效 Token，不接受 SessionAuthentication 绕过 Token 有效期。

## 4. 加密设计

### 4.1 算法与依赖

新增 `cryptography>=44,<47`，使用 `cryptography.fernet.Fernet`：

- AES-CBC 加密、HMAC 完整性校验和随机 IV 由成熟库统一实现。
- 不自行实现加密算法、填充、MAC 或随机数生成。
- 密文被篡改、密钥不匹配或格式损坏时抛出安全异常，业务层只返回通用错误。

### 4.2 密钥配置

环境变量：

- `DJANGO_STUDENT_PASSWORD_KEYS`：逗号分隔的 `key_id:fernet_key`，例如 `stage3-v1:<generated-key>`。
- `DJANGO_STUDENT_PASSWORD_PRIMARY_KEY_ID`：新写入使用的 key ID。
- `DJANGO_TOKEN_TTL_HOURS`：Token 最长有效小时数，默认 `12`。
- `DJANGO_PASSWORD_REVEAL_LIMIT`：单教师每分钟查看上限，默认 `30`。
- `DJANGO_PASSWORD_REVEAL_SECONDS`：前端展示秒数，默认 `30`。

规则：

1. key ID 只允许字母、数字、点、下划线和短横线，最长 40；不得重复。
2. 每个 Fernet key 必须能解码为 32 字节；主 key ID 必须存在于 key map。
3. `DJANGO_STUDENT_PASSWORD_KEYS` 和 primary key ID 均不得写入日志或错误详情。
4. production 缺少、无效或使用示例占位值时，Django 拒绝启动。
5. development 缺少密钥时允许执行不涉及学生密码的只读命令，但 Django system check 给出明确错误；注册、迁移、查看和重置失败关闭。
6. test 使用测试进程环境提供的固定专用 Fernet key，不复用本地或生产密钥。

### 4.3 本地密钥文件

新增 `scripts/stage3_security_local.sh`：

- `init`：使用 `Fernet.generate_key()` 生成本地 key，仅写入 `backend/.env.security.local`，权限 `0600`，不打印 key。
- `status`：只显示文件是否存在、权限是否正确、配置是否能解析，不显示 key。
- `destroy`：只删除经绝对路径校验的本地安全环境文件；属于不可逆操作，文档要求用户主动执行。

`settings.py` 先尝试加载 `.env.security.local`，再加载普通 `.env`；两次均不覆盖显式 shell/部署环境变量，同时避免普通 `.env` 的占位值遮蔽已生成的本地安全 key。新增 `.env.security.example` 仅保留占位值；`.env.security.local` 加入 `.gitignore`。

### 4.4 加密服务

新增 `backend/users/security.py`：

- `parse_password_keys(environ)`：解析并验证配置，返回只读 key map。
- `StudentPasswordCipher.encrypt(plaintext)`：使用 primary key，返回 `(ciphertext, key_id)`。
- `StudentPasswordCipher.decrypt(ciphertext, key_id)`：按 key ID 解密，统一将 `InvalidToken`、未知 key 和格式异常转换为不含敏感数据的领域异常。
- `configuration_check()`：供 Django system check、脚本和测试复用。

不得在 `__repr__`、异常字符串或日志中包含 plaintext、ciphertext 或 key。

## 5. 数据模型与迁移

### 5.1 CustomUser 最终字段

删除：

- `plain_password`

新增：

- `encrypted_password = TextField(null=True, blank=True, editable=False)`
- `password_encryption_key_id = CharField(max_length=40, null=True, blank=True, editable=False)`
- `password_recovery_status = CharField(max_length=32, choices=..., default='not_available')`

状态值：

- `available`：密文存在且迁移/写入时验证通过。
- `missing_legacy`：历史明文为空，教师需要重置。
- `hash_mismatch`：历史明文与哈希不一致，拒绝迁移旧值。
- `not_applicable`：教师账号或不保存可恢复密码的账号。

密文运行时损坏不修改为新的业务状态；揭示返回不可恢复并记录 `decrypt_failed` 审计，避免一次瞬时密钥配置错误永久改写数据。

模型增加数据库约束：

- `available` 时 ciphertext 和 key ID 必须非空。
- 非学生角色不得为 `available`。

### 5.2 PasswordSecurityAudit

新增 `PasswordSecurityAudit` 模型：

- `event_type`：`reveal`、`manual_reset`、`generated_reset`。
- `actor_user_id`：教师 ID 快照，可为空（匿名拒绝）。
- `target_user_id`：目标 ID 快照，可为空。
- `outcome`：`success`、`denied`、`not_found`、`unavailable`、`rate_limited`、`error`。
- `reason_code`：受控短代码，不接受任意异常文本。
- `source_ip`：直接连接来源 `REMOTE_ADDR`，可为空。
- `created_at`：自动时间。

使用 ID 快照而不是级联外键，保证教师或学生被删除后仍保留审计事实。模型不设置任意 JSON/备注字段，减少误写密码的入口。索引：

- `(actor_user_id, event_type, created_at)`：限流查询。
- `(target_user_id, created_at)`：安全核查。
- `(outcome, created_at)`：失败统计。

Django admin 以只读方式注册；禁止新增、编辑和删除审计记录，列表不展示来源 IP 之外的额外请求内容。

### 5.3 migration 顺序

`users.0006_add_encrypted_password_and_audit`：

1. 添加密文、key ID、recovery status 和审计模型。
2. 在原子 `RunPython` 中读取历史模型。
3. 教师账号设为 `not_applicable`。
4. 学生 `plain_password` 为空时设为 `missing_legacy`。
5. 学生明文通过 `check_password` 时，使用 primary key 加密并设为 `available`。
6. 哈希不匹配时不加密旧值，设为 `hash_mismatch`。
7. 系统性密钥/加密错误使 migration 整体失败并回滚，不把错误逐条吞掉。

`users.0007_remove_plain_password`：

1. 先执行数据守卫：所有 `available` 记录必须有密文/key ID；教师不得为 `available`。
2. 删除 `plain_password` 数据库列。
3. 添加最终 CheckConstraint 和索引。

两个 migration 均提供安全反向策略：0007 可以恢复一个空的 nullable `plain_password` 列，但不会把密文批量解密回填；回滚后必须通过教师重置恢复可查看值，避免自动制造新的数据库明文副本。

### 5.4 迁移核验命令

新增 `python manage.py verify_stage3_password_migration --report <path>`：

- 统计学生总数、available/missing/mismatch 数量。
- 对 available 记录逐条在进程内解密并执行 `check_password`。
- 检查教师 encrypted password 数量为 0。
- 检查 audit 表结构和数据库约束。
- 生成权限 `0600` 的脱敏 JSON，只包含数量、状态和整体通过/失败。
- 不输出用户 ID、姓名、密码、哈希、密文、key ID 或 Token。

报告目录限制在 Git 忽略的 `backend/migration_artifacts/stage3-*` 下，不覆盖已有报告。

## 6. 领域服务

新增 `backend/users/services.py`。

### 6.1 StudentPasswordService.set_password

输入：student、plaintext、`validate=True`、`invalidate_tokens=True`。

行为：

1. 验证目标 `role=student`。
2. 新注册和重置密码使用 Django `validate_password`，沿用项目 MinimumLengthValidator，最低 8 位；最大 128 位。
3. 对历史迁移调用使用 `validate=False`，因此现有两个 3 位密码继续可以登录和迁移，不强迫立即修改。
4. 在 `transaction.atomic()` 内加密、调用 `set_password`、保存 hash/ciphertext/key ID/status。
5. 保存后用 `check_password` 与解密结果做进程内一致性校验，失败则回滚。
6. 重置流程删除该学生全部 Token；新注册尚无旧 Token时跳过。

所有业务写入入口只调用该服务。Django admin 对学生禁用内置密码修改入口，并提示使用教师学生管理页面，防止绕过密文同步；教师密码仍使用 Django admin 标准哈希流程。

### 6.2 reveal_password

输入：teacher、student ID、source IP。

在 `transaction.atomic()` 中：

1. `select_for_update()` 锁定教师用户行，保证多 worker 针对同一教师的限流一致。
2. 统计过去 60 秒该教师的 `reveal` 审计尝试；达到配置上限后写 `rate_limited` 并返回 429。
3. 只查询 `role=student` 目标；不存在写 `not_found`。
4. status、ciphertext 或 key ID 不完整时写 `unavailable`。
5. 解密后再次 `student.check_password(plaintext)`；不匹配时拒绝返回并写 `unavailable/hash_mismatch_runtime`。
6. 成功写 `success` 审计后返回 plaintext；审计写入失败则事务失败，接口不返回密码。

数据库限流避免使用 LocMemCache 导致 Gunicorn 多 worker 分别计数。SQLite 的 `select_for_update` 不提供真实行锁，但本地开发/测试保持功能一致；正式 MySQL 8.0 提供事务锁保证。

### 6.3 reset_password

- `mode=manual`：接收教师输入，执行统一验证与写入。
- `mode=generated`：服务端使用 `secrets` 生成至少 12 位、含字母和数字的临时密码，不使用容易混淆字符。
- 事务成功后记录 `manual_reset` 或 `generated_reset` 审计。
- 手工模式响应不重复返回密码；generated 模式只在本次 `no-store` 响应中返回一次。
- Token 删除与密码更新在同一事务中完成。

## 7. Token 认证设计

新增 `backend/users/authentication.py`：

`ExpiringTokenAuthentication(TokenAuthentication)`：

1. 调用父类验证 Token 与用户。
2. 若用户 `is_active=False`，删除 Token 并返回 401。
3. 计算 `timezone.now() - token.created`，超过 `TOKEN_TTL` 时删除 Token 并返回 401。
4. 异常信息统一为“登录已过期，请重新登录”，不返回 Token 或账号信息。

修改：

- REST framework 默认 Token authentication 替换为该类，保留 SessionAuthentication 供 Django admin/现有调试使用。
- 密码揭示与重置视图显式只使用 `ExpiringTokenAuthentication`。
- `LoginView` 检查现有 Token 是否过期；过期则删除并创建新 Token，未过期继续复用。
- `LogoutView` 删除当前 Token。
- 前端 `api.logout()` 先调用 `POST /auth/logout/`，无论成功或失败都在 `finally` 清除本地 Token/user。
- `AuthContext.logout()` 改为 async；导航前允许调用方等待，但即使现有按钮不等待也立即开始撤销请求。

## 8. API 设计

### 8.1 普通学生详情

保留：

- `GET /api/auth/<user_id>/`
- `PUT /api/auth/<user_id>/`
- `DELETE /api/auth/<user_id>/`

调整：

- GET 永远不返回 plaintext、ciphertext、key ID；只增加 `password_available: boolean`。
- PUT 只编辑姓名、年级、班级和学号；不再接受 `password`，收到时返回 400 并提示使用密码重置接口。
- 三种方法统一 `IsTeacher` 权限类，匿名 401、学生 403。

### 8.2 揭示密码

`POST /api/auth/students/<user_id>/password/reveal/`

成功 HTTP 200：

```json
{
  "password": "<仅本次明文>",
  "display_seconds": 30
}
```

响应头：

- `Cache-Control: no-store, private, max-age=0`
- `Pragma: no-cache`
- `X-Content-Type-Options: nosniff`（全局已有）

失败：401、403、404、429 或密码不可恢复 409。任何失败响应不包含敏感值。

### 8.3 重置密码

`POST /api/auth/students/<user_id>/password/reset/`

手工：

```json
{"mode": "manual", "password": "new-password"}
```

成功 HTTP 200：`{"message": "密码已重置，学生原登录已失效"}`。

随机：

```json
{"mode": "generated"}
```

成功 HTTP 200：

```json
{
  "message": "临时密码已生成，学生原登录已失效",
  "temporary_password": "<仅本次明文>",
  "display_seconds": 30
}
```

两种成功均使用 `no-store`，生成密码不会在后续接口再次作为“临时响应”返回，但教师可按正常揭示流程查看当前密码。

### 8.4 权限类

新增 `backend/users/permissions.py`：

- `IsTeacher`：先要求 authenticated，再以数据库 user.role 判断。
- 不信任请求体、localStorage 或路由中的 role。
- 对密码接口显式限定 Token authentication。

权限拒绝、throttle/业务拒绝通过受控审计辅助函数记录；审计函数只接受枚举 reason code，不接受原始异常或请求 body。

## 9. 前端设计

### 9.1 API 封装

在 `frontend/src/api/index.js` 新增：

- `getStudentDetail(id)`
- `revealStudentPassword(id)`
- `resetStudentPassword(id, password)`
- `generateStudentTemporaryPassword(id)`

敏感响应只返回给调用组件；API 层不写 localStorage、不 console.log、不缓存。

### 9.2 StudentManagement

调整 `StudentManagement.jsx`：

1. 学生列表 mock/接口不再包含 `plain_password`。
2. `revealedPasswords` 只保存当前组件内存中的单学生值和 timer ID/到期时间。
3. 点击眼睛 → `window.confirm` 安全提示 → POST reveal。
4. 成功后显示 30 秒，timer 到期清除；再次点击立即清除。
5. 同时只显示一个学生密码；查看新学生时先清除前一个密码及 timer。
6. `useEffect` cleanup 在卸载时清理 timer 和状态引用。
7. 编辑弹窗的密码区域拆为：手工重置表单、生成临时密码按钮；普通学生信息保存不携带 password。
8. 生成的临时密码使用同样的短时组件状态展示，30 秒后清除。
9. 401 沿用全局重新登录；403、404、409、429 显示明确中文错误。

避免把密码写进 DOM 属性、aria label、测试快照和错误提示；显示时仅作为必要文本节点存在。

### 9.3 退出登录

- Navbar、TeacherDashboard、StudentDashboard 等退出调用改为等待 `logout()` 后导航。
- 网络失败仍清理本地状态并导航；服务端 Token 最迟由 12 小时过期兜底。
- 测试验证确实发送带 Authorization 的 POST logout，而不只是清理 localStorage。

## 10. 关键文件清单

### 10.1 新增

- `backend/users/security.py`：密钥解析与 Fernet 加解密。
- `backend/users/services.py`：学生密码写入、揭示、重置与审计事务。
- `backend/users/authentication.py`：过期 Token 认证。
- `backend/users/permissions.py`：教师后端权限。
- `backend/users/checks.py`：密码密钥 system check。
- `backend/users/migrations/0006_add_encrypted_password_and_audit.py`
- `backend/users/migrations/0007_remove_plain_password.py`
- `backend/users/management/commands/verify_stage3_password_migration.py`
- `backend/users/tests_security.py`
- `backend/users/tests_migrations.py`
- `backend/.env.security.example`
- `scripts/stage3_security_local.sh`
- `docs/deployment/stage-3-account-security.md`
- `docs/reports/2026-09-01-stage-3-completion.md`（完成时）

### 10.2 修改

- `requirements.txt`：固定兼容范围的 cryptography。
- `.gitignore`：忽略本地密钥和 stage3 artifacts。
- `backend/school_platform/settings.py`：加载本地安全 env、加密/Token 配置和认证类。
- `backend/school_platform/environment.py`：数值、密钥及生产安全校验。
- `backend/.env.example`：非敏感配置说明。
- `backend/users/apps.py`：注册 system checks。
- `backend/users/models.py`：密文字段、状态、审计模型和约束。
- `backend/users/admin.py`：隐藏密文、审计只读、阻止学生 admin 改密不同步。
- `backend/users/serializers.py`：重置请求验证与安全输出。
- `backend/users/views.py`：登录/注销、详情、揭示和重置视图。
- `backend/users/urls.py`：新密码端点。
- `backend/users/tests.py`、`tests_model.py`：替换明文断言、增加旧 Token 与权限测试。
- `backend/platform_ops/migration_data.py`：加入审计模型并适配最终字段。
- `backend/platform_ops/management/commands/verify_platform_migration.py`：改为密文解密后哈希抽查。
- `backend/platform_ops/tests/test_migration_data.py`：移除明文 fixture。
- `frontend/src/api/index.js`、`index.test.js`：安全 API 和真实 logout。
- `frontend/src/contexts/AuthContext.jsx`、测试：异步 logout。
- `frontend/src/pages/teacher/StudentManagement.jsx`、测试：查看/重置/自动隐藏。
- 所有调用 `logout()` 的导航组件及测试。
- `docs/2026-09-01-alicloud-deployment-roadmap.md`：逐项同步状态。

实施前再次执行 `rg plain_password` 和 `rg set_password` 建立精确调用清单；实施后允许旧 migration 历史与明确迁移说明出现 `plain_password`，运行时代码、最终模型、API 和新 fixture 不得出现。

## 11. 实施步骤

### Step 1：安全配置、依赖与本地密钥工具 ✅ 已完成

- [x] 增加 cryptography 依赖并验证 Fernet 可用。
- [x] 实现密钥/数值配置解析与 production 校验。
- [x] 增加 `.env.security.example`、忽略规则和本地 init/status/destroy 脚本。
- [x] 增加配置/system check/脚本权限与不泄密测试。
- [x] 生成当前工作区专用本地 key，权限设为 0600，不输出内容。

验证：

```bash
bash -n scripts/stage3_security_local.sh
scripts/stage3_security_local.sh init
scripts/stage3_security_local.sh status
python manage.py check
```

### Step 2：加密服务、模型和安全迁移 ✅ 已完成

- [x] 实现 `StudentPasswordCipher` 与领域异常。
- [x] 增加 CustomUser 密文字段、恢复状态和 PasswordSecurityAudit。
- [x] 编写 0006 加密回填和 0007 删除明文字段迁移。
- [x] 增加 schema 约束、索引、admin 安全配置和迁移核验命令。
- [x] 使用 SQLite 备份演练 migration；报告不含账号和任何密码材料。

验证：

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py migrate
python manage.py verify_stage3_password_migration \
  --report migration_artifacts/stage3-20260901/sqlite-report.json
python manage.py test users.tests_security users.tests_migrations
```

### Step 3：密码服务、Token 生命周期与后端 API ✅ 已完成

- [x] 实现统一 set/reveal/reset/generated password 服务。
- [x] 实现 ExpiringTokenAuthentication 和登录 Token 更新。
- [x] 实现教师权限、普通详情收口、揭示/重置接口与 no-store。
- [x] 密码重置事务内撤销旧 Token。
- [x] 增加成功、异常、权限、限流和审计测试。

重点测试：

- 哈希/密文一致及事务回滚。
- 匿名 401、学生 403、教师成功、教师目标 404/非学生拒绝。
- 普通详情/list/serializer 不含敏感字段。
- 31 次一分钟内请求的第 31 次返回 429。
- 解密损坏和 key 缺失失败关闭且审计无敏感内容。
- 手工/随机重置后旧密码失败、旧 Token 401、新密码成功。
- Token 过期边界前可用、边界后 401、重新登录签发新 Token。

### Step 4：教师前端查看、重置和真实注销 ✅ 已完成

- [x] 增加密码 API 封装。
- [x] 改造 StudentManagement 默认遮罩、确认、揭示、立即隐藏和 30 秒自动隐藏。
- [x] 改造手工重置与随机临时密码交互。
- [x] 页面卸载、切换学生和退出时清除明文/timer。
- [x] 前端 logout 调用后端并在 finally 清理本地状态。
- [x] 增加 Vitest 计时器、失败分支、无预取和注销请求测试。

验证：

```bash
cd frontend
npm test -- src/api/index.test.js \
  src/contexts/AuthContext.test.jsx \
  src/pages/teacher/StudentManagement.test.jsx \
  src/pages/teacher/TeacherDashboard.test.jsx
npm run build
npm run lint
```

若全仓库 lint 存在阶段前遗留问题，需分别报告“阶段 3 改动文件 lint”和“全仓库 lint”，不得把前者通过表述为全仓库通过。

### Step 5：阶段 2 工具适配与 MySQL 演练 ✅ 已完成

- [x] 更新导出模型顺序和 MySQL 密码一致性校验。
- [x] 新 fixture 不包含 `plain_password`，密文只保存在受限 artifact 中且不输出。
- [x] 启动隔离 MySQL 8.0，对阶段 2 迁移后的业务库执行 0006/0007。
- [x] 对全新空 MySQL 从零执行全部 migration。
- [x] 完成 MySQL 迁移核验、约束、API 和账号安全测试。
- [x] 停止本地 MySQL，确认 3308 不监听。

验证命令沿用 `scripts/stage2_mysql_local.sh`，数据库密码和学生密码均不打印。至少验证：

```bash
scripts/stage2_mysql_local.sh start
scripts/stage2_mysql_local.sh status
# 加载被忽略的 MySQL/security 环境后：
python manage.py migrate
python manage.py check --database default
python manage.py verify_stage3_password_migration --report <stage3-mysql-report>
python manage.py test users platform_ops.tests
scripts/stage2_mysql_local.sh stop
```

### Step 6：全量回归、敏感扫描与文档收尾 ✅ 已完成

- [x] SQLite 运行全量后端测试并与 321/323 基线比较。
- [x] MySQL 运行阶段 3/相关集成测试；风险允许时运行全量回归。
- [x] 前端运行阶段 3 定向测试、构建和 lint。
- [x] 实际调用登录、详情、揭示、重置、旧 Token、注销和过期 Token 链路。
- [x] 扫描可跟踪文件、日志和报告，确认无本地 key、测试外真实密码或 Token。
- [x] 完成部署/密钥轮换/故障恢复文档和阶段完成报告。
- [x] 精确列出阶段 2 旧敏感 artifacts，征得用户确认后再删除并生成新产物。
- [x] DEV 各 Step 标记完成，路线图阶段 3 勾选完成。

## 12. 测试矩阵

| 层级 | SQLite | MySQL 8.0 | 重点 |
|---|---:|---:|---|
| 配置/密钥解析 | 必测 | 配置复用 | 缺失、格式、primary、占位、无泄密 |
| Fernet 服务 | 必测 | 与 DB 无关 | round trip、错误 key、篡改、异常脱敏 |
| migration | 必测 | 必测 | 匹配、空、mismatch、教师、约束、最终无列 |
| 密码写入 | 必测 | 必测 | hash/cipher 原子一致、验证、Token 删除 |
| 揭示/重置 API | 必测 | 必测 | 401/403/404/409/429/200、no-store、审计 |
| Token 认证 | 必测 | 必测 | 未过期、过期、注销、重置、禁用 |
| 平台迁移工具 | 必测 | 必测 | 新模型摘要、密文哈希抽查、脱敏报告 |
| React 页面 | Vitest | 后端联调 | 遮罩、确认、30 秒、清理、错误、重置 |
| 全量回归 | 323 基线 | 风险允许时全量 | 阶段 3 不新增失败 |

测试中使用明显的测试密码和测试 key；静态泄密扫描要区分测试 fixture 与真实本地凭据，但任何日志/报告都不得包含测试明文回显。

## 13. 实际验收流程

### 13.1 数据与配置

1. 备份当前 SQLite，记录哈希与权限，不打印内容。
2. 初始化本地安全 key。
3. 在备份副本或测试库先跑 0006/0007，核对 2/2 历史可恢复密码迁移成功。
4. 再对当前开发 SQLite 执行 migration。
5. 查询最终 schema，确认 `plain_password` 列不存在，encrypted 字段非明文。

### 13.2 教师/学生链路

1. 使用现有教师 Token 或登录账号进入学生管理。
2. 验证学生列表请求不含密码字段。
3. 点击单学生眼睛图标，确认密码可见且 30 秒隐藏。
4. 使用该密码完成学生登录。
5. 保存旧学生 Token，教师手工重置密码。
6. 验证旧密码登录 401、旧 Token 请求 401、新密码登录 200。
7. 生成随机临时密码并验证同一链路。
8. 学生 Token 请求 reveal/reset 均为 403，匿名为 401。

实际验证只记录 HTTP 状态和通过/失败，不把密码或 Token 写到终端报告。

### 13.3 审计

核对成功查看、拒绝、不可恢复、限流、手工重置和随机重置事件数量。确认审计模型无 password/ciphertext/token/request_body 字段，记录内容中也不出现这些值。

## 14. 敏感数据扫描

完成前执行：

1. `git ls-files --cached --others --exclude-standard` 获取所有可提交文件。
2. 从本地 env 仅在进程内读取真实 key 和数据库密码，扫描命中数量；输出只显示数量和文件路径（期望 0），不打印秘密。
3. 使用专用测试哨兵密码运行接口后，扫描日志、报告和响应快照，确保只在专用成功响应的内存断言中出现。
4. `rg plain_password` 分类检查：只允许旧 migration、PRD/DEV/完成报告等历史说明，禁止运行时模型、view、serializer、前端与新 fixture 使用。
5. 检查 `.env.security.local`、stage2/stage3 artifacts 均被 Git 忽略且权限正确。

## 15. 回滚与故障处理

### 15.1 migration 前

- 使用 SQLite 在线备份 API 创建权限 0600 的一致性备份。
- MySQL 使用阶段 2 导出与摘要流程保留迁移前状态。
- 备份含历史明文，存放在忽略目录且只保留到阶段 3验证完成。

### 15.2 0006 失败

- 原子 migration 回滚，新字段/回填不被标记成功。
- 修复 key 配置后重新执行，不修改旧明文。

### 15.3 0007 或应用失败

- 若尚未删除明文字段，继续使用旧版本应用但关闭密码揭示相关新路由。
- 若已删除明文字段，应用可临时降级为“教师只能重置、不能查看”，不能恢复普通详情直接返回明文。
- 从加密备份恢复需再次核对目标，禁止把旧含明文备份当作日常运行库长期回退。

### 15.4 key 丢失或错误

- 学生登录仍依赖 Django hash，可以继续登录。
- 密码揭示返回 409/安全错误，教师可在 key 恢复后查看。
- 不知道旧 key 时不能解密；教师重置学生密码后用当前 primary key 生成新密文。
- 密钥轮换时保留旧 key 只用于读取，primary 指向新 key；后续管理命令逐条重加密后再移除旧 key。

## 16. 已知取舍

1. 可恢复密码本身仍高于纯哈希方案风险，这是用户确认的教学便利取舍；本阶段通过密钥分离、按需解密、限流、自动隐藏和审计降低风险。
2. 前端 Token 仍在 localStorage，仍需依赖 XSS 防护；Cookie 化不纳入本阶段。
3. SQLite 无真实行级锁，多进程严格限流以正式 MySQL 行为为准；SQLite 只用于单进程开发和测试。
4. 当前保持所有教师可管理所有学生；`managed_grade` 授权边界另行设计。
5. 历史 3 位密码可继续登录并被迁移；新注册或重置需至少 8 位，避免在本阶段强制全体学生立即改密。
6. 随机临时密码本阶段不强制首次登录修改，符合已确认 PRD 的课堂效率要求。

## 17. DEV 确认项

确认本 DEV 后，将按 Step 1–6 实施，并允许以下本地变更：

1. 安装/记录 `cryptography` Python 依赖（当前环境已有 44.0.1，仍写入 requirements 以保证可重复安装）。
2. 生成一个仅用于当前项目的随机 Fernet key，写入被 Git 忽略且权限 0600 的 `backend/.env.security.local`，不在终端显示内容。
3. 创建并执行 users 0006/0007 migration，最终删除当前数据库的 `plain_password` 列。
4. 临时启动阶段 2 隔离 MySQL 8.0，完成 migration 和相关测试后停止。
5. 产生被 Git 忽略、权限受限的 stage3 脱敏验证报告与迁移前备份。
6. 阶段 2 旧敏感 artifacts 暂不自动删除；完成验证后列出精确文件，再单独征得用户确认。

确认 DEV 后才开始修改业务代码、生成密钥或执行数据库 migration。
