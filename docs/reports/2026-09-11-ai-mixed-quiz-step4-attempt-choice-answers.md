# AI 混合题库 Step 4 验收报告

报告日期：2026-09-11
对应 DEV：`docs/dev/2026-09-11-ai-mixed-question-bank-quiz-dev.md`
实施范围：Step 4（Attempt、个人快照与选择题作答后端）

## 1. 已完成能力

- Migration 0009 创建 `AIQuizAttempt`，包含状态、当前作答标记、不可变个人快照、答案 revision、服务端截止时间、身份快照和后续结算字段。
- 数据库约束确保同一学生/小测/作答序号唯一，且同一学生同一小测最多只有一条 `current_marker=True` 的当前作答。
- 学生小测列表只返回开放、未归档且命中全校/年级/班级受众的小测。
- 已经开始作答的学生在发布范围缩小后仍可恢复；未开始的学生按最新范围校验。
- 开始操作使用用户行和 session 行锁，重复开始返回同一个 attempt、同一份试卷和同一截止时间。
- 个人试卷仅从首次发布冻结蓝图生成：按难度随机抽题、选择题随机排序、每题选项独立打乱。
- 学生响应使用显式白名单，不返回正确答案、解析、来源题号/版本、选项映射、完整编程题内容或测试点。
- 完整答案字典保存采用乐观并发 revision；未知 item、编程 item、非法选项、跨学生 attempt 均拒绝且不部分写入。
- 到达服务端截止时间后，attempt 原子切换为 `settling` 并锁卷，再返回 410；教师关闭或归档小测后立即拒绝继续保存。

## 2. 新增学生接口

- `GET /api/ai/quizzes/`
- `POST /api/ai/quizzes/{id}/attempt/`
- `GET /api/ai/quizzes/{id}/attempt/`
- `PUT /api/ai/quizzes/{id}/attempt/answers/`

Step 4 不提供主动交卷和最终计分；对应能力在 Step 6 完成。

## 3. 验证结果

- Step 4 定向测试：11 项通过，1 项 MySQL/InnoDB 真并发测试在当前 SQLite 环境跳过。
- AI 课程 + Execution 全量回归：232 项通过，3 项按环境跳过。
- Django system check：通过。
- Migration check：无遗漏变更。
- Migration 0009 回退到 0008 后重新前进：通过。
- 真实 HTTP 链路：学生列表 200 → 开始 201 → 保存 200 → 刷新恢复 200。
- HTTP 验收中 revision 从 0 增至 1，恢复后保留已保存答案；学生响应敏感字段扫描为零。
- HTTP 验收临时账号、单元、题目、小测、attempt 和审计均已清理。

## 4. 存量兼容

- 迁移前后 AI 编程题均为 9 道，Submission 均为 9 条，ExecutionTask 均为 0 条。
- 9 道存量编程题继续保持未归类。
- 新增 Attempt 表部署后为空，不把历史单题 Submission 伪造成组合小测作答。

## 5. 下一步边界

Step 5 将为 `ExecutionTask` 和 `Submission` 增加小测上下文，提供冻结测试快照的可信入队路径，并实现小测内编程题运行、正式评测和活动任务恢复。最终综合计分仍在 Step 6。
