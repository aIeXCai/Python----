# AI 题目目录

- `programming/<年级>/`：编程题。先按年级建立目录，再为每道题创建以具体题目名称命名的独立目录，保存题目描述、代码模板和输入输出测试点。目录年级会在磁盘同步时写入题目的适用年级标签。
- `choice/`：选择题 JSON 文件的整理目录。选择题仍通过教师端导入并保存在数据库中，后端不会自动扫描此目录。

新题目可以直接使用目录名作为题目 ID 和标题。已有题目如需保持历史题目 ID，可在 `metadata.txt` 中配置：

```text
problem_id: problem1
title: 打印三行问候语
difficulty: easy
```

`problem_id`、`title` 和 `difficulty` 都是可选项。后端同时兼容旧的 `problems/ai/problem*/` 路径。
