# 课程扩展设计方案：AI课 + 信息科技课 双入口平台

**作者**: Alex 老师 & Hermes Agent
**日期**: 2026-04-21
**状态**: 待用户审核

---

## 1. 背景与目标

**现状**：
- 现有平台（Python http.server + SQLite）已作为 AI 课教学平台运行
- 学生用 年级+班级+用户名 登录，做编程题 + 系统自动评分

**扩展目标**：
- 在同一套用户系统上，新增"信息科技课"模块
- 学生登录后先选课（AI课 / 信息科技课），选课后进入对应课程界面
- AI课保持原有逻辑不变
- 信息科技课：学生学习 HTML 交互课件 + 做选择题小测
- 老师后台合并管理两门课

---

## 2. 设计原则

- **共用数据库**：现有 `users` 表不变，学生账号两门课都能访问
- **轻量扩展**：尽量复用现有架构，不过度设计
- **文件存储**：课件和题目用文件系统存储（JSON/HTML），不在数据库里存大型内容
- **渐进增强**：先跑通最小流程，再加细节功能

---

## 3. URL 结构

```
学生端：
/                          → 登录页（不变）
/student                   → 选课页（新增）
/student/ai                → AI课学生仪表盘（现有 /student 改名迁移）
/student/info               → 信息科技课学生首页（新增）
/student/info/quiz/<id>    → 做小测（新增）
/student/info/materials     → 查看课件列表（新增，内嵌iframe显示）

老师端（均在 /admin 下，加分支判断）：
/admin                     → 老师仪表盘（合并展示两门课概况）
/admin/problems            → AI课题目管理（现有逻辑）
/admin/info                → 信息科技课管理首页（新增）
/admin/info/quizzes        → 小测题目管理（新增）
/admin/info/materials      → 课件管理（新增）
```

**路由变更说明**：
- 原 `/student`（AI课仪表盘）→ 迁移到 `/student/ai`
- 新增 `/student` → 选课页
- 选课页用 JavaScript 做客户端跳转，不走服务端重定向

---

## 4. 数据库 Schema

### 4.1 复用现有表

- `users` 表：**不变**，所有学生继续用同一套账号
- `scores` 表：**不变**，AI课成绩继续存在这里

### 4.2 新增表

```sql
-- 信息科技课成绩表
CREATE TABLE IF NOT EXISTS info_tech_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    grade TEXT NOT NULL,
    class_num TEXT NOT NULL,
    quiz_id TEXT NOT NULL,
    score REAL NOT NULL,          -- 百分制
    total_questions INTEGER NOT NULL,
    correct_count INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,  -- ISO timestamp
    UNIQUE(username, quiz_id)    -- 每个学生每份小测只记录最高分
);

-- 小测题目表（简化版，仅存元数据索引）
CREATE TABLE IF NOT EXISTS info_tech_quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id TEXT UNIQUE NOT NULL,   -- 对应 quizzes/<id>.json
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,                   -- 分类，如 "计算机基础"
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 课件资料表
CREATE TABLE IF NOT EXISTS info_tech_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id TEXT UNIQUE NOT NULL, -- 对应 materials/<material_id>/
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

---

## 5. 小测题目格式（JSON）

老师上传 `quizzes/<quiz_id>.json`，格式如下：

```json
{
  "quiz_id": "computer_basics_01",
  "title": "计算机基础小测",
  "description": "第一章：计算机概述",
  "category": "计算机基础",
  "time_limit_minutes": 30,
  "questions": [
    {
      "id": 1,
      "type": "single",
      "question": "世界上第一台电子计算机（ENIAC）诞生于哪个国家？",
      "options": ["英国", "美国", "德国", "日本"],
      "answer": 1
    },
    {
      "id": 2,
      "type": "true_false",
      "question": "CPU 是中央处理器的英文缩写。",
      "answer": true
    },
    {
      "id": 3,
      "type": "multiple",
      "question": "以下哪些是编程语言？（多选）",
      "options": ["Python", "HTML", "Java", "CSS", "C++"],
      "answer": [0, 2, 4]
    }
  ]
}
```

**`type` 类型说明**：
- `single`：单选题（`answer` 为正确选项索引，整数）
- `true_false`：判断题（`answer` 为 `true`/`false`）
- `multiple`：多选题（`answer` 为正确选项索引数组）

---

## 6. 课件资料格式

课件存储在 `materials/<material_id>/` 目录：

```
materials/
  computer_basics_01/
    index.html        ← 必须是 index.html
    img/
      diagram.png
    style.css         （可选）
  office_tools_01/
    index.html
```

学生查看时，在 Info Tech 页面点击课件标题 → iframe 内嵌显示 `materials/<id>/index.html`。

**约束**：
- 每份课件必须包含 `index.html` 作为入口
- 路径中避免中文和空格
- 静态资源（图片/CSS/JS）放在同一目录下

---

## 7. 页面流程

### 7.1 学生登录 → 选课

```
学生访问 /
  → 输入 grade/class/username/password
  → 登录成功
  → 跳转到 /student（选课页）
  → 显示两个课程卡片：
      [🤖 AI课]  [💻 信息科技课]
  → 点击进入对应课程
  → 选课后记录在 session 里，后续直接进对应课
