# AI 混合题库 Step 1 验收报告

报告日期：2026-09-11
对应 DEV：`docs/dev/2026-09-11-ai-mixed-question-bank-quiz-dev.md`
实施范围：Step 1（AI 单元与选择题后端）

## 1. 完成内容

- 新增 `AIUnit`：支持年级、大单元—小节两级结构、同层同名保护、排序、软归档和恢复。
- 新增 `AIChoiceQuestion`：包含难度、知识点、题干、四个选项、正确答案、解析、创建人、管理版本和归档状态。
- `Problem` 新增可空 `unit` 关联；本步不对现有 9 道编程题做自动归类。
- 新增领域服务：年级权限、叶子小节约束、题目所有者规则、乐观并发、软归档/恢复、复制和原子 JSON 导入。
- JSON 导入支持 `unit_id + questions` 格式，同时兼容信息课的 `grade + unit + questions + options[]` 结构；AI 导入要求目标小节已存在，不自动创建错误层级。
- Django Admin 注册 AI 单元和选择题，审计字段设为只读。

## 2. 管理 API

- `GET/POST /api/ai/admin/units/`
- `PATCH/DELETE /api/ai/admin/units/{id}/`
- `POST /api/ai/admin/units/{id}/restore/`
- `GET/POST /api/ai/admin/choice-questions/`
- `GET/PATCH/DELETE /api/ai/admin/choice-questions/{id}/`
- `POST /api/ai/admin/choice-questions/{id}/copy/`
- `POST /api/ai/admin/choice-questions/{id}/restore/`
- `POST /api/ai/admin/choice-questions/import/`

错误响应统一为 `{error, code, ...safe_extra}`，并发冲突额外返回最新 `management_version`。

## 3. 迁移验收

- 已在当前本地 SQLite 数据库应用 `ai_courses.0007` 成功。
- 应用后：`Problem=9`、`Submission=9`、已归类编程题 `=0`、AI 单元 `=0`、AI 选择题 `=0`。
- 在数据库隔离副本中执行 `0007 -> 0006 -> 0007`；回滚和前进后均保持 `Problem=9`、`Submission=9`，前进后已归类题目仍为 0。
- `python manage.py makemigrations --check --dry-run`：无未生成的模型变更。
- `python manage.py check`：通过。

## 4. 测试验收

- Step 1 定向测试：9 项全部通过。
- AI 课程 + Execution 全量回归：208 项通过，2 项按原有条件跳过。
- 覆盖两级结构、跨年级禁止、叶子小节、必填内容、所有者权限、并发冲突、归档/恢复、复制、搜索和原子导入。

## 5. 边界

- 本步没有修改学生页面。
- 本步只为 `Problem` 增加数据关联；编程题管理 API、管理弹窗、可组卷状态和现有 9 道题的手工归类属于 Step 2。
