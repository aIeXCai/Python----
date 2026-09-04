# 阶段 5 Step 6：切断旧本机执行完成报告

日期：2026-09-04

## 完成内容

- 删除 `ai_courses.utils.run_code_interactive()` 及其本机临时文件/子进程实现。
- 删除 `ai_courses.models.grade_submission()` 及其逐测试点本机子进程实现。
- 删除过渡用 `LEGACY_CODE_EXECUTION_ALLOWED` 和已无业务引用的 `SUBMISSIONS_DIR` 配置。
- 替换旧执行单元测试，新增“本机执行模块已删除”和“Django AI 业务代码不引用 subprocess”护栏。
- 代码运行开关关闭时返回 503；开启时 Django 只创建持久化任务。

## 历史提交文件清点

- `backend/submissions/` 共 367 个文件，其中 268 个 `.py` 文件，总体积约 1.4 MB。
- 本 Step 没有删除这些历史文件。如需删除，必须先另行确认。

## 自动验证

- `ai_courses.tests_code_run`：22/22 通过。
- Django 全量：共运行 385 项，382 通过，3 跳过，0 失败。
- Django 系统检查：0 问题。
- 非测试、非 migration 的 backend Python 代码静态扫描：未发现学生代码本机执行路径。

## 已知限制

旧路径删除后，未完成 Runner/Docker 前不能真实运行或评测学生代码。这是预期的安全关闭状态，系统不会回退到 Django 本机执行。
