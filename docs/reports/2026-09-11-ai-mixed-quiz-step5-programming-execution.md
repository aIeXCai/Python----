# AI 混合题库 Step 5 验收报告

报告日期：2026-09-11
对应 DEV：`docs/dev/2026-09-11-ai-mixed-question-bank-quiz-dev.md`
实施范围：Step 5（小测编程运行与评测集成）

## 1. 已完成能力

- Migration `ai_courses.0010` 为 `Submission` 增加 `quiz_attempt`、`quiz_item_id`、`regrade_of` 和 `counts_for_quiz`。
- Migration `execution.0003` 为 `ExecutionTask` 增加 `quiz_attempt` 和 `quiz_item_id`。
- 两张表均使用成对上下文约束，禁止只写 attempt 或只写 item，并增加 attempt/item 联合索引。
- 旧题库练习继续使用原 `enqueue_run()` / `enqueue_grade()`，函数签名和空小测上下文均未改变。
- 新增服务端可信 `enqueue_quiz_run()` / `enqueue_quiz_grade()`；客户端不能传入测试点或快照哈希。
- 正式评测只读取 session 首次发布蓝图中的 `test_snapshot`，并在入队前校验蓝图 hash、attempt 快照关联、题目关联和测试快照 hash。
- run、grade 均绑定当前学生、当前 attempt 和指定编程 item；跨学生 attempt、过期 attempt、未知 item、关闭小测和截止时间均在入队前拒绝。
- 小测任务复用已有 UUID 幂等、用户运行/排队容量限制和安全任务响应白名单。
- 多道编程题分别创建任务和 Submission；题目详情按当前 attempt/item 汇总最高有效提交分，为 Step 6 综合计分提供稳定数据。
- Runner 领取任务的 envelope 和 Runner 程序未改动。

## 2. 新增学生接口

- `GET /api/ai/quizzes/{id}/attempt/items/{item_id}/`
- `POST /api/ai/quizzes/{id}/attempt/items/{item_id}/run/`
- `POST /api/ai/quizzes/{id}/attempt/items/{item_id}/submit/`
- `GET /api/ai/quizzes/{id}/attempt/items/{item_id}/executions/active/`

run/submit 请求显式携带 `attempt_id`；active 查询携带 `attempt_id` 和 `task_type`，避免旧页面或旧 attempt 将任务错误关联到当前作答。题目详情响应不包含来源题号、测试快照、测试快照 hash 或测试点。

## 3. 验证结果

- Step 5 定向测试：8 项全部通过。
- AI 课程 + Execution 全量回归：240 项通过，3 项按当前非 MySQL 环境跳过。
- 冻结快照结构校验加固后再次执行 Step 5 + Execution 回归：49 项通过，2 项按环境跳过。
- Django system check：通过。
- Migration check：无遗漏变更。
- 本地数据库迁移：`ai_courses.0010` 与 `execution.0003` 均已成功应用。
- 运行中后端真实路由检查：新 run 路径返回规范 JSON 401，说明路由已加载且认证层正常工作。
- `git diff --check`：通过。

定向测试覆盖冻结测试点不随题库修改漂移、run 幂等、活动任务刷新恢复、多编程题独立提交、跨 attempt/item 拒绝、截止前置校验、与旧练习共享容量，以及通用任务详情继续隐藏代码和测试点。

## 4. 存量兼容

- 迁移前后 AI 编程题均为 9 道，Submission 均为 9 条，ExecutionTask 均为 0 条。
- 9 道存量编程题继续保持未归类，没有自动归类或修改。
- 新增小测上下文字段对历史 Submission/ExecutionTask 可空，不迁移、不伪造历史归属。
- 正式小测 Submission 使用独立 attempt/item 上下文；旧练习成绩口径不受影响。

## 5. 下一步边界

Step 6 实现主动交卷、超时/关闭结算、等待已受理评测完成、选择题与编程题 Decimal 折算、综合成绩、系统异常重评和最终结果接口。Step 5 只负责可靠地产生并恢复小测编程任务与成绩原始记录，不提前锁卷或计算总分。
