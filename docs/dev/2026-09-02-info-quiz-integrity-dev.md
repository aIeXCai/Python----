# 阶段 4：信息课小测可信度 DEV 技术设计

文档日期：2026-09-02
文档状态：用户已确认（2026-09-02）
对应 PRD：`docs/prd/2026-09-02-info-quiz-integrity-prd.md`
前置条件：阶段 4 PRD 已于 2026-09-02 确认
实施状态：已完成并通过 SQLite、MySQL 8.0、前端测试与生产构建验证（2026-09-02）

## 1. 实施目标与不变量

本阶段不重做现有成绩页面。以下学生体验必须保留：

1. 学生提交后立即看到得分、正确题数和总题数。
2. 学生立即看到错题的正确答案和解析。
3. 满分时不显示空的错题区域。

本阶段只替换上述体验背后的不可信实现，并建立以下技术不变量：

1. 作答中的学生响应不含正确答案、解析、原始选项映射或等价信息。
2. 同一学生、同一小测始终只有一条当前有效作答。
3. 题目、显示选项、正确显示选项和解析在开始时形成不可变快照。
4. 服务端时间和截止时间是计时唯一依据。
5. 评分只读取服务端快照，总题数不读取客户端答案数量。
6. 未答题计错，未知题目、非法选项和其他 attempt 标识整体拒绝。
7. 重复或并发开始、保存、提交不会产生重复有效成绩。
8. 题库后续修改或删除不影响已开始试卷和已生成结果。
9. 学生只能访问自己的作答；教师只能管理授权年级。
10. 正式小测作答期间，站内 AI 前后端都拒绝提供对话能力。

## 2. 当前实现基线

### 2.1 已有且必须保留

- `QuizPage` 提交成功后跳转到 `/student/quiz-result/:sessionId`。
- `QuizResult` 显示分数、正确数、错误数和提交时间。
- `QuizResult` 过滤错题并显示正确选项和 `explanation`。
- 教师已有题库、小测配置、发布开关和成绩统计页面。
- 本地开发使用 SQLite，生产目标为 MySQL 8.0。

### 2.2 必须替换的问题

- `QuizDetailView` 每次 GET 都重新随机抽题和打乱选项。
- 详情响应返回 `correct_answer` 与 `shuffled_order`。
- 浏览器把原始答案、显示答案和选项映射一起提交。
- `QuizSubmitView` 用 `len(answers)` 作为评分分母，并跳过非法题目。
- 倒计时只存在 React 内存中，刷新后重置。
- `QuizSubmission` 只保存最终结果，没有进行中状态、服务端截止时间或完整快照。
- 同一学生可以重复提交，列表取最高分而结果页取最新一份，语义不一致。
- 学生年级校验错误使用 `managed_grade`。
- 结果接口重新读取当前 `Question`，题库变更会改变历史结果。
- `QuizPage` 把小测上下文注册给站内 AI，和正式小测规则冲突。

## 3. 总体架构

保留 `QuizSession`、`Question` 和 `QuizSubmission` 三个核心模型。为降低存量迁移和教师统计改造风险，不新增并行的 Attempt 表，而是把 `QuizSubmission` 扩展为完整作答生命周期模型；模型名称暂时保留，业务层统一称为 `attempt`。

```text
教师开放小测
    │
    ▼
学生 POST start ──事务锁──► 创建/恢复当前 QuizSubmission(attempt)
    │                              │
    │                              ├─ 固定试卷 snapshot_json
    │                              ├─ started_at / deadline_at
    │                              └─ status=in_progress
    ▼
前端只收到显示题目，不收到答案与映射
    │
    ├─ PUT answers（全量草稿 + revision）
    ├─ GET attempt（刷新/重登录恢复）
    └─ POST submit（服务端锁行、快照评分、幂等结算）
                                      │
                                      ▼
                            status=submitted/timed_out
                                      │
                                      ▼
                         立即返回得分 + 错题快照解析
```

核心代码分层：

- View：认证、序列化、HTTP 状态码，不实现抽题和评分规则。
- Serializer：请求白名单、类型与字段校验。
- `quiz_services.py`：开始、恢复、保存、结算、关闭和重置的事务边界。
- `quiz_snapshot.py`：抽题、选项打乱、快照生成和学生/结果序列化。
- Model：持久化状态、索引与跨数据库约束。

## 4. 数据模型设计

### 4.1 QuizSession 生命周期

