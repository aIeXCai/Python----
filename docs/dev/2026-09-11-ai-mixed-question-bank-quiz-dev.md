# AI 混合题库与自由组卷 DEV 技术设计

文档日期：2026-09-11
文档状态：用户已确认（2026-09-11）
对应 PRD：`docs/prd/2026-09-11-ai-mixed-question-bank-quiz-prd.md`
前置条件：AI 混合题库与自由组卷 PRD 已于 2026-09-11 确认
实施状态：Step 0–10 已完成（Step 10 于 2026-09-12 完成）；用户确认现有 9 道编程题暂不归类，等待进入 Step 11

## 1. 实施目标与技术不变量

本阶段把 AI 课程从“单道编程题直接练习”升级为“按单元管理选择题和编程题，并发布混合小测”，同时保留旧练习链路。实施过程中必须始终满足：

1. 现有 `Problem`、`Submission`、`ExecutionTask`、磁盘测试点和历史成绩不删除、不改业务标识。
2. `Problem` 从“小测”回归“编程题库题目”；正式小测使用新的 `AIQuizSession`。
3. AI 单元和信息课单元表分离，避免跨 app 外键耦合，但保持一致的年级—大单元—小节体验。
4. 选择题按发布时冻结的候选题池抽取；编程题按教师选定顺序全部进入试卷。
5. 同一场已发布小测的候选题内容、编程题内容、分值和测试点标准固定，不因题库后续编辑而漂移。
6. 每名学生每次作答有不可变 `snapshot_json`；作答中响应不含选择题答案、解析、原始选项映射或隐藏测试点。
7. 正式计分只读取服务端快照和 Runner 结果，不信任客户端分值、答案映射、截止时间或题目归属。
8. 同一学生、同一小测同时只有一个当前有效 attempt；开始、保存、评测、交卷和结算均可安全重试。
9. 代码仍只在独立 Runner 执行；新增小测能力不改变 Runner 内部协议和隔离边界。
10. 截止前已受理的正式编程评测可以完成并计分，截止后禁止创建新运行、评测和选择题保存。
11. 题库练习和正式小测使用不同入口与成绩口径；旧历史提交不伪造成小测 attempt。
12. 学生权限来自本人身份，教师权限来自 `managed_grade`/超级管理员身份，前端参数不能扩大权限。

## 2. 当前实现基线

### 2.1 直接复用

- `ai_courses.Problem`：编程题内容、稳定 `problem_id`、模板代码、测试点读取、归档和内容所有权。
- `ai_courses.ProblemAudience`：继续控制题库自主练习可见范围。
- `ai_courses.Submission`：保留每次正式代码提交及其分数、错误和 `ExecutionTask` 一对一关系。
- `execution.ExecutionTask`：异步队列、幂等键、任务租约、测试点快照、Runner 结果校验和公开轮询。
- 信息课 `quiz_snapshot.py`：随机抽题、选项打乱、学生字段白名单和结果快照的设计方法。
- 信息课 `quiz_services.py`：当前 attempt 唯一约束、答案版本、服务端截止时间、恢复、重置和幂等结算模式。
- `users.grade_levels`、`users.scopes`、教师管理年级和真实班级查询能力。
- React 的 Monaco 编辑器、异步任务恢复、选择题作答、倒计时和成绩页交互。

### 2.2 必须新增或替换

- 新增 AI 单元、AI 选择题、AI 小测、发布受众、编程题项和 attempt 模型。
- `Problem` 增加 AI 单元归属；旧题允许暂时为空。
- `Submission` 和 `ExecutionTask` 增加可空的小测上下文，以区分题库练习和正式小测。
- 原 AI 首页拆分为“我的小测”和“题库练习”。
- 原 AI 管理页拆分为单元、选择题库、编程题库、小测、成绩五个区域。
- 原 `/api/ai/submissions/` 保持题库练习语义；正式小测代码使用独立接口和服务函数。
- 原 AI 总题数/完成数/平均分统计不能继续同时代表题库练习和正式小测。

## 3. 总体架构

```text
AIUnit
├── AIChoiceQuestion
└── Problem（现有编程题，新增 unit）

AIQuizSession（草稿配置）
├── choice_units
├── AIQuizProgrammingItem（顺序 + 分值）
├── AIQuizAudience（发布范围）
└── blueprint_json（首次发布时冻结）
       ├── 完整选择题候选池
       ├── 选择题抽题/难度/分值规则
       └── 编程题题干、模板、分值、测试点快照

AIQuizAttempt（学生一次作答）
├── snapshot_json（从 blueprint 随机生成）
├── answers_json + answer_revision
├── Submission[]（正式编程评测，多次提交）
│      └── ExecutionTask（现有 Runner 队列）
└── choice_score / programming_score / total_score
```

代码分层：

- `models.py`：持久化关系、状态、约束与索引。
- `quiz_permissions.py`：学生可见范围、教师管理范围和对象归属查询。
- `quiz_blueprint.py`：发布校验与不可变蓝图生成。
- `quiz_snapshot.py`：从蓝图生成个人试卷、学生字段白名单和结果序列化。
- `quiz_services.py`：开始、保存、提交、关闭、结算、重置和重评事务。
- `quiz_queries.py`：列表、成绩和分析聚合，避免把统计写进 View。
- Serializer：请求白名单和响应契约。
- View：认证、调用服务和统一错误映射。
- React：按 API 状态渲染，不自行决定权限、分值或是否超时。

## 4. 数据模型设计

所有新表位于 `ai_courses` app。字段名在实施时可因 Django/数据库限制小幅调整，但语义不得改变。

### 4.1 `AIUnit`

| 字段 | 类型 | 说明 |
|---|---|---|
| `grade` | `CharField(choices=GRADE_CHOICES, db_index=True)` | 课程年级 |
| `parent` | `ForeignKey(self, PROTECT, null=True)` | 空为大单元，非空为小节 |
| `name` | `CharField(max_length=100)` | 稳定短名称 |
| `display_name` | `CharField(max_length=200)` | 教师与学生显示名称 |
| `order` | `IntegerField(default=0)` | 同层排序 |
| `created_by` | `ForeignKey(CustomUser, SET_NULL, null=True)` | 创建教师 |
| `archived_at` | `DateTimeField(null=True, db_index=True)` | 软归档 |
| `created_at/updated_at` | 时间字段 | 审计时间 |

约束与验证：

