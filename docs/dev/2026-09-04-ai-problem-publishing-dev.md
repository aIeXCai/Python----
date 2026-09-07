# AI 题目发布管理 DEV 技术设计

文档日期：2026-09-04
文档状态：用户已确认（2026-09-04）
对应 PRD：`docs/prd/2026-09-04-ai-problem-publishing-prd.md`
前置条件：AI 题目发布管理 PRD 已于 2026-09-04 确认
实施状态：开发与自动化验证已完成（2026-09-04），等待用户手工验收

## 1. 实施目标与技术不变量

本阶段继续以一条 `Problem` 代表一道 AI 编程小测，不新增 `AIQuiz`。实现后必须满足：

1. 题目内容、学生提交、执行任务和发布范围保持稳定外键关系。
2. 题目是否对学生可访问只能由服务端发布规则决定。
3. 年级和班级必须成对保存，不能使用两个数组生成笛卡尔积。
4. 普通教师的范围写操作只影响其 `managed_grade`，不能覆盖其他年级。
5. 只有 `is_superuser=True` 可以设置全校规则、全局暂停、归档和恢复。
6. `is_staff`、请求参数或前端隐藏控件不能扩大权限。
7. 修改、隐藏、范围调整和归档不删除 `Submission` 或 `ExecutionTask`。
8. 隐藏后禁止创建新评分任务；已创建任务继续按快照完成并允许本人轮询结果。
9. 现有题目迁移后保持全校可见，升级前后题目、提交和任务行数一致。
10. AI 成绩继续取每名学生每题历史最高分，不在本阶段改变统计口径。

## 2. 当前实现基线

### 2.1 保留

- `Problem`、`Submission` 以及 `ExecutionTask.problem` 的现有关联。
- `problem_id` 作为学生 URL、磁盘目录和执行快照中的稳定业务标识。
- `Problem.sync_from_disk()` 读取 `problems/ai/problem*` 的兼容流程。
- 教师题库列表、详情、磁盘同步和成绩矩阵的现有入口。
- 学生题目列表、详情、代码运行、正式提交、成绩和统计页面。
- Runner 使用任务创建时 `test_snapshot`，不在执行时重新读取题目文件。

### 2.2 必须替换或补齐

- 学生列表与详情当前查询所有课程题目，没有发布范围。
- `SubmissionView` 按 `problem_id` 直接查询，修改请求可提交任意存在题目。
- 学生成绩、统计和历史未统一使用可见题目集合。
- 教师只能查看和物理删除，不能编辑题目或维护范围。
- 当前 DELETE 会因 `Submission.problem=CASCADE` 删除历史成绩。
- 多教师共用一个题库，缺少内容所有者、范围版本和管理审计。

## 3. 总体架构

```text
Problem（共享题目内容）
   │
   ├── ProblemAudience（全校 / 全年级 / 精确班级发布规则）
   ├── Submission（历史提交，保留）
   ├── ExecutionTask（运行快照，保留）
   └── ProblemManagementAudit（管理操作审计）

学生请求
   └── visible_problems_for_student(user)
          ├── 未归档
          ├── 未被 Alex 全局暂停
          └── 命中一条生效发布规则

普通教师范围更新
   └── select_for_update(Problem)
          ├── 校验 expected_version
          ├── 仅更新 managed_grade 规则
          ├── management_version + 1
          └── 写审计
```

代码分层：

- Model：保存题目管理字段、规范发布规则和审计记录。
- Query scope：只负责构造学生可见题目 queryset。
- Domain service：承担内容编辑、范围更新、暂停、归档、恢复和同步事务。
- Serializer：按角色验证请求白名单，不在 View 中拼权限判断。
- View：认证、调用服务、输出统一 HTTP 状态。
- React：显示范围摘要、编辑弹窗和分层范围选择，不自行决定最终权限。

## 4. 数据模型

### 4.1 `Problem` 新增字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `created_by` | `ForeignKey(CustomUser, SET_NULL, null=True)` | `NULL` | 内容所有者；兼容历史磁盘题 |
| `publishing_suspended` | `BooleanField` | `False` | Alex 全局暂停开关 |
| `management_version` | `PositiveIntegerField` | `1` | 内容/范围乐观并发版本 |
| `archived_at` | `DateTimeField(null=True, db_index=True)` | `NULL` | 软归档时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 当前时间 | 最近管理变更时间 |

同时将 `Submission.problem` 从 `CASCADE` 改为 `PROTECT`。正常业务不物理删除 `Problem`；该约束作为误操作的最后防线。`ExecutionTask.problem` 继续使用现有 `SET_NULL`，避免影响任务清理策略。

