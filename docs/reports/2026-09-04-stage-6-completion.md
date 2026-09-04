# 阶段 6 完成报告：数据规范与业务权限

日期：2026-09-04
状态：DEV 已完成，自动化验证通过，等待用户浏览器手工验收

## 1. 完成内容

- 年级权威枚举收口为七年级、八年级、九年级、高一、高二、高三；初一/初二/初三仅作为输入别名。
- 学生班级和学号去首尾空白、保留 `01` 类前导零、拒绝空值与控制字符。
- 增加学生身份普通唯一约束、学生身份必填约束和教师学生字段为空约束，兼容 SQLite/MySQL。
- 完成用户、单元、小测可见年级和历史提交年级快照的数据迁移。
- 教师学生管理、密码查看/重置、AI 成绩、信息课内容与统计均按 `managed_grade` 在查询集层收紧。
- 普通教师缺少管理年级时 fail closed；`is_staff` 不越权；仅 `is_superuser` 可跨年级。
- 学生 AI 题目、提交、成绩、任务和对话使用统一 `IsStudent`，资源详情保留所有者过滤。
- 跨年级密码请求在解密前拒绝，并记录 `teacher_grade_forbidden` 审计事件。
- 前端六个年级选项收口到单一常量，主要文案使用简体“教师/登录/加载”，日期改为 `zh-CN`，学生提交状态显示中文。
- 提供只读数据审计命令、验收数据创建/清理命令和手工验收清单。

## 2. 数据安全与迁移

- 迁移前 SQLite 备份：`backend/migration_artifacts/stage6-prechange-20260904`。
- 备份 SHA-256：`c03b819ffff8bb37655197a336df84990a470ca17203fa67a6d0027287d80be6`。
- 迁移后审计：0 个阻断项；1 个普通教师未配置范围（本地 `t`，按确认决策不自动授权）。
- 迁移前后行数一致：用户 4、密码审计 2、AI 题目 9、AI 提交 9、单元 58、题目 17、小测 2、小测提交 4、会话 1、消息 2。
- migration 回滚时移除新约束，规范化后的业务值保持不变；若需完全还原别名原值，使用上述一致性备份，不猜测历史别名。

## 3. 自动验证

- SQLite 全量 Django：399 通过，3 跳过，0 失败。
- MySQL 8.0.46 全量 Django：398 通过，0 失败（包含 MySQL/InnoDB 并发测试）。
- 最终 MySQL 阶段 6 定向回归：35 通过，0 失败。
- Django `check`、`makemigrations --check --dry-run`、Python `compileall`：通过。
- Vitest：24 个测试文件，277 通过，2 跳过，0 失败。
- ESLint：0 error，35 warning，命令成功。warning 为已有 Hook/性能改进项，不影响本阶段功能和构建。
- Vite 生产构建：通过，3.18s。Monaco 代码编辑器仍有大 chunk 提示，不是构建错误。
- 验收数据命令在独立临时 SQLite 库中已完成“创建→审计→清理”往返测试。
- MySQL 验证后已停止，`127.0.0.1:3308` 未监听。验证中遗留的专用测试表空间已删除并重建测试库，不涉及业务库。

## 4. 主要交付物

- `backend/users/grade_levels.py`：年级和学生标识规范。
- `backend/users/scopes.py`：教师与超级管理员作用域。
- `backend/users/migrations/0008_normalize_grade_and_identity.py`：用户数据迁移与约束。
- `backend/info_tech/migrations/0008_normalize_grade_data.py`：信息课年级数据迁移。
- `backend/users/management/commands/audit_stage6_data.py`：只读数据审计。
- `backend/users/management/commands/prepare_stage6_acceptance.py`：本地手工验收数据。
- `frontend/src/constants/grades.js`：前端标准年级选项。
- `docs/deployment/stage-6-manual-acceptance.md`：用户手工验收清单。

## 5. 已知限制

- 本地普通教师 `t` 不会自动获得年级权限；需超级管理员在 Django Admin 显式设置 `managed_grade`。
- Docker/Runner 仍按用户决定暂缓，学生真实代码执行不在阶段 6 范围内。
- 本阶段交付到“自动化通过 + 可手工验收”；浏览器端的人工确认由用户完成。