- `UniqueConstraint(grade, parent, name)`；MySQL 对 `NULL parent` 的唯一语义不能阻止重复大单元，因此服务层在事务中额外检查同年级大单元重名。
- 只允许两级结构：小节的 parent 必须是根单元，不能建立第三层。
- 子项和父项必须同年级。
- 有题目、草稿小测关系或历史蓝图引用时只允许归档，不物理删除。
- 索引 `(grade, archived_at, order)`、`(parent, archived_at, order)`。

### 4.2 `AIChoiceQuestion`

字段与信息课 `Question` 基本一致：

- `unit=ForeignKey(AIUnit, PROTECT, related_name='choice_questions')`；
- `difficulty=easy/medium/hard`；
- `category`、`text`；
- `option_a/option_b/option_c/option_d`；
- `answer=A/B/C/D`；
- `explanation`；
- `created_by=SET_NULL`；
- `management_version=PositiveIntegerField(default=1)`；
- `archived_at`、`created_at`、`updated_at`。

验证：

- unit 必须是未归档叶子小节。
- 题干和四个选项 trim 后非空，答案必须是 A-D。
- 普通教师只能写入 `unit.grade == managed_grade` 的题目。
- 修改使用 `expected_version` 防止多教师覆盖。
- 日常删除设置 `archived_at`；历史蓝图不依赖当前行恢复结果。

### 4.3 `Problem` 改造

新增：

| 字段 | 类型 | 说明 |
|---|---|---|
| `unit` | `ForeignKey(AIUnit, PROTECT, null=True, blank=True)` | AI 题的主要叶子小节；旧题过渡期允许空 |

规则：

- 仅 `course='ai'` 的 Problem 可以关联 `AIUnit`。
- unit 必须是未归档叶子小节。
- 设置 unit 时 `grade_tag` 同步为 `unit.grade`；后续 API 不允许两者分别写出冲突值。
- 未归类、已归档、题干为空或 `get_test_count()==0` 的 Problem 不可用于新组卷。
- 磁盘同步不得清空数据库中已有 unit。

### 4.4 `AIQuizSession`

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | `CharField(max_length=200)` | 小测名称 |
| `content_grade` | `CharField(choices=GRADE_CHOICES)` | 组卷所用 AI 课程年级 |
| `created_by` | `ForeignKey(CustomUser, PROTECT)` | 创建教师 |
| `choice_units` | `ManyToManyField(AIUnit)` | 草稿阶段选择题池小节 |
| `choice_question_count` | `PositiveSmallIntegerField(default=0)` | 抽题数 |
| `choice_difficulty_ratio` | `JSONField(default=dict)` | `easy/medium/hard` 精确题数 |
| `choice_points` | `DecimalField(max_digits=5, decimal_places=1)` | 选择题部分分值 |
| `time_limit` | `PositiveSmallIntegerField(null=True)` | 分钟；空为不限时 |
| `status` | `draft/open/closed` | 生命周期唯一真相 |
| `management_version` | `PositiveIntegerField(default=1)` | 草稿/范围并发版本 |
| `blueprint_version` | `PositiveSmallIntegerField(default=0)` | 0 未发布，首版为 1 |
| `blueprint_json` | `JSONField(null=True)` | 首次发布生成，之后不可变 |
| `blueprint_hash` | `CharField(max_length=64, blank=True)` | 规范 JSON SHA-256 |
| `opened_at/closed_at` | 可空时间 | 生命周期时间 |
| `archived_at` | 可空时间、索引 | 软归档 |
| `created_at/updated_at` | 时间字段 | 审计时间 |

约束：

- 分值字段范围 0–100。
- `status != draft` 时 `blueprint_version > 0`、蓝图和 hash 非空。
- `blueprint_json` 只由领域服务写入，不接受普通 Serializer 透传。
- 第一次开放后不允许修改 content、规则、顺序、分值和时长；发布范围和 open/closed 状态仍可改。

`content_grade` 表示题库内容所属年级。超级管理员可以把同一内容发布到更广范围，但 UI 必须明确显示内容年级；普通教师只能选择本人 `managed_grade`。

### 4.5 `AIQuizProgrammingItem`

| 字段 | 类型 | 说明 |
|---|---|---|
| `session` | `ForeignKey(AIQuizSession, CASCADE)` | 草稿所属小测 |
| `problem` | `ForeignKey(Problem, PROTECT)` | 编程题 |
| `position` | `PositiveSmallIntegerField` | 编程题内部顺序 |
| `points` | `DecimalField(max_digits=5, decimal_places=1)` | 折算分值 |

约束：

- `UniqueConstraint(session, problem)`。
- `UniqueConstraint(session, position)`。
- points 大于 0 且不超过 100。
- 小测首次发布后禁止增删改；历史还原依赖蓝图，关系表用于管理查询。

### 4.6 `AIQuizAudience`

复用 `ProblemAudience` 的规范范围模式，但关联 `AIQuizSession`：

- `scope_type=all_school/grade_all/class`；
- `grade`、`class_num` 使用空字符串规避 MySQL 唯一索引 NULL 语义；
- `is_active`、`configured_by`、时间字段；
- 唯一约束 `(session, scope_type, grade, class_num)`；
- Check 约束和索引与 `ProblemAudience` 同构。

普通教师服务端只允许修改本人 `managed_grade`；超级管理员可以配置全校或跨年级。范围只决定谁可开始/发现小测，不改变 `content_grade` 和蓝图内容。

### 4.7 `AIQuizAttempt`

状态：

```text
in_progress -> settling -> submitted
                       -> timed_out
                       -> closed
in_progress/submitted/timed_out/closed -> reset（教师重置历史）
旧的当前 attempt -> superseded（学生开始下一次时）
```

