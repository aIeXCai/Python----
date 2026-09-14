# 教学内容恢复说明

仓库保存以下不含学生隐私的固定教学内容：

- `problems/ai/programming/<年级>/`：AI 编程题的描述、模板、输入与标准输出文件；题目目录可以使用具体题名，年级目录会自动同步为题目的适用年级标签。旧的平铺目录仍兼容读取。
- `problems/ai/choice/`：用于整理待导入教师端的 AI 选择题 JSON 文件；系统不会自动从该目录写入数据库。
- `problems/info-tech/`：信息课原始题目 JSON 文件。
- `backend/ai_courses/fixtures/current_ai_catalog.json`：9 道 AI 题目的数据库元数据与 18 条发布范围。
- `backend/info_tech/fixtures/current_curriculum.json`：58 个信息课单元/小节与 17 道信息课题目。

在全新数据库执行 migration 后，从 `backend/` 目录恢复：

```bash
python manage.py migrate
python manage.py loaddata info_tech/fixtures/current_curriculum.json ai_courses/fixtures/current_ai_catalog.json
```

成功时 Django 应报告导入 102 个对象。AI 测试点从项目根目录的 `problems/ai/programming/<年级>/` 读取，并兼容旧的 `problems/ai/programming/题目/` 和 `problems/ai/problem*/` 目录。

这些 fixture 不包含用户、教师、小测场次、学生作答、成绩、聊天记录、密码、密钥或管理审计。它们使用固定主键，适合恢复到完成 migration 的全新数据库；向已有教学数据的数据库导入前应先备份并检查主键冲突。
