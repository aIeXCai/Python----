# AI 混合题库与自由组卷 Step 0 完成报告

日期：2026-09-11
对应 DEV：`docs/dev/2026-09-11-ai-mixed-question-bank-quiz-dev.md`
阶段：Step 0 基线与契约保护
结果：已完成，等待用户确认后进入 Step 1

## 1. 基线

实施前：

- Git 分支：`Macbook`。
- 基线提交：`98adfb1`。
- 工作区仅有本需求新建且未跟踪的 PRD/DEV 文档，没有发现用户已有代码改动。
- 后端 `ai_courses + execution`：188 项通过，2 项跳过。
- 前端：287 项通过，2 项跳过。
- Django system check：通过。
- Django migration check：无待生成迁移。
- Vite 生产构建：通过。
- ESLint：0 错误、32 个既有警告。

## 2. 完成内容

### 2.1 存量 AI 题库保护

新增基于 `current_ai_catalog.json` 的回归测试，锁定：

- `problem1` 至 `problem9` 共 9 个稳定业务 ID；
- 9 道题仍属于 AI 课程且未归档；
- 18 条现有发布范围记录；
- 八年级学生仍能看到全部 9 道现有题；
- 9 道题的仓库测试点文件均可读取且至少有 1 个有效测试点。

### 2.2 历史提交与执行任务保护

新增测试锁定：

- Submission 的 user、problem、code、score、status 字段；
- Submission 与 ExecutionTask 的一对一关系；
- ExecutionTask 的测试点快照和稳定 problem 关联；
- 有历史 Submission 的 Problem 继续受到 `PROTECT` 保护；
- 删除失败时 Problem、Submission 和 ExecutionTask 均保留。

### 2.3 新 API 契约测试辅助

新增可复用断言：

- 错误响应必须包含稳定 `code` 和非空 `error`；
- 小测分值使用 1 位小数的字符串，范围为 0.0–100.0；
- 时间使用包含时区的 ISO 8601 字符串。

这些断言将在后续小测 API 测试中复用。

### 2.4 旧题库练习完成口径

此前学生首页使用 100 分判断“已通过”，后端成绩和统计使用 80 分判断 completed，存在双重口径。

Step 0 保持现有学生端展示语义，将旧题库练习统一为：

- 100 分：`completed / 已通过`；
- 低于 100 分：`attempted / 作答中`。

正式混合小测后续不使用分数判断“已完成”，只使用 Attempt 是否已经结算。

## 3. 关键文件

- `backend/ai_courses/testing_contracts.py`
- `backend/ai_courses/tests_step0_contracts.py`
- `backend/ai_courses/tests_step0_compatibility.py`
- `backend/ai_courses/views.py`
- `backend/ai_courses/tests.py`
- `frontend/src/pages/student/StudentDashboard.jsx`
- `frontend/src/pages/student/StudentDashboard.test.jsx`
- `docs/dev/2026-09-11-ai-mixed-question-bank-quiz-dev.md`

## 4. 最终验证

- 后端定向测试：23 项通过。
- 学生首页定向测试：10 项通过。
- 后端 `ai_courses + execution` 全量：199 项通过，2 项跳过。
- 前端全量：288 项通过，2 项跳过。
- Django system check：通过。
- Django migration check：无待生成迁移。
- Vite 生产构建：通过。
- ESLint：0 错误、32 个既有警告，与实施前一致。

已知非阻断提示：

- Python `requests` 依赖组合发出既有兼容性 warning。
- Vite 提示 Monaco 相关 chunk 大于 500 kB。
- jsdom 输出既有 `HTMLFormElement.requestSubmit()` 未实现提示。

## 5. 下一步

用户确认 Step 0 后进入 Step 1：AI 单元与选择题后端，包括 Migration 0007、模型、服务、权限、CRUD、软归档恢复和 JSON 导入。