`QuizSession` 新增：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | `CharField(choices=draft/open/closed, db_index=True)` | 小测唯一生命周期状态 |
| `opened_at` | `DateTimeField(null=True)` | 第一次开放时间 |
| `closed_at` | `DateTimeField(null=True)` | 关闭时间 |

最终删除数据库字段 `is_visible`，避免 `status` 与布尔值形成双重真相。为了兼容现有教师前端，API 在阶段 4 内仍返回计算字段 `is_visible = status == "open"`，并暂时接受旧的 `is_visible` 写入格式，由 Serializer 转换成状态迁移。

状态迁移允许：

```text
draft -> open <-> closed
```

- `draft/open/closed` 均可编辑标题、单元、题数、难度分配、时限和可见年级/班级。
- 已开始 attempt 始终使用原快照和截止时间；编辑后的配置只用于之后新开始的 attempt。
- `closed` 可重新开放；重新开放会更新 `opened_at` 并清空 `closed_at`。
- 关闭时同步结算所有 `in_progress` attempt。

### 4.2 QuizSubmission 扩展为 attempt

保留现有表名和整数主键，新增或调整字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | `CharField` | `in_progress/submitted/timed_out/reset/superseded` |
| `attempt_no` | `PositiveIntegerField` | 同一学生同一小测的作答序号，从 1 开始 |
| `current_marker` | `BooleanField(null=True)` | 当前有效行为 `True`，历史行为 `NULL` |
| `snapshot_version` | `PositiveSmallIntegerField(default=0)` | `0` 为旧数据，阶段 4 新快照为 `1` |
| `snapshot_json` | `JSONField(null=True, blank=True)` | 不可变试卷与答案快照 |
| `started_at` | `DateTimeField(null=True)` | 服务端开始时间 |
| `deadline_at` | `DateTimeField(null=True)` | 无时限小测为 `NULL` |
| `submitted_at` | 改为 `DateTimeField(null=True)` | 首次成功结算时间，不再 `auto_now_add` |
| `updated_at` | `DateTimeField(auto_now=True)` | 草稿或状态最近更新时间 |
| `answer_revision` | `PositiveIntegerField(default=0)` | 乐观并发版本号 |
| `score` | 改为可空 | 作答中为 `NULL` |
| `correct_count` | 改为可空 | 作答中为 `NULL` |
| `total_count` | 改为可空 | 作答中为 `NULL` |
| `grade` | 保留 | 开始时的学生年级快照 |
| `class_num_snapshot` | `CharField` | 开始时的班级快照 |
| `student_number_snapshot` | `CharField` | 开始时的学号快照 |
| `reset_at` | `DateTimeField(null=True)` | 教师重置时间 |
| `reset_by` | `ForeignKey(CustomUser, SET_NULL, null=True)` | 执行重置的教师 |
| `reset_reason` | `CharField(max_length=300, blank=True)` | 重置原因 |

`answers_json` 保留为 TextField，避免对旧数据执行高风险 Text-to-JSON 原地转换：

- 旧记录继续保存原结构。
- 新 attempt 只保存 `{item_id: "A"|"B"|"C"|"D"}` 的显示选项。
- 读写统一经过服务函数，使用稳定排序和紧凑 JSON 编码。

数据库约束：

1. `UniqueConstraint(user, session, attempt_no)`。
2. `UniqueConstraint(user, session, current_marker)`。
3. `current_marker` 只允许 `TRUE` 或 `NULL`；一个学生/小测只能有一个 `TRUE`，历史记录使用可重复的 `NULL`。SQLite 和 MySQL 都允许唯一索引中存在多个 `NULL`。
4. `status in (in_progress, submitted, timed_out, reset, superseded)`。
5. 索引：`(user, session, current_marker)`、`(session, status)`、`(status, deadline_at)`、`(grade, session)`。

### 4.3 快照 JSON 结构

```json
{
  "schema_version": 1,
  "session_title": "第一单元小测",
  "question_count": 2,
  "questions": [
    {
      "item_id": "a5f5d51a-...",
      "source_question_id": 31,
      "position": 1,
      "text": "题干",
      "category": "知识点",
      "difficulty": "easy",
      "options": {
        "A": "显示选项一",
        "B": "显示选项二",
        "C": "显示选项三",
        "D": "显示选项四"
      },
      "correct_option": "C",
      "explanation": "解析"
    }
  ]
}
```