`problem_id` 继续唯一且创建后 API 只读。

### 4.2 `ProblemAudience`

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `problem` | `ForeignKey(Problem, CASCADE, related_name="audience_rules")` | 规则所属题目；仅题目被数据库级物理删除时级联 |
| `scope_type` | `CharField` | `all_school / grade_all / class` |
| `grade` | `CharField(max_length=10, blank=True, default="")` | 标准年级；全校规则为空 |
| `class_num` | `CharField(max_length=20, blank=True, default="")` | 精确班级；其他规则为空 |
| `is_active` | `BooleanField(default=True)` | 当前是否生效；停用不删除选择 |
| `configured_by` | `ForeignKey(CustomUser, SET_NULL, null=True)` | 最近配置人 |
| `created_at` | `DateTimeField(auto_now_add=True)` | 创建时间 |
| `updated_at` | `DateTimeField(auto_now=True)` | 更新时间 |

不使用 `NULL grade/class_num`，因为 MySQL 唯一索引允许多行 `NULL`，会导致全校或全年级规则重复。统一使用空字符串后增加：

1. `UniqueConstraint(problem, scope_type, grade, class_num)`。
2. Check：`all_school` 必须 `grade='' AND class_num=''`。
3. Check：`grade_all` 必须 `grade in CANONICAL_GRADES AND class_num=''`。
4. Check：`class` 必须 `grade in CANONICAL_GRADES AND class_num<>''`。
5. 索引 `(problem, is_active, scope_type)`。
6. 索引 `(grade, class_num, is_active)`。

Serializer 和 Model `clean()` 复用 `users.grade_levels.normalize_grade()` 及学生标识规范；数据库 Check 作为并发和非 API 写入的最终防线。约束语法需同时通过 SQLite 和 MySQL 8.0。

### 4.3 `ProblemManagementAudit`

字段：

- `event_type`：`content_edit / scope_update / global_suspend / global_resume / archive / restore / disk_sync`。
- `outcome`：`success / denied / conflict / failed`。
- `actor_user_id`：整数快照，不使用外键，删除账号后仍保留审计。
- `problem_id`：业务标识快照。
- `reason_code`：拒绝或失败原因。
- `before_summary`、`after_summary`：JSON 摘要。
- `source_ip`、`created_at`。

摘要只包含标题摘要/哈希、难度、状态、版本和范围，不保存完整模板代码、测试点或学生代码。Django Admin 只读，禁止增加、修改和删除。

## 5. 发布规则语义

### 5.1 学生匹配

在 `ai_courses/problem_scopes.py` 提供：

```python
visible_problems_for_student(queryset, user)
get_visible_problem_or_404(user, problem_id, course='ai')
student_can_access_problem(user, problem)
```

可见 queryset 必须同时满足：

```text
course = ai
archived_at IS NULL
publishing_suspended = false
至少命中一条 is_active=true 的规则：
  all_school
  OR grade_all 且 grade = student.grade
  OR class 且 grade = student.grade 且 class_num = student.class_num
```

ORM 使用 `Q()` 与 `.distinct()`，避免一题多规则产生重复行。调用前验证学生角色、标准年级和非空班级；身份异常默认返回空 queryset。

### 5.2 规则优先级

- `archived_at` 和 `publishing_suspended` 优先于全部规则。
- 生效的 `all_school` 规则覆盖范围最广，但不删除具体规则。
- 取消全校只将全校规则设为 inactive，原有全年级和班级规则重新决定范围。
- `grade_all` 生效时，同年级精确班级规则可保留但不影响结果。
- 停用某年级时，将该年级所有规则设为 inactive，不处理其他年级。
- 没有命中规则即不可见，不设置隐式默认范围。

### 5.3 教师看到的状态

- Alex：计算全局状态 `全校可见 / 部分可见 / 不可见 / 已暂停 / 已归档`。
- 普通教师：计算其管理年级状态 `全年级可见 / 部分班级 / 本年级不可见`。
- 若全校规则生效，普通教师显示“全校规则已生效（由超级管理员管理）”，不可用本年级按钮覆盖。

## 6. 领域服务与事务

新增 `ai_courses/problem_management.py`。

### 6.1 `edit_problem_content(actor, problem_id, payload, expected_version)`

事务步骤：

1. `select_for_update()` 查询未归档 Problem。
2. Alex 可编辑全部；普通教师仅可编辑 `created_by_id == actor.id` 的题目。
3. 校验 `expected_version == management_version`，不一致抛出 409 `version_conflict`。
4. 白名单更新 `title/description/difficulty/template_code`，禁止修改 `problem_id/course/created_by`。
5. `management_version += 1`，保存并记录内容哈希摘要审计。