```

session 里增加字段记录学生当前所在课程（`current_course`），用于刷新后保持状态。

### 7.2 信息科技课学生首页

```
/student/info
  左侧边栏：
    📚 我的课件
    📝 小测试卷
    📊 我的成绩
  主内容区：
    横向展示课件卡片（点击 → iframe 嵌入查看）
    小测列表（显示：标题/题目数/是否已做/最高分）
```

### 7.3 做小测流程

```
/student/info/quiz/<quiz_id>
  → 加载 JSON，显示题目（一次显示一题，或全部显示）
  → 学生选择答案，点击提交
  → 服务端评分（比对 answer 字段）
  → 显示得分 + 正确答案（可做可不做）
  → 成绩写入 info_tech_scores 表
  → 返回上一页
```

### 7.4 老师管理后台

```
/admin
  顶部导航卡：
    [📊 总览] [🤖 AI课管理] [💻 信息科技课管理]

/admin/info
  两大区块：
    课件管理：上传/删除课件（zip 打包上传，解压到 materials/）
    小测管理：上传/删除 JSON 题目文件

/admin/info/quizzes
  上传 quiz JSON 文件
  列出已有小测（quiz_id / 标题 / 题目数 / 创建时间）
  支持删除

/admin/info/materials
  上传课件（zip，含 index.html）
  列出已有课件
  支持删除
```

---

## 8. 目录结构

```
school_platform/              （项目根目录）
  server.py                   # 主服务（扩展路由）
  users.db                    # SQLite 数据库（不变）
  
  templates/                  # HTML 模板
    index.html                # 登录页（不变）
    course_select.html        # ⭐ 新增：选课页
    student_dashboard_ai.html # ⭐ 重命名（原 student_dashboard.html）
    student_dashboard_info.html # ⭐ 新增：信息科技课学生首页
    quiz_take.html            # ⭐ 新增：学生做小测页面
    materials_view.html       # ⭐ 新增：课件 iframe 嵌入页面
    admin_dashboard.html      # 扩展：增加信息科技课管理入口
    info_tech_admin.html      # ⭐ 新增：信息科技课管理面板

  problems/                   # AI课题目（不变）
    problem1/
    ...

  quizzes/                    # ⭐ 新增：信息科技课小测 JSON
    computer_basics_01.json
    network_basics_01.json

  materials/                  # ⭐ 新增：HTML 课件
    computer_basics_01/
      index.html
      img/
    office_intro_01/
      index.html
```

---

## 9. session 扩展

现有 session 结构：
```python
SESSIONS[session_id] = {
    'username': username,
    'role': role,          # 'student' or 'teacher'
    'grade': grade,
    'class_num': class_num,
    'created_time': time.time()
}
```

新增 `current_course` 字段（学生选课后写入）：
```python
'current_course': 'ai' | 'info'
```

---

## 10. 关键实现细节

### 10.1 成绩计算逻辑

**选择题评分**：
- 单选题：选对得 `100/总题数` 分
- 判断题：同上
- 多选题：全对得分，错选/漏选不得分

最终成绩取历次最高分（`UNIQUE(username, quiz_id)` 约束，重复提交取最高分）。

### 10.2 老师上传课件流程（ZIP）

1. 老师在管理页面上传 `.zip` 文件
2. 服务端接收 ZIP，解压到 `materials/<自动生成id>/`
3. 校验 `index.html` 存在
4. 元数据写入 `info_tech_materials` 表

### 10.3 老师上传小测流程（JSON）

1. 老师上传 `.json` 文件
2. 服务端校验 JSON 格式（包含 `quiz_id`, `questions` 数组，每个题目有 `type`, `question`, `options`, `answer`）
3. 写入 `quizzes/` 目录
4. 元数据写入 `info_tech_quizzes` 表

### 10.4 复用现有认证

- `authenticate_user()` / `authenticate_teacher()` 不变
- session 机制不变，加一个 `current_course` 字段
- 学生路由 `/student/*` 全部加 session 校验

---

## 11. 最小可行版本（MVP）范围

**第一阶段实现**（MVP）：
1. ✅ 新增 `course_select.html` 选课页
2. ✅ AI课学生仪表盘迁移到 `/student/ai`
3. ✅ 新增 `/student/info` 信息科技课学生首页（静态展示课件列表）
4. ✅ 新增 `info_tech_scores` 表
5. ✅ 小测 JSON 格式支持（single/true_false/multiple）
6. ✅ 学生做小测页面 + 评分
7. ✅ 信息科技课老师管理面板（上传quiz JSON）

**第二阶段**（后续迭代）：
- 课件 ZIP 上传/解压功能
- 课件管理界面
- 合并成绩查看（老师后台看两门课的总成绩）

---

## 12. 技术风险与备选

| 风险 | 应对 |
|------|------|
| iframe 内嵌 HTML 跨域问题 | 课件必须同源（上传到本服务器），禁止外链 |
| JSON quiz 格式老师容易写错 | 提供示例 JSON 模板下载 + 简单的 schema 校验 |
| 现有 server.py 已2366行，继续膨胀 | MVP 阶段先堆在一起，之后重构拆分 |
| 学生多次提交同一小测 | 后端取最高分，前端提示"已做过，最高分是XX" |

---

## 13. 待确认事项

- [ ] 小测有没有时间限制？（JSON里加了 `time_limit_minutes`，前端未实现）
- [ ] 学生做完小测后能否查看正确答案？（设计里写了"可做可不做"，待定）
- [ ] 课件 ZIP 上传的大小限制？（建议 50MB 以内）