规则：

- `item_id` 使用随机 UUID 字符串，是学生提交时唯一允许使用的题目标识。
- `source_question_id`、`correct_option` 和 `explanation` 只保存在服务端，作答序列化器绝不返回。
- 快照生成后禁止修改；保存草稿只更新 `answers_json` 和 `answer_revision`。
- 结果页只从快照读取文本、选项、正确答案和解析，不再查询 `Question`。
- 快照不写普通日志，不进入学生错误响应。

### 4.4 旧数据归档规则

数据迁移按 `(user_id, session_id, submitted_at, id)` 排序：

- 每组最新一条旧 `QuizSubmission` 标记为 `submitted + current_marker=True`。
- 更早记录标记为 `superseded + current_marker=NULL`。
- `attempt_no` 按时间递增回填。
- `snapshot_version=0`，`started_at=submitted_at`，保留原成绩和 `answers_json`。
- 有旧提交的不可见小测迁移为 `closed`；可见小测迁移为 `open`；无提交且不可见迁移为 `draft`。

旧结果仅在题目仍存在且 `Question.updated_at <= submitted_at` 时按旧 payload 尝试还原；否则只返回成绩摘要，并设置：

```json
{
  "legacy_record": true,
  "analysis_available": false
}
```

不得使用已修改题目伪造历史解析。旧记录仍保留在教师历史查询中，但 `superseded` 不计入当前成绩统计。

## 5. 权限设计

### 5.1 权限类

在 `info_tech/permissions.py` 集中定义：

- `IsStudent`：已认证且 `role == "student"`。
- 复用 `users.permissions.IsTeacher`：已认证且 `role == "teacher"`。

学生小测接口不再只使用 `IsAuthenticated`。教师接口逐步替换散落的手工角色判断，至少覆盖本阶段修改的小测、成绩和重置接口。

### 5.2 年级范围

- 学生可见性只使用 `request.user.grade`。
- `visible_grades=[]` 继续表示所有学生年级可见，但普通教师只能选择自己 `managed_grade`；超级管理员可跨年级。
- 教师只能管理自己创建且目标年级属于 `managed_grade` 的小测；超级管理员不受此限制。
- attempt 查询始终附加 `user=request.user`，不先查询再比较，避免泄露记录存在性。
- 无权访问统一返回 403 和通用信息；不存在返回 404。

## 6. 领域服务与事务

### 6.1 `start_or_resume_attempt(user, session_id)`

事务步骤：

1. `select_for_update()` 锁定学生和 `QuizSession`。
2. 校验学生角色、`user.grade`、小测 `status=open` 和题库容量。
3. 查询 `current_marker=True` 的 attempt。
4. 若为 `in_progress`，先执行惰性超时判断；未超时则直接恢复。
5. 若已结算，将其 `current_marker` 置空并保留为历史记录。
6. 若没有进行中的当前 attempt，重新抽题及打乱选项，生成完整快照、计算截止时间并创建 `attempt_no=max+1`。
7. 捕获并发唯一约束冲突，重新读取当前 attempt 后返回。

SQLite 的 `select_for_update()` 不能提供与 MySQL 相同的行锁语义，因此唯一约束是最终防线；MySQL 使用 InnoDB 行锁。两种数据库都必须通过重复开始测试。

### 6.2 `save_answers(user, session_id, attempt_id, revision, answers)`

请求提交完整答案状态，不提交增量 patch：

1. 锁定本人当前 attempt。
2. 若已超过 `deadline_at`，拒绝新答案；超过宽限期时先按已保存草稿结算。
3. 校验状态必须为 `in_progress`。
4. 校验 `attempt_id`、`revision`、所有 `item_id` 和 A-D 选项。
5. `revision` 不一致返回 409，不用旧标签页静默覆盖新数据。
6. 原子写入规范化答案并令 `answer_revision += 1`。

### 6.3 `settle_attempt(..., reason, final_answers=None)`

所有手动提交、超时、教师关闭都调用同一结算函数：

1. 在事务中锁定当前 attempt。
2. 如状态已经是 `submitted/timed_out`，直接返回已存结果，实现幂等。
3. 手动提交且请求到达时间不晚于 `deadline_at + 5 秒` 时，可使用校验后的 `final_answers`。
4. 超过宽限、教师关闭或没有 final payload 时，使用最后成功保存的 `answers_json`。
5. 遍历快照的全部题目；缺少答案计错。
6. `score = round(correct_count / snapshot_question_count * 100, 1)`。
7. 一次性保存最终答案、分数、计数、状态和 `submitted_at`。

