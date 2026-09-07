# 教学内容恢复说明

仓库保存以下不含学生隐私的固定教学内容：

- `problems/ai/`：9 道 AI 题目的描述、模板、输入与标准输出文件。
- `problems/info-tech/`：信息课原始题目 JSON 文件。
- `backend/ai_courses/fixtures/current_ai_catalog.json`：9 道 AI 题目的数据库元数据与 18 条发布范围。
- `backend/info_tech/fixtures/current_curriculum.json`：58 个信息课单元/小节与 17 道信息课题目。

在全新数据库执行 migration 后，从 `backend/` 目录恢复：

```bash
python manage.py migrate
python manage.py loaddata info_tech/fixtures/current_curriculum.json ai_courses/fixtures/current_ai_catalog.json
```

成功时 Django 应报告导入 102 个对象。AI 测试点继续从项目根目录的 `problems/ai/` 读取。

这些 fixture 不包含用户、教师、小测场次、学生作答、成绩、聊天记录、密码、密钥或管理审计。它们使用固定主键，适合恢复到完成 migration 的全新数据库；向已有教学数据的数据库导入前应先备份并检查主键冲突。
