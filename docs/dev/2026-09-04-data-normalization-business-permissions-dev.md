# 阶段 6：数据规范与业务权限 DEV 技术设计

文档日期：2026-09-04
文档状态：已实施并通过自动化验证（2026-09-04）
对应 PRD：`docs/prd/2026-09-04-data-normalization-business-permissions-prd.md`
实施前提：本 DEV 确认后才修改数据、migration 和权限逻辑

## 1. 实施目标

本阶段将同时完成三件事：

1. 将年级、班级和学号规范化，并在 SQLite/MySQL 上建立可靠约束。
2. 将“是否登录/是否教师”升级为“角色 + 资源归属 + 管理年级”三层权限。
3. 统一核心简体中文术语、日期区域和业务状态显示。

不修改 Runner/Docker，不删除历史用户、成绩、提交或小测数据。

## 2. 当前数据预检查

本地 SQLite 当前有：

| 账号 | 角色 | 管理年级 | 超级管理员 | 实施影响 |
| --- | --- | --- | --- | --- |
| `alex` | teacher | 空 | 是 | 可保留跨年级管理，不会被锁出 |
| `t` | teacher | 空 | 否 | 权限收紧后受限管理列表为空，需配置 `managed_grade` |

现有学生和单元使用“七年级/八年级”标准文案，未发现需自动合并的用户。实施时仍必须重新运行预检查，不依赖本次抽查结果。

## 3. 年级与身份规范

### 3.1 后端权威定义

新增 `users/grade_levels.py`：

- `GRADE_CHOICES`：七年级、八年级、九年级、高一、高二、高三。
- `GRADE_ALIASES`：初一→七年级、初二→八年级、初三→九年级。
- `normalize_grade(value, allow_blank=False)`：去首尾空白、转换别名、拒绝未知值。
- `normalize_student_identifier(value)`：转字符串、去首尾空白、拒绝空值和控制字符，不转整数。

后端是年级规则的权威来源。前端将年级选项收口到 `frontend/src/constants/grades.js`，并用合同测试检查与后端返回值一致。

### 3.2 数据库约束

`CustomUser` 调整：

- `grade` 和 `managed_grade` 改用标准 choices。
- 普通教师 `managed_grade` 仍允许数据库为 NULL，但业务权限 fail closed，避免 migration 自动猜测授权。
- 学生必须有非空 `grade/class_num/student_number`。
- 教师的学生身份字段应为 NULL。
- 对 `(grade, class_num, student_number)` 建立普通唯一约束。教师三字段为 NULL，SQLite/MySQL 均允许多行 NULL；避免使用 MySQL 不创建的条件唯一索引。

应用层在写入前先规范化，并在并发冲突时捕获 `IntegrityError`，返回稳定 409，不向用户暴露数据库异常。

### 3.3 migration 顺序

1. 运行只读审计命令 `audit_stage6_data`，列出未知年级、空学生身份、规范化后重复身份和无管理范围教师。
2. 创建 SQLite 备份和 manifest；MySQL 演练前使用已有备份工具。
3. `users` 数据 migration 转换用户年级/管理年级，去除班级和学号首尾空白。
4. `info_tech` 数据 migration 转换 `Unit.grade`、`QuizSession.visible_grades` 和 `QuizSubmission.grade` 快照。
5. 若发现未知值或唯一冲突，migration 终止并输出摘要，不删除或合并数据。
6. 数据清洗通过后再添加字段 choices、检查约束和唯一约束。
7. SQLite 和 MySQL 8.0 分别从空库、现有备份演练 migration，核对行数和抽样关联。

## 4. 权限架构

### 4.1 统一权限类

`users/permissions.py` 保留统一定义：

- `IsStudent`：已认证、激活且 `role=student`。
- `IsTeacher`：已认证、激活且满足 `role=teacher` 或 `is_superuser=True`。
- `is_platform_admin(user)`：仅 `is_superuser=True`，不使用 `is_staff` 作为跨年级依据。

删除 `ai_courses.views` 里的重复 `IsTeacher`，`info_tech`、`ai_courses`、`users` 和 `chat` 统一引用。

### 4.2 统一作用域 helper

新增 `users/scopes.py`：