教师关闭不使用 5 秒宽限；关闭事务开始后的新保存和提交全部拒绝。

### 6.4 惰性超时

阶段 4 不引入 Celery、Redis 或常驻任务。以下入口都会调用 `settle_expired_attempts()`：

- 学生恢复、保存、提交、查看结果或刷新小测列表。
- 教师查看该小测统计。
- 教师关闭小测。

因此即使浏览器在倒计时结束时离线，下一次读取仍会按截止时已保存草稿得到同一结果。数据库中暂时保留的过期 `in_progress` 不代表还能继续答题，任何写入口都先比较服务端时间。

### 6.5 `reset_attempt(teacher, session_id, student_id, reason)`

1. 校验教师角色、创建者和管理年级。
2. 锁定当前 attempt。
3. 只允许在小测仍为 `open` 时重置；关闭后如需补测应复制小测。
4. 将旧记录改为 `reset`、`current_marker=NULL`，写入教师、时间和原因。
5. 不立即创建新 attempt；学生下次点击开始时获得 `attempt_no+1`。
6. 不删除旧快照、答案和成绩。

## 7. 学生 API 契约

所有时间使用 ISO 8601 UTC 输出；前端只负责本地化显示。错误响应保持现有 `error` 字符串并新增稳定 `code`：

```json
{"error": "作答版本已变化，请重新加载", "code": "attempt_revision_conflict"}
```

### 7.1 GET `/api/info/quizzes/`

返回当前学生年级可见的小测及动作状态：

```json
{
  "id": 7,
  "title": "第一单元小测",
  "status": "open",
  "num_questions": 10,
  "time_limit": 20,
  "attempt_status": "not_started",
  "score": null,
  "action": "start"
}
```

学生列表只返回 `open` 小测；`action` 为 `start/continue/restart`。`restart` 同时提供“查看成绩”和“再做一次”，分数为最近一次已完成成绩而非最高分。

### 7.2 POST `/api/info/quizzes/<session_id>/attempt/`

开始或幂等恢复。新建返回 201，恢复返回 200：

```json
{
  "attempt_id": 123,
  "status": "in_progress",
  "revision": 2,
  "server_time": "2026-09-02T01:00:00Z",
  "started_at": "2026-09-02T00:50:00Z",
  "deadline_at": "2026-09-02T01:10:00Z",
  "remaining_seconds": 600,
  "saved_answers": {"item-uuid": "B"},
  "quiz": {"id": 7, "title": "第一单元小测", "num_questions": 10},
  "questions": [
    {"item_id": "item-uuid", "position": 1, "text": "题干", "category": "知识点", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}}
  ]
}
```

响应明确禁止 `source_question_id/correct_option/explanation/shuffled_order`。

### 7.3 GET `/api/info/quizzes/<session_id>/attempt/`

只恢复，不创建。响应与 7.2 相同；无当前记录返回 404；已结算返回 409 + `attempt_completed` 和结果地址。

### 7.4 PUT `/api/info/quizzes/<session_id>/attempt/answers/`

请求：

```json
{
  "attempt_id": 123,
  "revision": 2,
  "answers": {"item-uuid": "B"}
}
```

成功返回新 revision、规范化已保存答案、服务端时间与剩余秒数。旧 revision 返回 409；已提交返回 409；超时返回 410，并附 `result_available`。

### 7.5 POST `/api/info/quizzes/<session_id>/attempt/submit/`

请求与保存接口相同。首次结算和重复请求都返回 200；重复请求返回同一 `attempt_id` 和同一成绩，不新增记录：

```json
{
  "attempt_id": 123,
  "status": "submitted",
  "score": 80.0,
  "correct_count": 8,
  "total_count": 10,
  "submitted_at": "2026-09-02T01:02:00Z",
  "result_url": "/api/info/quizzes/7/result/"
}
```

### 7.6 GET `/api/info/quizzes/<session_id>/result/`

保留当前页面依赖的顶层字段，并把 `question_results` 改为只返回错题快照：