### 6.2 `update_problem_audience(actor, problem_id, payload, expected_version)`

共同步骤：锁题、校验版本、规范化范围、原子更新规则、版本加一、写审计。

普通教师请求结构：

```json
{
  "expected_version": 3,
  "visible": true,
  "all_classes": false,
  "classes": ["1", "3"]
}
```

- 服务端从 `actor.managed_grade` 得到年级，不接受客户端年级。
- `visible=false`：仅停用该年级全部规则，保留记录。
- `visible=true, all_classes=true`：启用 `grade_all`，停用本年级精确班级规则。
- `visible=true, all_classes=false`：至少一个班级；启用对应 `class` 规则，停用该年级其他规则。
- 全校规则生效时普通教师更新返回 409 `all_school_managed_by_admin`，避免显示与实际不一致。

Alex 请求结构：

```json
{
  "expected_version": 3,
  "publishing_suspended": false,
  "all_school": false,
  "scopes": [
    {"grade": "七年级", "all_classes": false, "classes": ["1", "3"]},
    {"grade": "八年级", "all_classes": true, "classes": []}
  ]
}
```

- `all_school=true`：启用全校规则；保留但不启用/删除指定规则的选择状态由现有记录保存。
- `all_school=false`：停用全校规则，按请求启用指定范围，未出现年级的现有规则停用但不删除。
- `publishing_suspended=true`：只修改全局暂停状态，不清空任何规则。
- 解除暂停时如果没有任何生效规则，返回 400 `publication_scope_required`。

### 6.3 `archive_problem(actor, problem_id, expected_version)`

- 仅 Alex 可调用。
- 锁题并校验版本；设置 `archived_at`，停用学生新访问，但不删除受众、提交或任务。
- 已排队/运行任务不取消，继续使用任务快照。
- 重复归档幂等返回当前状态。

### 6.4 `restore_problem(actor, problem_id, expected_version)`

- 仅 Alex 可调用。
- 清空 `archived_at`，同时设置 `publishing_suspended=True`。
- 保留范围规则，但必须由 Alex 明确解除暂停后学生才能访问。

### 6.5 `sync_from_disk(actor)`

- `Problem.sync_from_disk()` 改为接收 `actor`，并把文件扫描与数据库写入交给服务函数。
- 新建题目：`created_by=actor`、`publishing_suspended=False`、没有生效范围，默认学生不可见。
- 更新题目：只更新磁盘负责的 `title/description/difficulty/template_code`，不覆盖所有者、暂停、归档和范围。
- 每题使用事务或 savepoint；单题失败不留下半条记录，并在响应中列出失败原因。
- 版本与内容发生实际变化时才递增，避免无变化同步造成无意义冲突。

## 7. API 设计

保留前缀 `/api/ai/`。

### 7.1 学生接口

| 方法 | 路径 | 改造 |
| --- | --- | --- |
| GET | `/problems/?course=ai` | 使用学生可见 queryset |
| GET | `/problems/{problem_id}/` | 从可见 queryset 查详情 |
| POST | `/submissions/` | 创建任务前再次从可见 queryset 查题 |
| GET | `/scores/?course=ai` | 只统计当前可见题目 |
| GET | `/stats/?course=ai` | 总数、完成数、平均分和排名使用同一可见集合 |
| GET | `/submissions/history/` | 常规列表只返回当前可见题目的历史；数据库记录不删除 |

`run_code/` 是不关联题目的通用代码运行接口，不做题目范围校验。正式评分 `submissions/` 必须校验。

执行任务详情和 active 查询继续以 `task.user=request.user` 为主权限，不重新套当前题目范围；这样隐藏前创建的任务仍可完成和轮询。任务响应不得返回题目描述和测试点原文。创建任何新评分任务时必须已经通过题目范围校验。

### 7.2 教师接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/admin/problems/` | 管理列表，返回角色对应范围摘要和版本 |
| POST | `/admin/problems/` | 兼容现有磁盘同步，传入 actor |
| GET | `/admin/problems/{problem_id}/` | 管理详情，不受学生可见性过滤 |
| PATCH | `/admin/problems/{problem_id}/` | 编辑内容，执行所有权与版本校验 |
| DELETE | `/admin/problems/{problem_id}/` | 改为 Alex 软归档，要求 expected_version |
| GET | `/admin/problems/{problem_id}/publication/` | 获取完整/本年级发布配置 |
| PATCH | `/admin/problems/{problem_id}/publication/` | 按角色选择 serializer 更新规则 |
| POST | `/admin/problems/{problem_id}/restore/` | Alex 恢复归档题 |
| GET | `/admin/problem-classes/?grade=七年级` | 返回授权年级的真实班级列表 |