- `teacher_grade(user)`：超级管理员返回全局标记；普通教师返回标准 `managed_grade`；缺失时返回空范围。
- `scope_students(queryset, teacher)`：超级管理员不过滤，普通教师按 `grade=managed_grade`，缺失时 `queryset.none()`。
- `require_teacher_grade(teacher, requested_grade=None)`：写操作或显式跨年级请求不符合时抛出统一异常。
- `scope_info_content(queryset, teacher, grade_path)`：按单元、题目或小测的真实年级关联收紧。

对外错误码：

- `teacher_scope_missing`：普通教师未配置管理年级。
- `teacher_grade_forbidden`：请求了管理范围外的年级。
- `resource_not_found`：已缩小 queryset 中不存在的详情资源，对外使用 404 减少存在性泄露。

## 5. 接口权限矩阵

| 范围 | 学生 | 普通教师 | 无 `managed_grade` 教师 | 超级管理员 |
| --- | --- | --- | --- | --- |
| 学生本人 AI 题目/提交/成绩/任务 | 仅本人 | 拒绝 | 拒绝 | 拒绝学生作答操作 |
| 学生本人小测/结果/对话 | 仅本人 | 拒绝 | 拒绝 | 拒绝学生作答操作 |
| 学生列表/详情/编辑/删除 | 拒绝 | 仅管理年级 | 空/拒绝 | 全年级 |
| 学生密码查看/重置 | 拒绝 | 仅管理年级 | 拒绝并审计 | 全年级并审计 |
| AI 题库管理 | 拒绝 | 共享 | 共享 | 共享 |
| AI 学生统计/成绩 | 拒绝 | 仅管理年级 | 空 | 全年级 |
| 信息课单元/题目/小测 | 拒绝管理 | 仅管理年级 | 空/拒绝 | 全年级 |
| 信息课统计 | 拒绝 | 仅管理年级 | 空 | 全年级 |

说明：AI 题目列表/详情的学生阅读仍属学生功能，但不允许教师借该接口创建提交或任务。

## 6. 各业务模块改造

### 6.1 `users`

- 注册、登录、学生编辑和 Admin 共用规范化函数。
- `UserDetailView` 从 `scope_students()` 查找目标。
- 密码查看/重置服务在事务内重新加载教师和学生，然后再次校验年级作用域，防止请求中途权限变更。
- 跨年级密码请求记录 denied 审计，不解密密文。

### 6.2 `ai_courses` 与 `execution`

- 学生题目、成绩、统计、提交和运行入队统一使用 `IsStudent`。
- 任务详情和 active 查询继续附加 `user=request.user`。
- 教师仪表盘、学生列表和 AI 成绩按年级作用域聚合；请求中的 `grade` 只能继续缩小，不能扩大。
- AI 题库管理保持教师共享。

### 6.3 `info_tech`

- 学生端保持 `IsStudent` 和已有试卷所有者校验。
- 教师单元、题目、小测列表在 queryset 层按年级过滤。
- 详情、更新、删除、发布、关闭和重开先从已收紧 queryset 查找。
- 可见班级选项只来自已确认可管理的年级。
- 统计和学生成绩先限制年级，再应用班级/小测筛选。

### 6.4 `chat`

- 三个对话接口统一使用 `IsStudent`。
- 会话详情和删除始终使用 `(pk, user=request.user)` 查找。
- 本阶段不改 AI 系统提示词和第三方数据处理，留给阶段 7。

## 7. 历史年级快照决策

- 账号、密码、AI 提交和与当前学生关联的管理以学生当前 `grade` 为权限依据。
- 信息课历史统计以 `QuizSubmission.grade` 的提交时快照为年级归属，保证学生升级后旧学年报表仍正确。
- 当前学生详情不因历史快照被多个年级教师同时获得账号或密码权限。

## 8. 文案与前端

- 将核心页面的“老师”统一为“教师”，“载入”统一为“加载”，保留题目内容原文。
- 替换 `toLocaleString('zh-TW')` 为 `zh-CN`，时区依旧使用部署环境的 `Asia/Shanghai`。
- 为提交、小测和任务状态建立显示映射，不直接把 `wrong_answer/runtime_error/pending` 等状态码显示给学生。
- 权限收紧后的空列表和 403 提示使用可操作文案，例如“请先为教师账号设置管理年级”。

## 9. 测试设计

### 9.1 后端