```json
{
  "submission_id": 123,
  "quiz_title": "第一单元小测",
  "score": 80.0,
  "correct_count": 8,
  "total_count": 10,
  "submitted_at": "2026-09-02T01:02:00Z",
  "question_results": [
    {
      "item_id": "item-uuid",
      "text": "题干",
      "user_answer": "B",
      "correct_answer": "C",
      "is_correct": false,
      "explanation": "解析",
      "options": {
        "A": {"text": "...", "is_user_answer": false, "is_correct_answer": false},
        "B": {"text": "...", "is_user_answer": true, "is_correct_answer": false},
        "C": {"text": "...", "is_user_answer": false, "is_correct_answer": true},
        "D": {"text": "...", "is_user_answer": false, "is_correct_answer": false}
      }
    }
  ]
}
```

未答题使用 `user_answer: null`。作答中访问返回 409，不能借结果接口提前获取答案。

### 7.7 旧接口处置

- `GET /api/info/quizzes/<id>/` 仅保留无答案的小测元数据，不再创建或返回随机试卷。
- `POST /api/info/quizzes/<id>/submit/` 停止接受旧的答案映射 payload，返回 410 + `quiz_api_upgraded`。
- 前后端在同一阶段发布，避免旧前端继续调用不可信协议。

## 8. 教师 API 与统计

### 8.1 状态迁移

新增：

```text
PATCH /api/admin/info/sessions/<id>/status/
body: {"status": "open"|"closed"}
```

- `open` 前执行题数、难度、单元、年级和题库容量预检。
- `closed` 原子更新状态，再结算进行中的 attempt。
- 旧 `toggle` 接口阶段内兼容：`true -> open`；`false -> closed`。已关闭小测允许恢复为 `open`，但不能恢复为 `draft`。

### 8.2 重置学生作答

```text
POST /api/admin/info/sessions/<session_id>/students/<student_id>/reset/
body: {"reason": "机房电脑故障"}
```

成功返回旧 attempt ID、重置时间和学生下次可开始状态。请求必须二次确认由前端完成，后端强制要求非空原因。

### 8.3 统计口径

- 当前成绩按学生和小测取 `status IN (submitted, timed_out)` 中 `attempt_no` 最大的一条；新 attempt 尚在作答时仍保留上一条已完成成绩。
- `reset/superseded/in_progress` 不进入平均分、最高分、最低分和提交人数。
- 题目错误率从 `snapshot_json + answers_json` 计算，不读取当前题库。
- 未答题进入题目分母并计错。
- 教师详情增加未开始、作答中、已提交、已超时、已重置人数。
- 历史记录单独查询，不和当前成绩混合。

## 9. 前端设计

### 9.1 API 层

`frontend/src/api/info.js`：

- 新增 `startInfoQuizAttempt`、`getInfoQuizAttempt`、`saveInfoQuizAnswers`、`submitInfoQuizAttempt`。
- `submitInfoQuiz` 不再发送原始答案和 `shuffled_orders`。
- 所有非 2xx 响应先解析 `code/error` 后抛出，避免把错误 JSON 当成功数据。

### 9.2 QuizPage

- 首次进入调用 start；刷新时由 start 幂等恢复同一 attempt。
- 删除 `shuffledOrders` 和浏览器还原原始字母逻辑。
- `answers` 使用 `item_id -> 显示字母`。
- 选择答案后 400ms debounce 保存完整答案，并展示“保存中/已保存/保存失败”。
- 保存请求带 `revision`；409 时停止自动覆盖并提示重新加载。
- 提交前取消 debounce、等待在途保存，再提交本地完整答案。
- 倒计时根据 `server_time/deadline_at` 计算时钟偏移，每秒仅更新显示，不自行延长截止时间。
- 到 0 时立即尝试提交；离线时显示等待结算，恢复网络后读取结果。
- 已提交、超时或关闭状态不可编辑。

### 9.3 QuizResult

保留现有得分圆环、正确/错误数和错题解析布局，只做数据适配：

- 支持 `item_id` 作为 React key。
- 未答题显示“未作答”。
- 正确答案和学生选择均按显示字母高亮。
- 小测为 `open` 时同时显示“返回列表”和“再做一次”；为 `closed` 时只显示“返回列表”。
- 旧记录没有可靠解析时显示“历史成绩可查看，逐题解析不可还原”。

### 9.4 学生列表

- 按 `action` 显示“开始小测/继续作答/查看成绩/再做一次”。
- 不显示最高分，显示最近一次已完成成绩。
- 新一轮作答中显示“作答中”；教师端仍保留上一轮已完成成绩，直到本轮提交后替换。