响应统一包含 `management_version`。版本冲突返回 409，并返回最新版本号但不回显无权范围。权限不足 403，不存在或查询集外资源 404，参数错误 400。

### 7.3 序列化器

新增：

- `AdminProblemListSerializer`
- `AdminProblemDetailSerializer`
- `ProblemContentUpdateSerializer`
- `TeacherProblemAudienceUpdateSerializer`
- `AdminProblemAudienceUpdateSerializer`
- `ProblemAudienceSerializer`

学生 `ProblemListSerializer` 不返回发布规则、所有者、暂停、归档或版本字段。学生详情继续维持本阶段前既有测试点展示行为；测试点公开/隐藏分级属于后续题库入库设计，不在本次范围扩张。

## 8. 教师前端设计

### 8.1 组件拆分

从当前单文件 `aiAdmin.jsx` 拆出：

- `ProblemCard`：状态、范围摘要和操作。
- `ProblemEditModal`：标题、描述、难度、模板代码。
- `ProblemAudienceModal`：全校、全年级和精确班级选择。
- `ProblemArchivePanel`：Alex 查看和恢复归档题。
- `problemAdminApi.js`：教师题目管理请求。

拆分只服务可维护性，不重做页面视觉风格。

### 8.2 范围选择交互

- Alex 顶部显示“一键全选全校”。
- 指定范围按年级折叠或下拉展示；每个年级提供“全年级”和真实班级多选。
- 普通教师只显示自己的管理年级，不渲染其他年级与全校选项。
- 选择全年级时保留之前具体班级选择在界面草稿中，但提交为 `grade_all`。
- 范围摘要使用统一格式：`全校可见`、`七年级全年级`、`七年级1、3班；八年级2班`。
- 保存期间禁用重复点击；409 时提示“配置已被其他教师更新”，重新载入最新值，不自动覆盖。

### 8.3 操作与文案

- “删除”改为“归档”，弹窗明确说明历史提交和成绩会保留。
- 不可见题目不从教师列表消失，用状态徽标展示。
- 新同步题显示“尚未发布”，引导先设置范围。
- 无管理年级教师显示现有阶段 6 提示，范围按钮禁用。
- 普通教师对非本人题目的内容编辑按钮禁用并说明“共享题目内容由创建教师或超级管理员维护”，但仍可配置本年级范围。

## 9. 成绩、统计与历史

- 学生 `scores/stats` 只对当前可见题目计算，避免隐藏题目数量和名称泄露。
- 教师成绩矩阵默认显示所有未归档 AI 题，包括不可见题，以便回顾历史。
- 教师学生集合继续使用 `scope_students()`，普通教师只看到管理年级，Alex 可跨年级。
- 已归档题默认不作为成绩矩阵列；提供归档筛选后可查看历史，不删除数据。
- 每学生每题继续使用 `Max(score)`；空成绩保持空，不改成最新一次。
- 题目重新开放后原有历史成绩重新显示，学生可继续提交并更新最高分。

## 10. 数据迁移

新增 `ai_courses/migrations/0005_problem_publication.py`，依赖现有 `0004_submission_execution_task`。

迁移顺序：

1. 给 `Problem` 增加 nullable/有默认值的新字段。
2. 创建 `ProblemAudience` 和索引、约束。
3. 创建 `ProblemManagementAudit`。
4. `RunPython` 为每条现有 Problem 创建一条 active `all_school` 规则。
5. 将 `Submission.problem` 改为 `PROTECT`。
6. 核对行数和孤儿关联后结束。

数据迁移必须幂等处理已存在规则。反向迁移只删除由迁移创建的发布规则和新增表/字段，不删除 Problem、Submission 或 ExecutionTask。回滚后旧应用恢复“所有题默认可见”行为。

迁移前通过管理命令记录：

- Problem 总数及按 course 数量。
- Submission 总数和按 Problem 数量。
- ExecutionTask 总数、有关联 Problem 数和状态分布。
- 缺失磁盘目录或没有测试点的题目清单。

## 11. 测试设计

### 11.1 Model 与 migration

- 三种 scope shape 的合法/非法组合。
- 空字符串唯一约束在 SQLite/MySQL 下均拒绝重复。
- 非标准年级和空精确班级拒绝。
- `Submission.problem=PROTECT` 防止物理误删。
- 0004 → 0005 后每个旧题恰好一条 active 全校规则。
- 迁移前后 Problem、Submission 和 ExecutionTask 关联数一致。

