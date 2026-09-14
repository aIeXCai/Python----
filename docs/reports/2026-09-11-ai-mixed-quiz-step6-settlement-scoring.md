# AI 混合题库 Step 6 验收报告

报告日期：2026-09-11
对应 DEV：`docs/dev/2026-09-11-ai-mixed-question-bank-quiz-dev.md`
实施范围：Step 6（交卷、超时、关闭与综合计分）

## 1. 已完成能力

- 主动交卷原子保存最终选择题答案并把 attempt 锁定为 `settling`，锁卷后不再允许保存答案或创建运行/评测任务。
- 重复交卷幂等返回已有结算状态和结果，不重复计算、不增加结果版本。
- 服务端截止时间到达后使用最后一次成功保存的选择题答案，以 `timed_out` 原因结算。
- 教师关闭小测后，对仍在作答的当前 attempt 批量请求 `closed` 结算；已主动交卷或已超时的结算原因不被覆盖。
- 截止或锁卷前已经受理的正式 grade 任务可以继续完成；attempt 保持 `settling`，Runner 回写后自动触发幂等结算。
- 选择题只按个人冻结快照中的展示答案判分，未答计错；结果完成前不返回正确答案或解析。
- 编程题按 attempt/item 查询 `counts_for_quiz=True` 且有有效分数的 Submission，取最高分；同分优先最早完成记录。
- 使用 `Decimal` 按题目分值折算，选择题分项、编程题分项和总分统一量化到 1 位小数。
- 没有提交的编程题按 0 分处理但不记系统异常；只有系统错误或任务取消且无有效成绩时增加 `grading_issue_count`。
- 学生结果提供分项成绩、选择题判定/解析、编程题最高原始分与折算分；`result_revision` 支持识别系统重评更新。
- 教师可重置开放小测中的当前 attempt，旧 attempt 保留为 `reset`，学生再次开始时生成递增的 attempt。
- 教师只可对系统异常且没有有效成绩的编程 item 发起重评；重评复用原代码和发布时冻结测试点，支持 UUID 幂等。
- Runner 完成钩子使用 `transaction.on_commit()` 延迟调用，钩子异常只记录日志，不改变 Runner 已成功回执。
- 新增幂等补偿命令 `python manage.py settle_ai_quiz_attempts`，先恢复/取消过期执行任务，再处理超时和遗留 `settling` attempt。

本步复用 Step 4–5 已建立的字段和约束，不需要新增数据库迁移。

## 2. 新增接口

学生端：

- `POST /api/ai/quizzes/{id}/attempt/submit/`
- `GET /api/ai/quizzes/{id}/result/`
- `GET /api/ai/quizzes/{id}/attempts/`

教师端：

- `POST /api/ai/admin/quizzes/{id}/attempts/{attempt_id}/reset/`
- `POST /api/ai/admin/quizzes/{id}/attempts/{attempt_id}/items/{item_id}/regrade/`

关闭接口 `/api/ai/admin/quizzes/{id}/close/` 已扩展为关闭后触发批量结算。学生本人已完成的小测在关闭后仍可出现在列表中并读取结果，其他学生数据不可访问。

## 3. 计分规则

- 选择题得分：`选择题总分 × 答对数 ÷ 选择题数量`。
- 单道编程题得分：`该题配置分值 × 本 attempt/item 最高有效原始分 ÷ 100`。
- 编程题分项为各编程题折算分之和，总分为选择题分项与编程题分项之和。
- 各分项最终按 `ROUND_HALF_UP` 量化到 1 位小数。
- 评测系统错误不生成学生原始分；结果页单独标识为 `system_issue`，教师可重评。

## 4. 验证结果

- Step 6 定向测试：10 项通过，1 项 MySQL/InnoDB 真并发测试在当前 SQLite 环境跳过。
- AI 课程 + Execution 全量回归：251 项通过，4 项按环境跳过。
- Django system check：通过。
- Migration check：无遗漏变更。
- `git diff --check`：通过。
- 本地真实补偿命令：成功执行，无待结算 attempt。
- 运行中后端真实结果路由检查：返回规范 JSON 401，说明新路由已加载且认证层正常。

测试覆盖纯选择、纯编程、混合试卷；最高分折算；重复交卷；revision；截止前受理、截止后完成；Runner 自动结算；关闭结算；系统异常；重评幂等；重置再答；补偿命令；本人历史与跨学生隔离。并发交卷使用 MySQL/InnoDB 集成用例保证最终只产生一个结果版本。

## 5. 存量兼容

- 当前本地数据库仍有 9 道 AI 编程题、9 条历史 Submission、0 条 AIQuizAttempt、0 条 ExecutionTask。
- 9 道存量编程题继续保持未归类，没有自动归类或修改。
- 旧题库练习的运行、评测、成绩和 Runner 协议均未改变。
- 小测结果只读取带 attempt/item 上下文的正式 Submission，不会把旧练习提交混入小测成绩。

## 6. 下一步边界

Step 7 开始教师端题库 UI：拆分 AI 管理区域，完成单元管理、选择题 CRUD/导入和编程题归类筛选。Step 8 实现教师自由组卷 UI，Step 9 才接入学生混合作答与结果页面；因此本步新增能力目前以 API 为主。
