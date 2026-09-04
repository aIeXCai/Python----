# 小测全状态编辑与安全删除 DEV

文档日期：2026-09-02
对应 PRD：`docs/prd/2026-09-02-quiz-edit-delete-prd.md`
状态：已实施

## 编辑

`PUT /api/admin/info/sessions/<id>/` 对 `draft/open/closed` 均开放，但仍受创建教师和 `managed_grade` 权限约束。

- 更新在数据库事务中完成。
- `open/closed` 更新后立即调用快照构建器执行题库容量和题目合法性预检。
- 预检失败时事务回滚，返回 `409 quiz_pool_insufficient`。
- 现有 attempt 的 `snapshot_json`、`deadline_at` 和答案不更新。
- 本人已有的 `in_progress` attempt 不因教师后来调整年级或班级范围而失去保存、提交权限；新 attempt 必须通过最新范围校验。

## 删除

`QuizSession` 新增 `archived_at`，迁移为 `info_tech.0007_quizsession_archived_at`。

- 无 attempt：物理删除，响应 `deletion_mode=permanent`。
- 有 attempt：若正在开放则调用统一关闭结算，再写入 `archived_at`，响应 `deletion_mode=archived`。
- 教师列表、学生列表、学生统计和教师统计默认过滤 `archived_at IS NOT NULL`。
- 已归档小测不允许开始新 attempt；本人历史结果仍可读取。

## 前端

- 每一行始终显示编辑和删除图标。
- 删除确认框说明小测会从列表移除，已有作答和成绩会保留。
- 编辑复用现有弹窗，完整回填名称、单元、时长、题数、难度、年级和班级。