### 11.2 权限与服务

- 七年级1班、七年级2班、八年级1班、八年级2班精确匹配。
- `七年级1班 + 八年级2班` 不产生交叉授权。
- 全年级自动覆盖后来新增班级；全校自动覆盖后来新增年级班级。
- 七年级教师不能修改八年级规则，伪造 payload 整体回滚。
- 普通 `is_staff` 不能全校发布、暂停、归档或编辑他人题目。
- 无管理年级教师 fail closed。
- 普通教师内容所有权、Alex 全量管理。
- expected_version 冲突返回 409，旧请求不覆盖新配置。
- 全校规则启用/停用后精确规则仍保留。
- 归档、恢复、暂停不会删除提交或任务。

### 11.3 学生 API

- 列表、详情、正式提交使用同一范围。
- 修改 URL 和 `problem_id` 不能访问无权题目。
- 隐藏后不能新建任务；隐藏前已建任务仍可由本人查询至完成。
- 学生成绩、统计和历史不泄露当前隐藏题目。
- 学生 A 不能读取学生 B 的任务或提交。
- 一般 `run_code/` 不因题目隐藏而受影响。

### 11.4 教师前端

- Alex 一键全校、取消全校和全局暂停。
- 普通教师只显示管理年级。
- 全年级/具体班级互切、多选和摘要。
- 编辑成功、验证错误、403、409 和网络失败。
- 新同步题“尚未发布”。
- 归档确认、历史保留说明和恢复后暂停状态。

### 11.5 完整回归

- Django SQLite 全量。
- MySQL 8.0 全量及发布规则并发定向测试。
- `makemigrations --check --dry-run`、`check`、`compileall`。
- Vitest 全量、ESLint、Vite production build。
- 阶段 3 密码、阶段 4 信息小测、阶段 5 任务协议和阶段 6 权限测试继续通过。

## 12. 实施顺序

1. 备份 SQLite，记录哈希和关键表行数。
2. 编写模型、0005 migration、Django Admin 只读审计和模型/迁移测试。
3. 实现学生可见 queryset 与领域服务。
4. 先收紧学生列表、详情、提交、成绩、统计和历史接口。
5. 实现教师内容编辑、范围、暂停、归档、恢复和班级选项接口。
6. 改造磁盘同步，验证不覆盖发布配置。
7. 拆分并改造教师前端，补齐前端 API 和测试。
8. 执行 SQLite 全量和迁移数据审计。
9. 执行 MySQL migration、定向并发和全量回归。
10. 准备手工验收账号、范围组合和验收清单。

每步失败先修复，不跳过数据核对。Docker Runner 未安装不阻塞模型、权限、API 和前端开发；涉及真实执行的端到端用现有安全关闭状态与任务服务测试验证，Docker 沙箱仍属于阶段 5 剩余工作。

## 13. 回滚方案

- 前端可先回滚，不影响新表；旧教师页面不会写发布范围。
- 后端回滚到旧版本前，导出所有 ProblemAudience 和管理审计。
- 回滚 migration 会恢复 `Submission.problem=CASCADE` 的模型状态，因此只用于受控回滚，不执行任何题目物理删除。
- 若学生过滤上线异常，可临时仅回滚应用并依赖旧题全部已有全校规则，不直接删除范围数据。
- 数据迁移发生异常时从一致性 SQLite/MySQL 备份恢复，不人工猜测或补写发布范围。

## 14. DEV 确认项

确认本 DEV 即表示同意：

1. 不创建 `AIQuiz`，以 `Problem + ProblemAudience` 实现题目发布。
2. 发布规则使用规范关系表和空字符串约束，不使用平行 JSON 数组。
3. `publishing_suspended` 只供 Alex 全局暂停；普通教师通过启停本年级规则控制可见性。
4. 普通教师只编辑自己创建的题目内容，但可以配置共享题目在自己年级的发布范围。
5. Alex 的全校规则生效时普通教师不能用本年级规则覆盖。
6. 使用 `management_version + select_for_update` 防止并发覆盖。
7. 旧题迁移为 active 全校规则；新同步题默认无范围、学生不可见。
8. DELETE 改为 Alex 软归档，`Submission.problem` 改为 `PROTECT`。
9. 学生列表、详情、正式提交、成绩、统计和历史统一使用可见题目集合。
10. 隐藏前任务允许完成和本人轮询，隐藏后禁止创建新评分任务。
11. 保持 AI 最高分统计、通用代码运行和当前测试点展示方式不变。
12. DEV 确认后才创建 migration 和修改前后端业务代码。