字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `user` | `ForeignKey(CustomUser, PROTECT)` | 学生 |
| `session` | `ForeignKey(AIQuizSession, PROTECT)` | 小测 |
| `status` | 状态枚举、索引 | 作答状态 |
| `final_reason` | `submitted/timed_out/closed/blank` | 结算原因 |
| `attempt_no` | `PositiveIntegerField` | 第几次作答 |
| `current_marker` | `BooleanField(null=True, default=True)` | 当前行为 True，历史为 NULL |
| `snapshot_version` | `PositiveSmallIntegerField(default=1)` | 快照版本 |
| `snapshot_json` | `JSONField` | 个人试卷与评分真相 |
| `answers_json` | `JSONField(default=dict)` | `{choice_item_id: displayed_letter}` |
| `answer_revision` | `PositiveIntegerField(default=0)` | 乐观并发 |
| `choice_score` | `DecimalField(null=True)` | 选择题折算分 |
| `programming_score` | `DecimalField(null=True)` | 编程题折算分 |
| `total_score` | `DecimalField(null=True)` | 0–100 |
| `correct_count/choice_count` | 可空整数 | 选择题统计 |
| `grade/class/student_number` | 字符串 | 学生身份快照 |
| `started_at/deadline_at` | 时间 | 服务端计时 |
| `settlement_requested_at` | 可空时间 | 锁卷时间 |
| `settled_at` | 可空时间 | 完成结算时间 |
| `grading_issue_count` | 非负整数 | 无有效成绩的异常编程项数 |
| `result_revision` | 非负整数 | 重评后结果版本 |
| `reset_at/reset_by/reset_reason` | 重置审计字段 | 保留历史 |
| `updated_at` | 时间 | 最近变化 |

约束与索引：

1. `UniqueConstraint(user, session, attempt_no)`。
2. `UniqueConstraint(user, session, current_marker)`；仅 `True/NULL`，沿用信息课跨 SQLite/MySQL 方案。
3. 分数为空或位于 0–100。
4. `(session, status)`、`(status, deadline_at)`、`(user, session, current_marker)`、`(grade, session)` 索引。
5. attempt 快照生成后永不修改；只更新答案、状态和结果字段。

### 4.8 `Submission` 改造

新增可空字段：

- `quiz_attempt=ForeignKey(AIQuizAttempt, PROTECT, null=True, related_name='code_submissions')`；
- `quiz_item_id=CharField(max_length=36, blank=True, db_index=True)`：指向 attempt 快照中的编程题 item UUID；
- `regrade_of=ForeignKey(self, SET_NULL, null=True, related_name='regrades')`；
- `counts_for_quiz=BooleanField(default=True)`：系统错误重评和管理员处置时保留显式口径。

规则：

- 普通题库练习：`quiz_attempt=NULL AND quiz_item_id=''`。
- 正式小测：二者必须同时存在；服务层验证 item 属于快照且其 `source_problem_id` 等于 `Submission.problem_id`。
- 不尝试用数据库 Check 跨 JSON 验证题目归属，事务服务是唯一写入口。
- 原有记录迁移时保持空上下文。

### 4.9 `ExecutionTask` 改造

为运行任务和正式评测统一增加可空字段：

- `quiz_attempt=ForeignKey(AIQuizAttempt, SET_NULL, null=True, related_name='execution_tasks')`；
- `quiz_item_id=CharField(max_length=36, blank=True, db_index=True)`。

普通练习任务保持为空。小测运行/评测在创建时写入上下文，便于截止校验、按题恢复任务和审计。Runner 领取任务的 envelope 不需要新增字段，Runner 协议保持不变。

### 4.10 管理审计

新增 `AIQuizManagementAudit`，覆盖单元、选择题和小测事件。保存：事件类型、结果、操作者 ID 快照、对象类型、对象 ID、原因码、前后摘要、IP 和时间。

不保存完整正确答案集合、解析全集、蓝图、测试点、学生答案或学生代码。现有 `ProblemManagementAudit` 继续负责编程题内容与练习发布事件。

## 5. 发布蓝图

### 5.1 为什么在发布时冻结

只在学生开始时查询当前题库，会导致先开始和后开始的学生使用不同题干、选项或测试点。首次开放小测时必须把本场考试所依赖的内容冻结为发布蓝图。

### 5.2 蓝图结构（schema version 1）

示意：

```json
{
  "schema_version": 1,
  "session": {
    "title": "循环与列表小测",
    "content_grade": "八年级",
    "time_limit": 45,
    "choice_question_count": 5,
    "choice_difficulty_ratio": {"easy": 2, "medium": 2, "hard": 1},
    "choice_points": "30.0"
  },
  "choice_pool": [
    {
      "source_question_id": 31,
      "source_version": 2,
      "unit_id": 6,
      "difficulty": "easy",
      "category": "range",
      "text": "题干",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct_source_option": "B",
      "explanation": "解析"
    }
  ],
  "programming_items": [
    {
      "item_id": "固定 UUID",
      "source_problem_id": "problem3",
      "source_management_version": 4,
      "position": 1,
      "points": "35.0",
      "title": "星号三角形",
      "description": "...",
      "template_code": "...",
      "test_snapshot": {"schema_version": 1, "cases": []},
      "test_snapshot_hash": "sha256"
    }
  ]
}
```

规范：

- 使用稳定键排序和紧凑 JSON 生成 `blueprint_hash`。
- 分值在 JSON 中用十进制定点字符串，禁止二进制浮点累计误差。
- `choice_pool` 保存满足所选单元的全部可用候选题内容，attempt 从冻结池中抽取。
- 编程测试点使用现有 `execution.snapshots.build_test_snapshot(problem)` 生成并校验。
- 蓝图不通过学生或普通列表接口返回，不写应用日志。
- 首次 `draft -> open` 在事务中构建并保存；构建失败则整个发布回滚。
- `closed -> open` 复用原蓝图，不重新读取题库。

### 5.3 个人快照

`AIQuizAttempt.snapshot_json` 从蓝图生成：

- 按难度从冻结 `choice_pool` 采样，题目不重复。
- 选择题顺序随机，四个选项独立随机。
- 为每个选择题生成随机 `item_id`，保存展示选项和 `correct_display_option`。
- 编程题复制蓝图中的固定 item_id、题干、模板和分值；隐藏测试点不复制到学生可读部分。评测服务从 session 蓝图按 item_id 读取测试快照。
- 快照保存 session/blueprint hash，防止错误关联。

## 6. 生命周期与事务服务

### 6.1 服务错误

建立 `AIQuizServiceError(code, message, http_status, **extra)`，View 统一映射。稳定错误码至少包括：

- `quiz_not_found`、`quiz_not_open`、`quiz_locked`；
- `quiz_scope_forbidden`、`teacher_grade_forbidden`；
- `quiz_pool_insufficient`、`quiz_points_invalid`、`invalid_programming_problem`；
- `attempt_not_found`、`attempt_not_active`、`attempt_completed`；
- `attempt_revision_conflict`、`unknown_quiz_item`、`invalid_option`；
- `quiz_deadline_passed`、`execution_pending`；
- `idempotency_conflict`、`regrade_not_allowed`。