- 规范化单元测试：标准值、别名、空白、未知值、“01”学号保留。
- migration 测试：别名转换、JSON 年级列表、历史快照、冲突中止。
- SQLite/MySQL 唯一约束与并发创建测试。
- 权限参数化测试：未登录、学生 A/B、普通教师同年级/跨年级、无范围教师、普通 `is_staff`、超级管理员。
- 列表、详情、写操作、统计和密码审计分别覆盖。
- 全量 Django 回归、system check 和 migration drift 检查。

### 9.2 前端

- 年级选项、教师空范围提示、中文状态、`zh-CN` 日期测试。
- 保留登录、学生管理、AI 编程题、小测和成绩页面回归。
- 全量 Vitest、ESLint 和 Vite 生产构建。

## 10. 手动验收设计

实施完成后可由用户通过浏览器验收。我会提供临时测试账号的创建/清理命令和逐项表格，至少包括：

1. 用七年级学生确认只能看到本班可见小测。
2. 尝试替换小测/任务 URL ID，确认看不到其他学生数据。
3. 用七年级普通教师确认列表、密码和成绩只包含七年级。
4. 尝试修改 URL/query 为八年级，确认返回空列表、403 或 404，而不是八年级数据。
5. 用超级管理员 `alex` 确认可跨年级管理。
6. 用“初一”兼容输入创建/登录，确认最终显示和存储为“七年级”。
7. 抽查登录、学生管理、小测、AI 提交和成绩页，确认简体术语和日期格式。

真实代码执行不在本阶段手动验收内，因为 Runner/Docker 仍暂缓。

## 11. 分步实施

### Step 0：基线、审计与备份（已完成，2026-09-04）

- 运行全量测试，生成年级/身份/教师范围审计报告。
- 备份 SQLite；核对 MySQL 演练环境。
- 明确 `t` 账号在权限收紧后的影响，不自动赋予年级。

### Step 1：规范化领域层（已完成，2026-09-04）

- 实现年级/身份规范化、共享验证器和前端常量。
- 收紧注册、登录、导入和编辑入口。

### Step 2：数据 migration 与约束（已完成，2026-09-04）

- 实现可回滚的数据转换和 SQLite/MySQL 约束。
- 空库、现有 SQLite 和 MySQL 各至少演练一次。

### Step 3：权限核心与账号数据（已完成，2026-09-04）

- 实现权限类、scope helper、学生详情和密码边界。
- 保留密码审计与 Token 失效规则。

### Step 4：课程与统计权限（已完成，2026-09-04）

- 收紧 `ai_courses`、`execution`、`info_tech` 和 `chat`。
- 完成端点权限矩阵与聚合泄露测试。

### Step 5：前端文案与错误体验（已完成，2026-09-04）

- 统一年级选项、简体中文、日期和状态映射。
- 增加教师缺少范围的明确提示。

### Step 6：全量验证与手动验收包（自动化部分已完成，2026-09-04）

- 运行 SQLite/MySQL、Django、Vitest、ESLint 和 Vite build。
- 生成完成报告、临时验收数据工具和可操作的手动清单。
- 清单见 `docs/deployment/stage-6-manual-acceptance.md`；浏览器端确认由用户执行。

## 12. 回滚和安全

- migration 前必须有带校验值的备份。
- 数据转换 migration 提供 reverse；别名逆转可回到之前快照，不猜测原别名。
- 唯一冲突在建约束前中止，不使用“保留第一条”等自动丢数据策略。
- 权限收紧可通过回滚代码恢复，不增加“临时全校权限”开关。
- 验收用临时账号不使用生产密码，验收后可恢复地禁用或删除。

## 13. DEV 确认项

确认本 DEV 即表示同意：

1. 按 Step 0–6 顺序实施，数据迁移前必须先审计和备份。
2. 普通教师无 `managed_grade` 时 fail closed，不自动猜测授权。
3. 本地 `alex` 作为超级管理员保留全年级管理；`t` 保持无范围，直到用户明确配置。
4. 信息课历史报表按提交年级快照归属；学生账号和密码按当前年级归属。
5. AI 题库保持教师共享，AI 学生数据和成绩按管理年级归属。
6. 阶段 6 完成后先交付手动验收清单，用户验收通过后再开始阶段 7。
