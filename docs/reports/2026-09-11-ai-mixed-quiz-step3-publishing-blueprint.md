# AI 混合题库 Step 3 验收报告

报告日期：2026-09-11
对应 DEV：`docs/dev/2026-09-11-ai-mixed-question-bank-quiz-dev.md`
实施范围：Step 3（小测草稿与发布蓝图后端）

## 1. 已完成能力

- Migration 0008 创建 `AIQuizSession`、`AIQuizProgrammingItem`、`AIQuizAudience` 和 `AIQuizManagementAudit`。
- 教师管理 API 支持小测列表、创建、详情、草稿编辑、软归档和复制。
- 草稿支持选择题小节多选、精确难度题数、选择题部分分值、编程题多选/排序/分值、限时和发布范围。
- 发布前预检覆盖至少一种题型、总分 100、选择题题池容量、单元/年级、编程题归类与测试点、受众和管理版本。
- 首次发布冻结 schema version 1 蓝图，并使用规范 JSON 的 SHA-256 保存 `blueprint_hash`。
- 蓝图冻结选择题候选池的题干、选项、答案、解析和版本，以及编程题题干、模板、分值、顺序和测试点快照。
- 首次发布后组卷内容锁定；关闭和重新开放沿用原蓝图；复制生成无蓝图的新草稿。
- 普通教师只能管理本人年级，超级管理员可配置跨年级或全校范围；管理版本冲突返回 409。
- 管理响应不返回 `blueprint_json`，失败审计不保存题库答案、测试点或完整蓝图。

## 2. 新增管理接口

- `GET/POST /api/ai/admin/quizzes/`
- `GET/PATCH/DELETE /api/ai/admin/quizzes/{id}/`
- `POST /api/ai/admin/quizzes/{id}/validate/`
- `POST /api/ai/admin/quizzes/{id}/publish/`
- `POST /api/ai/admin/quizzes/{id}/close/`
- `POST /api/ai/admin/quizzes/{id}/reopen/`
- `POST /api/ai/admin/quizzes/{id}/copy/`
- `GET/PATCH /api/ai/admin/quizzes/{id}/audience/`

学生开始与作答接口不在本 Step 开放。

## 3. 验证结果

- Step 3 定向测试：7 项通过。
- AI 课程 + Execution 全量回归：221 项通过，2 项跳过。
- Django system check：通过。
- Migration check：无遗漏变更。
- Migration 0008 回退到 0007 后重新前进：通过。
- 真实 HTTP 链路：登录→创建单元→创建选择题→创建纯选择题草稿→预检→发布，预检和发布均返回 200，蓝图版本为 1。
- HTTP 验收临时单元、题目、小测和审计均已清理。

## 4. 存量兼容

- 迁移前后 AI 编程题均为 9 道，Submission 均为 9 条，ExecutionTask 均为 0 条。
- 9 道存量编程题继续保持未归类，未生成猜测性映射。
- 新建小测、题项、受众和审计表部署后保持为空。

## 5. 下一步边界

Step 4 将创建 Attempt 与个人快照，并实现纯选择题小测的开始/恢复、选择题答案保存和服务端截止时间。Step 3 尚未向学生开放小测入口。
