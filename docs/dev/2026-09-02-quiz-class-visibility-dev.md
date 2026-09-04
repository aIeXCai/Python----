# 小测班级可见范围 DEV

文档日期：2026-09-02
对应 PRD：`docs/prd/2026-09-02-quiz-class-visibility-prd.md`
状态：已实施

## 数据模型

`QuizSession` 新增：

```text
visible_classes JSONField(default=list)
```

- `[]`：所选年级的全部班级，且自动包含以后新增班级。
- `['1', '3']`：只允许 1 班和 3 班。
- 班级值统一按字符串与 `CustomUser.class_num` 比较。
- migration `info_tech.0006_quizsession_visible_classes` 使用空数组回填旧记录，无破坏性数据转换。

## 后端契约

- 小测创建、详情、状态接口新增 `visible_classes`。
- `GET /api/admin/info/classes/?grade=<grade>` 返回教师管理年级已有班级：

```json
{"grade": "七年级", "classes": ["1", "2", "10"]}
```

- 非超级管理员不能查询自己 `managed_grade` 之外的班级。
- 学生访问条件为：年级匹配，并且 `visible_classes` 为空或包含学生 `class_num`。
- 相同校验同时用于列表、开始/恢复、保存、提交、结果和学生信息课统计。

## 前端状态

`sForm.visible_classes` 使用以下约定：

- `[]`：全年级模式。
- 非空数组：指定班级模式。

弹窗打开或年级变化时并行加载单元和班级。切换年级会清空单元选择并恢复全年级模式。任意状态的小测都可打开编辑弹窗；修改后的配置供之后新建的 attempt 使用，已有 attempt 继续使用原快照和截止时间。

## 数据安全与回滚

- 本地迁移前备份位于 `backend/migration_artifacts/stage4-class-scope-pre-20260902/`。
- 本地 MySQL 迁移后验证备份位于 `backend/migration_artifacts/stage4-class-scope-mysql-20260902/post-0006.sql`，权限为 0600。
- 回滚代码前必须先确认数据库字段兼容；该字段添加本身不改写既有小测业务数据。
- 不记录学生名单到小测配置，只保存班级号，避免复制额外个人信息。

## 验证结果

- SQLite 全量：345 项通过，1 项 MySQL 专用测试按设计跳过。
- MySQL 8.0 全量：345 项全部通过。
- Vitest 全量：23 个测试文件通过，267 项通过，2 项原有跳过。
- ESLint：0 error，42 条既有 warning。
- Vite production build：成功。