### 9.5 站内 AI 禁用

前端用于清晰反馈，后端用于真正强制：

- `ChatContext` 增加禁用状态与原因；QuizPage 挂载时关闭悬浮窗并禁用，卸载时恢复。
- `FloatingChat` 在禁用时隐藏入口。
- `chat` 发送接口检查用户是否存在未过截止宽限的当前 `in_progress` 信息课 attempt；存在时返回 403 + `quiz_in_progress`。
- 历史会话读取不改变成绩，也不向小测注入上下文；正式作答页不再注册 `info_quiz` context。

### 9.6 教师页面

- 小测状态展示为“未发布/进行中/已关闭”。
- 已关闭状态提供“重新开放”；关闭后学生列表不再返回该小测。
- 所有状态均提供配置编辑；已有作答不随配置改变。
- 关闭前提示未提交作答会按已保存草稿结算。
- 学生成绩行增加“重置本次作答”，要求确认并填写原因。

## 10. Migration 设计

### 10.1 `0004_quiz_attempt_lifecycle`

1. 给 `QuizSession` 添加 `status/opened_at/closed_at`。
2. 给 `QuizSubmission` 添加 attempt、快照、时间、revision、重置和学生信息快照字段。
3. 把分数、计数和 `submitted_at` 改为可空。
4. `RunPython` 分批回填小测状态、attempt 编号、当前标记和旧记录状态。
5. 回填完成后添加唯一约束、检查约束和索引。

迁移函数使用历史模型，不导入运行时 model；按主键分批处理，避免一次加载所有答案。

### 10.2 `0005_remove_quizsession_is_visible`

- 删除数据库 `is_visible` 字段。
- API 兼容字段由 Serializer 计算，不再落库。
- 更新 admin、测试工厂、迁移导出/校验工具的字段摘要。

### 10.3 迁移验证

必须覆盖：

1. 空库从 0001 迁移到最新。
2. 有可见/不可见小测、单次/多次旧提交的 SQLite 升级。
3. 同一数据集导入 MySQL 8.0 后升级。
4. 每组只有一个 `current_marker=True`。
5. 所有旧成绩、答案原文、提交时间和教师统计历史数量可核对。
6. 回滚演练只回到备份，不依赖不可逆地把新 attempt 降级成旧 payload。

## 11. 测试矩阵

| 类别 | 关键用例 |
|---|---|
| Model/Migration | 状态回填、attempt_no、唯一当前记录、多 NULL 唯一索引、旧成绩不丢失 |
| 抽题快照 | 题数固定、无重复、难度补位、选项打乱、题库不足失败 |
| 答案泄露 | 列表/start/resume/save 响应递归扫描禁用字段和值 |
| 开始并发 | 同一用户并发 10 次只生成一个当前 attempt |
| 刷新恢复 | 10 次恢复的 item、顺序、选项和 deadline 完全一致 |
| 草稿 | 保存成功、未知 item、非法选项、旧 revision、不同标签页冲突 |
| 计时 | 改客户端时钟无效、截止后保存拒绝、5 秒提交宽限、宽限后按草稿结算 |
| 评分 | 10 题只答对 1 题得 10 分、空答 0 分、题外答案整体拒绝 |
| 提交幂等 | 连点、网络重试和并发提交只保留一份结果 |
| 结果 | 提交后立即得分与错题解析、未提交不可读、未答题列为错题 |
| 快照稳定 | 修改/删除 Question 后试卷、评分和解析不变 |
| 权限 | 学生角色、年级、他人 attempt、教师跨年级和非创建者管理全部拒绝 |
| 状态 | draft/open/closed 合法迁移、全状态安全编辑、关闭批量结算 |
| 重置 | 审计字段、旧记录保留、新 attempt_no、其他学生不受影响 |
| 统计 | 只统计当前已结算、未答计错、题目统计来自快照 |
| AI | 前端隐藏、直接调用 chat send 也被拒绝、结算后恢复 |
| 前端 | 自动保存状态、计时偏移、提交跳转、得分与错题解析回归 |
| 双数据库 | SQLite 与 MySQL 8.0 migration、唯一约束和并发行为 |

测试文件规划：