### 6.2 `publish_quiz(actor, session_id, expected_version)`

事务：

1. `select_for_update()` 锁 session。
2. 校验操作者、状态、版本、受众、时间和分值。
3. 查询并锁定相关单元、候选选择题和编程题；校验年级、归档和题库容量。
4. 构建、规范编码并哈希蓝图。
5. 保存 `blueprint_version=1`、蓝图、hash、`status=open`、`opened_at`、版本加一。
6. 写成功审计；任何失败回滚并写不含敏感内容的失败审计。

### 6.3 `start_or_resume_attempt(user, session_id)`

事务：

1. 锁用户和 session，校验学生身份、session open、未归档和发布范围。
2. 查询 `current_marker=True`；如为 `in_progress` 且未到截止，直接恢复。
3. 如已过截止，先请求结算；根据状态返回结算中或结果。
4. 如当前 attempt 已完成，将其 `current_marker=NULL` 并创建 `attempt_no+1`。
5. 从发布蓝图生成个人快照，设置身份快照、开始和截止时间。
6. 捕获唯一约束冲突并返回并发请求已创建的同一 attempt。

### 6.4 `save_choice_answers(...)`

- 请求提交完整选择题答案字典和当前 revision。
- 锁本人当前 attempt，先执行服务端截止判断。
- 只接受快照中的 choice item UUID 和 A-D 展示字母。
- revision 不一致返回 409 和当前 revision。
- 原子保存规范答案并 `answer_revision += 1`。
- 已锁卷、结算中或已完成时拒绝修改。

### 6.5 `enqueue_quiz_run(...)`

- 锁或稳定读取 attempt，校验 `in_progress`、未截止和编程 item 归属。
- 代码/标准输入大小、容量和 UUID 幂等键继续使用 execution 现有规则。
- 创建 `task_type=run` 的 ExecutionTask，并写入 attempt/item 上下文。
- digest 包含 attempt ID、item ID、代码和 stdin，避免幂等键跨题复用。
- 不创建 Submission，不参与成绩和结算等待。

### 6.6 `enqueue_quiz_grade(...)`

- 校验 attempt、截止时间和编程 item。
- 从 session 蓝图按 item ID 读取冻结的 `test_snapshot`，不得调用当前 Problem 的 `get_test_cases()`。
- 扩展 execution 服务，允许内部可信调用传入已验证测试快照；普通公开接口不能提交测试快照。
- digest 包含 attempt、item、problem、代码和测试快照 hash。
- 原子创建 ExecutionTask 与带小测上下文的 Submission。
- 现有题库练习 `enqueue_grade()` 行为不变。

### 6.7 `request_settlement(..., reason)`

主动交卷、超时和教师关闭使用同一入口：

1. 锁 attempt；已完成时返回已存结果。
2. 主动交卷可携带 final choice answers 和 revision；其他原因使用最后成功保存答案。
3. 保存最终选择答案，设置 `settlement_requested_at` 和 `final_reason`。
4. 将状态改为 `settling`，从此拒绝新保存、运行和评测。
5. 检查截止/关闭前已受理的 grade 任务：
   - 有非终态任务：提交事务并返回 `settling`；
   - 全部终态：在同一服务中调用 `finalize_attempt()`。

主动交卷请求到达服务端即锁卷，不等待前端轮询结束。交卷重复请求幂等返回当前状态。

### 6.8 `finalize_attempt(attempt_id)`

事务中锁 attempt：

- 只处理 `settling`，重复调用安全返回。
- 选择题按快照正确展示选项评分，未答为错。
- 对每个编程 item 查询该 attempt/item 下 `counts_for_quiz=True` 且 `score IS NOT NULL` 的 Submission，取最高分；同分时取最早完成记录作为展示依据。
- 仍有非终态正式评测则保持 settling。
- 无有效分数的编程 item 得 0，并累计 `grading_issue_count`（只有系统错误/取消时记异常；学生未提交不记系统异常）。
- 使用 `Decimal` 折算并量化到 1 位小数。
- 按 `final_reason` 设置 `submitted/timed_out/closed`，写各部分分数和 `settled_at`。

### 6.9 Runner 完成后的结算钩子

`execution.queue.complete_task()` 完成现有 Task/Submission 更新后：

- 使用 `transaction.on_commit()` 调用轻量、幂等的 `maybe_finalize_attempt(task_id)`；
- 函数只在 task 带 quiz context 且 attempt 为 settling 时尝试结算；
- 使用函数内延迟 import 避免 execution 与 ai_courses 模块循环导入；
- 钩子异常写结构化日志但不改变 Runner 已成功回执；补偿机制稍后重试。

### 6.10 超时和补偿

项目当前没有 Celery/Redis 常驻调度，因此第一阶段采用三层补偿：

1. 学生恢复、保存、运行、评测、交卷、结果查询时惰性检查截止。
2. 教师打开小测统计或关闭小测时批量请求过期 attempt 结算。
3. 新增 `python manage.py settle_ai_quiz_attempts` 管理命令，处理：
   - 已过 deadline 的 `in_progress`；
   - 所有 grade 任务已终态但仍为 `settling`；
   - 超过合理等待窗口且任务已取消/过期的 attempt。

生产部署文档在现有系统任务中每分钟运行该幂等命令。DEV 验收必须验证无定时命令时，用户和教师读取仍可触发正确结算。

### 6.11 关闭、重置与重评

- `close_quiz()`：锁 session 改 closed，对进行中 attempt 批量调用结算请求；不能在一个超大事务中等待 Runner。
- `reset_attempt()`：只在 session open 时允许；旧 attempt 设 reset/current NULL，保存教师和原因，学生下次开始获得新 attempt。
- `regrade_submission()`：教师仅可对 `grading_issue_count>0` 且原任务为系统错误/取消的 item 操作；使用原 Submission 代码和蓝图测试快照创建新 Submission/Task，并设置 `regrade_of`。
- 重评完成后重新计算该 attempt，`result_revision += 1`；历史结果变更写审计并在学生结果页标识“系统重评已更新”。

## 7. 权限设计

### 7.1 学生发现与访问

新增：

```python
visible_ai_quizzes_for_student(queryset, user)
get_visible_ai_quiz_or_404(user, session_id)
get_student_attempt_or_404(user, session_id, attempt_id)
```

访问必须同时满足：学生启用、身份字段规范、session open/允许读取历史结果、未归档、命中一条 audience。直接访问未授权资源返回不泄露存在性的 404；本人已完成结果在小测关闭后仍可读取。

