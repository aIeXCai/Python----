# AI 选择题

这里可以保存准备通过教师端“选择题库”导入的 JSON 文件。

支持题目数组，或包含 `questions` 数组的对象。每道题可包含：

- `difficulty`：`easy`、`medium` 或 `hard`
- `category`：知识点分类
- `text`：题干
- `options`：包含 A、B、C、D 的选项数组
- `answer`：正确选项字母
- `explanation`：解析

选择题必须在教师端导入到一个已存在的小节中；仅把 JSON 放进本目录不会自动写入数据库。