- 扩展 `backend/info_tech/tests_student_quiz.py`。
- 新增 `backend/info_tech/tests_quiz_services.py`。
- 新增 `backend/info_tech/tests_quiz_migrations.py`。
- 扩展 `backend/info_tech/tests.py` 或拆分教师状态/重置测试。
- 扩展 `backend/chat/tests.py` 的小测期间拒绝用例。
- 重写 `frontend/src/pages/student/info/QuizPage.test.jsx` 的 attempt、保存和计时场景。
- 扩展 `frontend/src/pages/student/info/QuizResult.test.jsx`，锁定立即得分与错题解析。
- 扩展 `frontend/src/contexts/ChatContext.test.jsx` 与 `FloatingChat.test.jsx`。

并发测试使用 `TransactionTestCase` 和独立数据库连接；SQLite 验证唯一约束兜底，MySQL 集成测试验证 InnoDB 行锁路径。

## 12. 文件改动清单

### 12.1 新增

- `backend/info_tech/permissions.py`
- `backend/info_tech/quiz_services.py`
- `backend/info_tech/quiz_snapshot.py`
- `backend/info_tech/migrations/0004_quiz_attempt_lifecycle.py`
- `backend/info_tech/migrations/0005_remove_quizsession_is_visible.py`
- `backend/info_tech/tests_quiz_services.py`
- `backend/info_tech/tests_quiz_migrations.py`
- `frontend/src/contexts/ChatContext.test.jsx`

### 12.2 修改

- `backend/info_tech/models.py`
- `backend/info_tech/admin.py`
- `backend/info_tech/serializers.py`
- `backend/info_tech/views_student.py`
- `backend/info_tech/views.py`
- `backend/info_tech/urls_student.py`
- `backend/info_tech/urls.py`
- `backend/info_tech/tests_student_quiz.py`
- `backend/info_tech/tests.py`
- `backend/chat/views.py`
- `backend/chat/tests.py`
- `backend/platform_ops/migration_data.py`
- `backend/platform_ops/management/commands/verify_platform_migration.py`
- `backend/platform_ops/tests/test_migration_data.py`
- `frontend/src/api/info.js`
- `frontend/src/pages/student/info/QuizPage.jsx`
- `frontend/src/pages/student/info/QuizPage.test.jsx`
- `frontend/src/pages/student/info/QuizResult.jsx`
- `frontend/src/pages/student/info/QuizResult.test.jsx`
- `frontend/src/pages/student/StudentDashboard.jsx`
- `frontend/src/pages/student/StudentDashboard.test.jsx`
- `frontend/src/contexts/ChatContext.jsx`
- `frontend/src/components/FloatingChat.jsx`
- `frontend/src/components/FloatingChat.test.jsx`
- `frontend/src/pages/teacher/InfoAdmin.jsx`
- `frontend/src/pages/teacher/InfoAdmin.test.jsx`
- `frontend/src/pages/teacher/tabs/Tab2Sessions.jsx`
- `frontend/src/pages/teacher/tabs/Tab2Sessions.test.jsx`
- `frontend/src/pages/teacher/tabs/Tab3Stats.jsx`
- `frontend/src/pages/teacher/tabs/Tab3Stats.test.jsx`
- `docs/2026-09-01-alicloud-deployment-roadmap.md`

## 13. 实施步骤

### Step 1：回归护栏与模型迁移（已完成）

- 先补充“提交后立即显示得分与错题解析”的前端回归测试。
- 编写 0004/0005 migration 和迁移测试。
- 扩展模型、admin、数据库导出与校验工具。
- 在 SQLite 和 MySQL 8.0 执行存量升级演练。

### Step 2：快照与领域服务（已完成）

- 实现抽题/选项快照生成器和安全序列化器。
- 实现开始、恢复、保存、结算、惰性超时、关闭和重置服务。
- 完成事务、幂等、并发和评分单元测试。

### Step 3：学生 API（已完成）

- 接入 `IsStudent` 和 `user.grade` 年级校验。
- 实现 attempt、草稿和新提交接口。
- 结果接口改为快照读取并保留即时反馈字段。
- 废止旧不可信提交协议。

### Step 4：学生前端与 AI 禁用（已完成）

- 改造 API 层、QuizPage、Dashboard 和 QuizResult。
- 实现服务端时间倒计时、自动保存、冲突提示和恢复。
- 前端隐藏 AI，后端拒绝作答中的 chat send。
- 删除学生自行重新作答入口。

### Step 5：教师状态、重置与统计（已完成）