### 7.2 教师管理

- 普通教师只能创建 `content_grade == managed_grade` 的 session 和题库内容。
- 范围写服务忽略客户端伪造的其他年级，普通教师只能维护本人年级规则。
- 超级管理员可以管理全部年级和全校规则。
- 题库内容编辑继续执行所有者规则；“可用于组卷”不等于“可编辑内容”。
- 成绩查询必须先得到教师可管理 session queryset，再按 session 过滤 attempt。

### 7.3 AI 助手

- Chat 后端除前端禁用外，还必须拒绝 `context.type='ai_quiz_choice'` 或处于选择题页面的正式小测上下文。
- 编程上下文使用 `ai_quiz_programming`，服务端校验 attempt/item 属于当前学生且仍允许辅导。
- 注入模型的内容只取个人快照的编程题公开字段、学生主动提交的代码和本人最近错误。

## 8. API 契约

具体字段由 Serializer 定义，时间统一 ISO 8601，错误统一 `{error, code, ...safe_extra}`。

### 8.1 教师端单元与题库

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/api/ai/admin/units/` | 分层列表、创建 |
| PATCH/DELETE | `/api/ai/admin/units/{id}/` | 编辑、软归档 |
| POST | `/api/ai/admin/units/{id}/restore/` | 恢复 |
| GET/POST | `/api/ai/admin/choice-questions/` | 筛选列表、创建 |
| GET/PATCH/DELETE | `/api/ai/admin/choice-questions/{id}/` | 详情、编辑、归档 |
| POST | `/api/ai/admin/choice-questions/{id}/copy/` | 复制为当前教师的新题，可选目标小节 |
| POST | `/api/ai/admin/choice-questions/{id}/restore/` | 恢复 |
| POST | `/api/ai/admin/choice-questions/import/` | JSON 批量导入 |
| GET | `/api/ai/admin/problems/` | 扩展 unit/grade/usable 筛选与字段 |
| PATCH | `/api/ai/admin/problems/{problem_id}/` | 扩展 unit 更新 |

### 8.2 教师端小测

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/api/ai/admin/quizzes/` | 列表、创建草稿 |
| GET/PATCH/DELETE | `/api/ai/admin/quizzes/{id}/` | 详情、编辑草稿、归档 |
| POST | `/api/ai/admin/quizzes/{id}/validate/` | 发布前检查和题池摘要 |
| POST | `/api/ai/admin/quizzes/{id}/publish/` | 首次发布并冻结蓝图 |
| POST | `/api/ai/admin/quizzes/{id}/close/` | 关闭并请求结算 |
| POST | `/api/ai/admin/quizzes/{id}/reopen/` | 使用原蓝图重新开放 |
| POST | `/api/ai/admin/quizzes/{id}/copy/` | 复制为新草稿，不复制蓝图/成绩 |
| GET/PATCH | `/api/ai/admin/quizzes/{id}/audience/` | 范围读取和更新 |
| POST | `/api/ai/admin/quizzes/{id}/attempts/{attempt_id}/reset/` | 重置 |
| POST | `/api/ai/admin/quizzes/{id}/attempts/{attempt_id}/items/{item_id}/regrade/` | 系统异常重评 |
| GET | `/api/ai/admin/quizzes/{id}/analytics/overview/` | 参与情况与最近一次已结算成绩概览 |
| GET | `/api/ai/admin/quizzes/{id}/analytics/students/` | 分页、筛选学生明细，包含最近成绩与历史最好成绩 |
| GET | `/api/ai/admin/quizzes/{id}/analytics/students/{student_id}/attempts/` | 分页历史作答摘要，不返回学生代码 |
| GET | `/api/ai/admin/quizzes/{id}/analytics/items/` | 按冻结快照统计选择题选项分布与编程题表现 |

创建/编辑草稿请求示意：

```json
{
  "title": "循环与列表小测",
  "content_grade": "八年级",
  "choice_unit_ids": [5, 6],
  "choice_question_count": 5,
  "choice_difficulty_ratio": {"easy": 2, "medium": 2, "hard": 1},
  "choice_points": "30.0",
  "programming_items": [
    {"problem_id": "problem3", "position": 1, "points": "30.0"},
    {"problem_id": "problem5", "position": 2, "points": "40.0"}
  ],
  "time_limit": 45,
  "expected_version": 1
}
```

### 8.3 学生端小测

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/ai/quizzes/` | 本人可见小测、动作和成绩摘要 |
| POST | `/api/ai/quizzes/{id}/attempt/` | 开始或恢复 |
| PUT | `/api/ai/quizzes/{id}/attempt/answers/` | 全量保存选择题答案 |
| GET | `/api/ai/quizzes/{id}/attempt/items/{item_id}/` | 获取本人快照中的编程题公开内容 |
| POST | `/api/ai/quizzes/{id}/attempt/items/{item_id}/run/` | 小测内运行代码 |
| POST | `/api/ai/quizzes/{id}/attempt/items/{item_id}/submit/` | 小测内正式评测 |
| GET | `/api/ai/quizzes/{id}/attempt/items/{item_id}/executions/active/` | 恢复本人活动任务 |
| POST | `/api/ai/quizzes/{id}/attempt/submit/` | 锁卷并请求结算 |
| GET | `/api/ai/quizzes/{id}/result/` | 当前/最近结果或 settling 状态 |
| GET | `/api/ai/quizzes/{id}/attempts/` | 本人历史作答摘要 |

开始/恢复响应使用显式学生白名单：

```json
{
  "attempt_id": 81,
  "status": "in_progress",
  "revision": 3,
  "server_time": "...",
  "deadline_at": "...",
  "remaining_seconds": 1200,
  "quiz": {
    "id": 7,
    "title": "循环与列表小测",
    "choice_count": 5,
    "programming_count": 2,
    "total_points": "100.0"
  },
  "items": [
    {"item_id": "...", "type": "choice", "position": 1, "text": "...", "options": {}},
    {"item_id": "...", "type": "programming", "position": 6, "title": "...", "points": "30.0"}
  ],
  "saved_answers": {}
}
```

主响应不返回全部编程题模板，学生打开对应编程 item 时按需获取，减少快照内容暴露和首屏体积。

## 9. 前端设计

### 9.1 API 模块

- 保留 `frontend/src/api/index.js` 的旧 AI 练习 API。
- 新增 `frontend/src/api/aiQuiz.js`，集中管理单元、选择题、小测、attempt 和成绩接口。
- 复用统一 `request()`、Token、幂等 UUID 和错误对象格式。
- 所有自动保存请求支持 `keepalive`，页面卸载前只发送本人最新完整选择题答案。

### 9.2 学生首页

改造 `StudentDashboard.jsx`：

- AI 课程并行加载 `getAIQuizzes()`、旧 `getProblems()` 和对应统计。
- 页面显示“我的小测”“题库练习”两个清晰区块。
- 旧题目卡片路由保持 `/problem/:problemId?course=ai`。
- 新小测路由：`/student/ai-quiz/:sessionId` 和 `/student/ai-quiz-result/:sessionId`。
- 正式小测统计与题库练习统计分开显示，避免把不同口径混成一个平均分。

### 9.3 学生作答页

新增 `pages/student/ai/QuizPage.jsx`：

- 顶部显示标题、倒计时、保存/结算状态。
- 统一题目导航，题型使用文字和图标双重标识。
- 选择题视图从信息课 `QuizPage` 抽取可复用展示组件，不直接复用其 API 状态。
- 编程题视图从现有 `ProblemDetail` 抽取 `ProgrammingWorkspace`：题干、Monaco、stdin、运行、提交、轮询、结果和历史最高分。
- 切换题目不销毁本地代码草稿；本地草稿仅为体验缓存，正式成绩仍以服务端 Submission 为准。
- 选择题使用全量答案去抖保存、revision、pagehide 兜底和在线恢复。
- 交卷后进入 settling 页面并有限轮询结果；不允许返回页面继续编辑。

### 9.4 AI 助手上下文

- 选择题视图调用 `setDisabled(true, ...)` 并关闭面板。
- 编程题视图设置 `ai_quiz_programming` 上下文。
- 页面卸载和题型切换时清理旧上下文，避免把上一题错误带到下一题。

### 9.5 结果页

新增 `pages/student/ai/QuizResult.jsx`：

- 处理 settling、完成、超时、关闭结算和重评更新状态。
- 展示总分、选择题分项、编程题分项、错题解析和重做入口。
- 系统异常编程题明确显示“评测异常，教师可重评”，不伪装成学生答案错误。

### 9.6 教师端

将 `aiAdmin.jsx` 逐步拆为容器和五个 tab 组件：

- `tabs/AIUnitsTab.jsx`；
- `tabs/AIChoiceQuestionsTab.jsx`；
- `tabs/AIProgrammingProblemsTab.jsx`；
- `tabs/AIQuizzesTab.jsx`；
- `tabs/AIQuizStatsTab.jsx`。

小测创建建议使用独立 `AIQuizBuilder` 页面或大尺寸分步 Modal，不继续把全部逻辑堆入 `aiAdmin.jsx`。步骤为基本信息、选择题、编程题、分值范围、预览保存。每一步只更新本地草稿，最终一次 PATCH；发布另行调用 validate/publish。

## 10. 统计查询设计

### 10.1 学生摘要

对每个可见 session 使用子查询或预聚合得到：

- 当前 attempt 状态；
- 最近一次已结算总分；
- 历史最好总分；
- attempt 次数；
- action：`start/continue/result/restart/settling`。

避免对每张卡片逐条查询 attempt。

### 10.2 教师概览

- 应参与人数由 session audience 与当前启用学生计算。
- 已开始/进行中/结算中/已完成按每个学生 current/latest attempt 统计。
- 默认成绩口径为每位学生最近一次已结算 attempt。
- 选择题和编程题分析读取 attempt 快照和最终分项，不回查当前题库。
- 选择题选项分布必须按快照 `source_question_id + source_version` 聚合；不同展示字母先映射回冻结源选项，防止选项打乱造成错误统计。

### 10.3 数据量与分页

- 学生明细和历史 attempt 必须分页。
- 题目分析可按 session 缓存短时间聚合结果；MVP 先正确查询并监控性能，不提前引入 Redis。
- 对常用过滤字段建立第 4 节所列索引，并用 `assertNumQueries`/查询捕获验证无明显 N+1。

## 11. 迁移设计

迁移文件从 `ai_courses/0007_*` 开始，按可回滚小步拆分。

### Migration 0007：单元与题库基础

- 创建 `AIUnit`、`AIChoiceQuestion`。
- `Problem` 增加可空 unit。
- 增加基础约束和索引。
- 不执行内容猜测或自动归类。

### Migration 0008：小测配置

- 创建 `AIQuizSession`、`AIQuizProgrammingItem`、`AIQuizAudience` 和管理审计。
- 所有新表初始为空。

### Migration 0009：Attempt 与执行关联

- 创建 `AIQuizAttempt`。
- `Submission` 和 `ExecutionTask` 增加可空 quiz context/regrade 字段。
- 旧记录自动保持 NULL/空字符串，不重写历史代码或分数。

### Migration 0010：约束收紧

- 在模型与服务测试稳定后添加跨字段 Check 和最终唯一约束。
- SQLite 与 MySQL 8.0 分别运行 migrate forward/backward 测试。

迁移前后记录数检查：

- Problem、ProblemAudience、Submission、ExecutionTask 行数一致。
- 每条 Submission 的 user/problem/code/score/status/execution_task 不变。
- 每条 ExecutionTask 的 public_id、快照、hash、状态和幂等键不变。

## 12. 分步实施计划

每个 Step 完成后必须在本 DEV 标题后标注“✅ 已完成（日期）”，运行该步定向测试并提交用户验收；未通过不得进入下一步。

### Step 0：基线与契约保护 ✅ 已完成（2026-09-11）

目标：先锁定旧链路不回归。

- 记录当前数据库模型、API、路由和测试基线。
- 增加旧 9 道题/历史 Submission/ExecutionTask 兼容性测试夹具。
- 修正并统一旧 UI 中“完成”与“80/100 分”混用的测试期望，但不改变旧题库练习的通过展示，正式小测使用 attempt 状态。
- 为新 API 错误格式、Decimal 字符串和时间格式建立契约测试辅助函数。

验证：后端 `ai_courses`、`execution` 全量测试，前端全量 Vitest、生产构建和 ESLint 基线。

### Step 1：AI 单元与选择题后端 ✅ 已完成（2026-09-11）

- 实施 Migration 0007。
- 新增单元/选择题模型、服务、Serializer、权限、CRUD、归档恢复和 JSON 导入。
- 注册只读安全字段的 Django Admin。
- 为两级结构、同年级约束、题目校验、权限和并发版本添加测试。

验收：API 可完整管理 AI 单元和选择题，尚不改变学生页面。

### Step 2：编程题归类与存量兼容 ✅ 已完成（2026-09-11）

> 用户确认现有 9 道编程题暂不归类。当前 AI 单元表为空，按本 DEV“不根据标题猜测”的约束保留 9 道题未归类；后续可在教师端按实际教学安排人工归类，不阻塞 Step 3。

- 扩展 Problem 管理 API 和编辑弹窗，支持 unit。
- `sync_from_disk()` 保留 unit，不覆盖人工归类。
- 增加可组卷状态和筛选。
- 保留管理员后续手工归类能力；若未来需要 fixture，单独生成明确映射，不根据标题猜测。

验收：9 道题历史数据不变，教师可按单元筛选，学生旧练习正常。

### Step 3：小测草稿与发布蓝图后端 ✅ 已完成（2026-09-11）

- 实施 Migration 0008。
- 实现小测草稿 CRUD、编程题项顺序/分值、受众和复制。
- 实现 validate/publish、蓝图规范编码、hash 和首次发布锁定。
- 测试题池不足、分值、权限、并发、测试点无效和重开复用蓝图。

验收：可通过 API 创建、预检并发布混合/纯题型小测，尚不允许学生开始。

### Step 4：Attempt、快照与选择题作答后端 ✅ 已完成（2026-09-11）

- 实施 Migration 0009/0010 中 attempt 部分。
- 实现学生小测列表、开始/恢复、个人快照、答案保存和服务端截止时间。
- 实现学生字段白名单与非法 item/答案/越权测试。
- 实现并发开始和 revision 冲突测试。

验收：纯选择题小测可以通过 API 完整作答和恢复，先不最终计分。

### Step 5：小测编程运行与评测集成 ✅ 已完成（2026-09-11）

- 扩展 ExecutionTask/Submission 小测上下文。
- 提供可信冻结测试快照的内部 enqueue 路径。
- 实现小测 run/grade/active API 和上下文权限。
- 保证 Runner envelope 与 Runner 程序无需修改。
- 测试幂等、容量、跨 attempt/item 越权、刷新恢复和旧练习回归。

验收：小测内多道编程题可独立运行、评测和取本 attempt 最高有效分。

### Step 6：交卷、超时、关闭与综合计分 ✅ 已完成（2026-09-11）

- 实现 settling 状态、锁卷、finalize、Runner 完成钩子和管理命令。
- 实现 Decimal 折算、选择题/编程题/总分结果。
- 实现关闭批量请求结算、重置和系统异常重评。
- 添加并发交卷、截止边界、运行中任务和补偿测试。

验收：三种试卷均能得到稳定结果，重复操作不产生双份结果。

### Step 7：教师端题库 UI ✅ 已完成（2026-09-11）

- 拆分 AI 管理页面。
- 完成单元管理、选择题 CRUD/导入和编程题归类筛选。
- 保留原编程题发布、归档、同步和成绩能力。
- 增加组件测试与可访问性查询。

验收：教师无需操作数据库或服务器文件即可完成选择题库维护和旧题归类。

### Step 8：教师端自由组卷 UI ✅ 已完成（2026-09-11）

- 实现分步组卷器、题池数量预览、编程题多选/排序/分值和组卷摘要。
- 实现草稿编辑、发布预检、发布、关闭、重开、复制和范围管理。
- 错误信息精确呈现服务端原因。

验收：教师可从页面完成 PRD 中全部小测管理流程。

### Step 9：学生端混合小测 UI ✅ 已完成（2026-09-12）

- 首页增加“我的小测”和“题库练习”。
- 实现混合作答页、选择题自动保存、编程工作区复用、倒计时和结算页。
- 实现 AI 助手题型切换策略。
- 实现刷新、断网、任务恢复、未答提醒和结果页。

验收：学生可以从首页完成混合小测全链路，旧题库练习不回归。

### Step 10：教师成绩与题目分析 ✅ 已完成（2026-09-12）

- 实现概览、学生明细、历史 attempt、选择题选项分布和编程题分析。
- 默认使用最近一次已结算成绩，并展示历史最好成绩。
- 增加分页、筛选、导出范围（若现有页面已有导出则复用；本期不新造复杂导出格式）。

验收：教师能定位学生未完成、选择题薄弱点和编程题常见失败。

### Step 11：安全、性能、部署与端到端验收

- SQLite 与 MySQL 8.0 全量迁移、约束和并发验证。
- 后端全量测试、前端全量 Vitest、构建和 ESLint。
- 使用真实 Runner 完成至少一次混合小测。
- 验证日志、学生响应、错误响应不泄露答案/测试点/他人数据。
- 更新部署文档，配置每分钟补偿命令。
- 更新 README、接口说明、教师操作手册和阶段完成报告。

验收：PRD AC-01 至 AC-12 全部逐项签收后完成。

## 13. 测试计划

### 13.1 后端模型与迁移

- 两级 AIUnit、年级一致性、归档保护。
- 选择题字段、答案、版本和软归档。
- session/编程题项/受众约束。
- attempt 当前唯一、状态、分数范围和索引。
- 旧数据迁移前后逐字段一致。
- SQLite/MySQL 8.0 forward/backward migration executor 测试。

### 13.2 服务与并发

- 10 个并发开始只产生一个当前 attempt。
- 多标签页答案 revision 冲突。
- 重复幂等键返回同一 Task/Submission。
- 10 个并发交卷只结算一次。
- Runner 回调、用户读取和管理命令同时 finalize 只更新一次。
- 教师关闭与学生提交竞争时，以事务获得锁的服务端顺序产生确定结果。

### 13.3 安全

- 学生响应字段递归扫描禁止 `correct*`、`answer`、`explanation`、`test_snapshot` 等敏感键。
- session/attempt/item/user/grade/class 全组合越权。
- 普通教师跨年级、伪造全校、编辑他人题目和查看他人成绩。
- 直接调用旧 `/submissions/` 不能把小测上下文伪造成普通练习以绕过截止。
- Chat 选择题上下文前后端双重禁用。

### 13.4 计分

- 选择题除不尽分值的 Decimal 分配与最终舍入。
- 多编程题按权重折算和同题多提交取最高。
- 未答、未提交、学生错误、系统错误和取消的不同口径。
- 纯选择题、纯编程题和混合卷均严格 0–100。
- 重评后 result revision 和总分重算。

### 13.5 前端

- 五个教师 tab 的加载、空态、权限、保存和错误态。
- 组卷器单元多选、题池预览、排序、分值校验和锁定态。
- 学生首页 action 路由。
- 选择题保存、编程代码状态、题目切换、倒计时、交卷和 settling。
- AI 助手在选择题关闭、编程题启用、切换时清理上下文。
- 结果页分项、异常和重评更新。

### 13.6 端到端

最小真实验收数据：

- 1 个年级、2 个班、2 个小节；
- 每个难度至少 3 道选择题；
- 2 道有效编程题；
- 1 场 5 道选择题 + 2 道编程题的混合小测；
- 2 名可见学生、1 名不可见学生；
- 真实 Runner 在线。

验证教师建库→组卷→发布→学生随机作答→代码评测→交卷→成绩分析→重做→关闭全链路。

## 14. 关键文件清单

预计新增：

- `backend/ai_courses/quiz_blueprint.py`
- `backend/ai_courses/quiz_snapshot.py`
- `backend/ai_courses/quiz_services.py`
- `backend/ai_courses/quiz_permissions.py`
- `backend/ai_courses/quiz_queries.py`
- `backend/ai_courses/serializers_quiz.py`
- `backend/ai_courses/views_quiz_student.py`
- `backend/ai_courses/views_quiz_admin.py`
- `backend/ai_courses/urls_quiz_student.py`
- `backend/ai_courses/urls_quiz_admin.py`
- `backend/ai_courses/management/commands/settle_ai_quiz_attempts.py`
- 对应 migrations 与 tests。
- `frontend/src/api/aiQuiz.js`
- `frontend/src/pages/student/ai/QuizPage.jsx`
- `frontend/src/pages/student/ai/QuizResult.jsx`
- `frontend/src/pages/teacher/tabs/AIUnitsTab.jsx`
- `frontend/src/pages/teacher/tabs/AIChoiceQuestionsTab.jsx`
- `frontend/src/pages/teacher/tabs/AIProgrammingProblemsTab.jsx`
- `frontend/src/pages/teacher/tabs/AIQuizzesTab.jsx`
- `frontend/src/pages/teacher/tabs/AIQuizStatsTab.jsx`
- `frontend/src/pages/teacher/components/AIQuizBuilder.jsx`
- 对应前端测试文件。

预计修改：

- `backend/ai_courses/models.py`
- `backend/ai_courses/admin.py`
- `backend/ai_courses/serializers.py`
- `backend/ai_courses/views.py`
- `backend/ai_courses/urls.py`
- `backend/ai_courses/problem_management.py`
- `backend/execution/models.py`
- `backend/execution/services.py`
- `backend/execution/queue.py`
- `backend/execution/views_public.py`
- `backend/execution/serializers.py`
- `backend/school_platform/urls.py`（仅在拆分 include 需要时）
- `frontend/src/App.jsx`
- `frontend/src/pages/student/StudentDashboard.jsx`
- `frontend/src/pages/student/ai/ProblemDetail.jsx`（抽取工作区）
- `frontend/src/pages/teacher/aiAdmin.jsx`
- `frontend/src/contexts/ChatContext.jsx` 或聊天请求校验相关文件。

## 15. 资源与部署约束

- 本地开发继续支持 SQLite，生产支持 MySQL 8.0。
- 不新增 Redis/Celery 依赖；结算补偿采用幂等管理命令和现有系统调度。
- 不修改 Runner 镜像和签名协议；Web 端只扩展任务创建时的内部快照来源。
- 蓝图和个人快照可能增大数据库体积，实施时为单场蓝图和单次快照设置可配置大小上限，并在发布前拒绝异常大内容。
- 正确答案、解析、测试点和学生代码不得写入普通日志、审计摘要或前端监控事件。
- 上线采用功能开关 `AI_MIXED_QUIZ_ENABLED`；关闭时隐藏新入口但保留数据和旧练习。

## 16. 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| 小测发布后题库变化导致学生标准不同 | 发布时冻结完整候选池和编程测试点蓝图 |
| 交卷时 Runner 尚未返回 | settling 状态、on_commit 回调、惰性检查和管理命令补偿 |
| 新旧 Submission 统计混淆 | nullable quiz context，练习与小测查询严格分流 |
| 多次编程提交引发任务量上升 | 继续使用用户排队/运行容量限制，前端防连点和幂等键 |
| 蓝图泄露答案或测试点 | 学生 allow-list serializer、递归敏感键测试、日志禁写 |
| ai_courses 与 execution 循环依赖 | execution 模型仅用字符串 FK，完成钩子延迟 import，服务边界单向 |
| aiAdmin.jsx 继续膨胀 | 先拆 tab/组件，再接入新能力 |
| SQLite 与 MySQL 唯一/锁语义不同 | 唯一约束作最终防线，两种数据库并发与迁移测试 |
| 旧 9 题无法自动准确归类 | 过渡期 unit 可空，由管理员明确映射，不根据标题猜测 |
| 关闭小测批量结算阻塞请求 | 只批量标记 settling，不在请求事务内等待 Runner |

## 17. 回滚策略

- 代码层：关闭 `AI_MIXED_QUIZ_ENABLED`，恢复只显示题库练习。
- 数据层：已创建的新表和 nullable 字段保留，不在生产紧急回滚中删除数据。
- API 层：新路由可关闭；旧 problems/submissions/execution 路由保持兼容。
- 发布失败：事务回滚，不留下 open 状态或半份蓝图。
- 前端失败：旧 ProblemDetail 和题库卡片仍可继续使用。
- 数据库 migration backward 只用于无生产数据的验证环境；已有正式 attempt 后不执行破坏性反迁移。

## 18. 文档与交付物

每个实施 Step 需要：

- 更新本 DEV 的完成标记；
- 保存定向测试结果；
- 如接口发生约定内的小幅调整，同步更新 API 示例；
- 对迁移、Runner、发布或权限相关步骤生成简短完成报告；
- 最终更新教师操作说明、部署补偿任务说明和项目状态报告。

## 19. 开工状态

本 DEV 已获用户确认，Step 0–10 已完成；用户确认 9 道存量编程题暂不归类，该过渡状态不阻塞后续实施。下一步进入 Step 11；不得跳过真实 Runner、部署、安全和完整端到端验收。