- 接入 draft/open/closed 状态迁移。
- 实现单学生重置与审计。
- 教师统计切换到当前有效 attempt 与快照口径。
- 补齐教师权限、关闭结算和统计测试。

### Step 6：全量验证与文档收尾（已完成）

- 后端全量测试、前端 Vitest、ESLint 和生产构建。
- SQLite/MySQL 8.0 双数据库回归。
- 执行答案泄露扫描、手工刷新/断网/超时/重复提交验收。
- 更新路线图与阶段 4 完成报告。

## 14. 验证命令与人工验收

实施后至少运行：

```bash
cd backend
python manage.py makemigrations --check
python manage.py test info_tech chat
python manage.py test

cd ../frontend
npm test
npm run lint
npm run build
```

MySQL 集成验证继续复用阶段 2 的隔离实例和 migration 工具，不在命令或文档中写入真实密码。

人工验收主链路：

1. 教师创建草稿并开放小测。
2. 学生开始，检查网络响应没有答案/解析/映射。
3. 作答部分题目，看到“已保存”，刷新并恢复同一试卷和倒计时。
4. 修改客户端时间，确认服务端截止时间不变。
5. 提交后立即看到准确得分和错题正确答案、解析。
6. 修改题库后再次查看结果，内容保持不变。
7. 学生提交后可直接开始第二个 attempt，并获得重新抽题和打乱后的新快照。
8. 跨学生、跨年级和直接调用 chat send 均被拒绝。
9. 教师关闭小测，未提交学生按已保存草稿结算。

## 15. 回滚与故障处理

### 15.1 实施前

- 使用阶段 2 工具生成 SQLite 文件备份、规范化导出和摘要。
- MySQL 演练前生成独立数据库备份。
- 记录 migration 版本、数据行数和摘要。

### 15.2 migration 失败

- 停止应用写入。
- 不手工删除约束或改写 attempt 数据。
- 恢复迁移前备份，再修正迁移脚本并重新演练。

### 15.3 上线后需回退

新 attempt 无法无损转换回旧的客户端答案映射协议，因此不执行仅回退代码的半回滚。应同时回退代码和数据库备份；如需保留故障期间产生的成绩，先导出只读审计副本，再恢复正式库。

### 15.4 单个学生故障

不直接删除提交记录、不修改分数。教师通过重置接口保留旧 attempt 和审计，再让学生重新开始。

## 16. 已知取舍

1. 不引入后台任务，因此无人再次访问时，过期 attempt 可能暂时保持 `in_progress`；所有读写入口都会在使用前一致结算，不影响实际权限与分数。
2. 快照使用 JSONField，教师题目统计需要在应用层解析；以当前最多约 150 名并发和单选小测规模可接受。
3. 保留模型名 `QuizSubmission` 可减少迁移风险，但领域含义已扩展为 attempt；未来如需要独立考试服务再做表重命名。
4. 提交后立即公开错题答案可能被学生转告仍在作答的同学，这是用户确认保留的教学体验，本阶段不改为延迟公开。
5. 关闭后允许重新开放；重新开放不解锁结构配置，也不会改写已结算历史成绩。

## 17. DEV 确认项

确认本 DEV 即表示同意：

1. 在现有 `QuizSubmission` 表上扩展 attempt 生命周期，不创建平行成绩表。
2. 使用 `snapshot_json` 保存不可变试卷，学生作答接口通过白名单隐藏答案。
3. 小测采用 `draft -> open <-> closed` 状态，各状态均可编辑，已有 attempt 由不可变快照隔离。
4. 学生在开放期间可不限次数作答；教师成绩显示最近一次已完成记录，教师仍可审计重置异常作答。
5. 服务端自动保存草稿，使用 revision 处理多标签页冲突。
6. 截止后 5 秒内允许首次手动提交；之后按最后保存草稿结算。
7. 保留提交后立即显示得分和错题解析，不改为延迟公开。
8. 正式作答期间前端隐藏 AI，同时后端拒绝直接发送 AI 消息。
9. 旧多次提交完整保留；迁移时建立 attempt 序号，运行时成绩按最近一次已完成记录统计。

本 DEV 已于 2026-09-02 经用户确认，并于同日完成 Step 1 至 Step 6。验证证据见 `docs/reports/2026-09-02-stage-4-completion.md`。

> 2026-09-02 实测修订：实现不限次数新 attempt、最近一次已完成成绩口径、关闭后学生列表隐藏，以及教师重新开放。该修订不新增数据库迁移。
