# 项目重构设计方案：Django REST + TypeScript 前端

**作者**: Alex 老师 & Hermes Agent
**日期**: 2026-04-21
**状态**: 进行中（第一阶段 ✅ | 第四阶段 🔄 前端开发（Vite+React）✅老师管理后台合并完成）

---

## 1. 背景与目标

**现状**：
- 现有系统：Python `http.server` + SQLite（`users.db`）+ 原生 HTML 模板
- `server.py` 约 2366 行，AI课正在使用
- 学生按年级+班级+用户名登录，做编程题自动评分

**重构目标**：
- 后端：Django 5 + Django REST Framework（DRF）+ SQLite
- 前端：TypeScript + Vite（CDN 版本，无需构建也可）
- 数据库：Django ORM（新建 schema，不迁移现有 users.db）
- 两门课（AI课、信息科技课）共存于同一 Django 项目
- 老师后台统一管理两门课

**不迁移现有 users.db 的原因**：现有 AI课系统继续独立运行，不改动。新 Django 项目作为信息科技课专用后端，数据库独立。

---

## 2. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | Django 5 + Django REST Framework | Python 3.10+，pip install |
| 后端路由 | DRF ViewSet + Router | URL 统一 `/api/` 前缀 |
| 数据库 | SQLite | Django 默认，够用 |
| 前端框架 | TypeScript + Vite | 构建工具，用 CDN 可免构建 |
| 前端路由 | 页面级路由（hash 或页面跳转） | 不做 SPA 全家桶，保持简单 |
| 模板 | 原生 HTML + TypeScript | 每个页面是独立 HTML |

---

## 3. Django 项目结构

```
backend/                          # 项目根目录（server/）
    manage.py
    pyproject.toml / requirements.txt
    school_platform/              # Django 项目配置
        __init__.py
        settings.py               # Django 设置
        urls.py                   # 根路由：/api/ + /admin/
        asgi.py / wsgi.py
    users/                        # 用户模块
        models.py                 # CustomUser（继承自AbstractUser）
        serializers.py
        views.py
        urls.py                   # /api/auth/*
        admin.py
    ai_courses/                  # AI课模块
        models.py                 # Problem, Submission, Score
        serializers.py
        views.py
        urls.py                   # /api/ai/*
        admin.py
    info_tech/                    # 信息科技课模块（新增）
        models.py                 # Quiz, Question, QuizResult, Material
        serializers.py
        views.py
        urls.py                   # /api/info/*
        admin.py
    docs/                         # 项目文档
```

### 3.1 users/models.py — 用户模型

```python
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """扩展 Django 默认 User 模型"""
    ROLE_CHOICES = [
        ('student', '学生'),
        ('teacher', '老师'),
    ]
    GRADE_CHOICES = [
        ('初一', '初一'), ('初二', '初二'), ('初三', '初三'),
        ('高一', '高一'), ('高二', '高二'), ('高三', '高三'),
    ]

    role = models.CharField('角色', max_length=20, choices=ROLE_CHOICES, default='student')
    grade = models.CharField('年级', max_length=10, choices=GRADE_CHOICES, blank=True, null=True)
    class_num = models.CharField('班级', max_length=20, blank=True, null=True)  # 如 "1班"
    student_number = models.CharField('班级内学号', max_length=20, blank=True, null=True)

    # 老师的 managed_grade 用于信息科技课管理范围
    managed_grade = models.CharField('管理年级', max_length=10, choices=GRADE_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.grade}{self.class_num})"
```

> **说明**：Django 默认 User 的 username 就是原来的"用户名"字段，不需要单独再要一个 username。Django 自带的 `authenticate` 配合 session/JWT 使用。

### 3.2 ai_courses/models.py — AI课模型

```python
# 题目
class Problem(models.Model):
    problem_id = models.CharField('题目ID', max_length=50, unique=True)  # 如 "problem1"
    title = models.CharField('标题', max_length=200)
    description = models.TextField('题目描述')
    difficulty = models.CharField('难度', max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

# 题目测试点
class TestCase(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='test_cases')
    input_file = models.CharField('输入文件', max_length=255)
    output_file = models.CharField('输出文件', max_length=255)
    is_sample = models.BooleanField('是否示例', default=False)

# 学生提交
class Submission(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    code = models.TextField('代码')
    score = models.FloatField('得分')
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField('状态', max_length=20, default='pending')
```

### 3.3 info_tech/models.py — 信息科技课模型

```python
# 小测
class Quiz(models.Model):
    quiz_id = models.CharField('小测ID', max_length=100, unique=True)  # 对应 JSON 文件名
    title = models.CharField('标题', max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField('分类', max_length=100, blank=True)
    time_limit = models.IntegerField('时间限制(分钟)', null=True, blank=True)
    total_score = models.IntegerField('总分', default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

# 小测成绩（每学生每小测只存最高分）
class QuizResult(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    score = models.FloatField('得分')
    correct_count = models.IntegerField('正确题数')
    total_count = models.IntegerField('总题数')
    answers_json = models.TextField('学生答案(JSON)')  # 存学生提交的答案
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'quiz']  # 重复提交取最高分

# 课件资料
class Material(models.Model):
    material_id = models.CharField('课件ID', max_length=100, unique=True)
    title = models.CharField('标题', max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField('分类', max_length=100, blank=True)
    file_path = models.CharField('文件路径', max_length=255)  # 相对路径
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
```

---

## 4. API 设计

### 4.1 认证相关 — `/api/auth/`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login/` | 学生/老师登录（返回 token） |
| POST | `/api/auth/logout/` | 登出 |
| GET | `/api/auth/me/` | 获取当前用户信息 |

**登录请求体**：
```json
{
  "username": "张三",
  "password": "xxx",
  "grade": "初二",
  "class_num": "3班"
}
```
> 注意：Django 默认 User 表只有 username，没有 grade/class_num。登录时需要把这几个字段一起传，后端在 CustomUser 对象上验证年级+班级+用户名+密码是否匹配。

**响应（登录成功）**：
```json
{
  "token": "abc123...",
  "user": {
    "id": 1,
    "username": "张三",
    "role": "student",
    "grade": "初二",
    "class_num": "3班"
  }
}
```

### 4.2 AI课 — `/api/ai/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ai/problems/` | 题目列表 |
| GET | `/api/ai/problems/<id>/` | 题目详情 |
| POST | `/api/ai/submissions/` | 提交代码 |
| GET | `/api/ai/submissions/?problem_id=X` | 我的提交记录 |
| GET | `/api/ai/scores/` | 我的AI课成绩 |

### 4.3 信息科技课 — `/api/info/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/info/quizzes/` | 小测列表（含是否已做/最高分） |
| GET | `/api/info/quizzes/<id>/` | 小测详情（含题目） |
| POST | `/api/info/quizzes/<id>/submit/` | 提交小测答案 |
| GET | `/api/info/quizzes/<id>/result/` | 我的小测成绩 |
| GET | `/api/info/materials/` | 课件列表 |
| GET | `/api/info/materials/<id>/` | 课件详情（含文件路径） |

### 4.4 老师管理 — `/api/admin/`（需要老师权限）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/dashboard/` | 总览统计 |
| GET | `/api/admin/students/` | 学生列表 |
| GET | `/api/admin/ai/problems/` | AI课题目列表 |
| POST | `/api/admin/ai/problems/` | 新增题目 |
| GET | `/api/admin/info/quizzes/` | 信息课小测列表 |
| POST | `/api/admin/info/quizzes/` | 上传小测 JSON |
| GET | `/api/admin/info/materials/` | 课件列表 |
| POST | `/api/admin/info/materials/` | 上传课件 |

---

## 5. 前端项目结构

```
frontend/
    index.html                  # 入口页面（登录 + 路由分发）
    api/
        client.ts               # fetch 封装，统一处理 token
        auth.ts                  # 认证 API
        ai.ts                    # AI课 API
        info.ts                  # 信息科技课 API
    pages/
        login.html               # 登录页
        course_select.html       # 选课页
        # AI课学生端
        ai/
            dashboard.html       # AI课学生首页
            problem_list.html    # 题目列表
            problem_detail.html  # 做题页面
            my_scores.html       # 成绩查看
        # 信息科技课学生端
        info/
            dashboard.html       # 信息课学生首页
            quiz_list.html       # 小测列表
            quiz_take.html       # 做小测
            quiz_result.html     # 小测结果
            materials.html       # 课件查看
        # 老师端
        admin/
            dashboard.html       # 老师总览
            students.html        # 学生管理
            ai/
                problem_list.html
                problem_edit.html
            info/
                quiz_list.html
                quiz_edit.html
                material_list.html
    components/
        navbar.ts               # 顶部导航栏组件
        sidebar.ts               # 侧边栏
        quiz_card.ts            # 小测卡片组件
        material_card.ts        # 课件卡片组件
        modal.ts                # 弹窗组件
    styles/
        main.css                # 全局样式
        variables.css           # CSS 变量（颜色/字体）
        components.css          # 组件样式
    utils/
        router.ts               # 简单 hash 路由
        storage.ts              # localStorage 封装（存 token）
        date.ts                 # 日期格式化
```

**关于 TypeScript 的使用方式**：
- 用 Vite 构建时用 `.ts` 文件
- 如果想免构建环境，可以把 `.ts` 编译成 `.js` 或直接用 CDN 的 TypeScript（`<script src="https://cdn.jsdelivr.net/npm/typescript@5.0.4/lib/typescript.min.js">` 但实际项目中不推荐）
- **建议**：还是用 Vite 构建，本地开发 `npm run dev`，构建后发布静态文件到 Django `static/` 目录

---

## 6. Django settings.py 关键配置

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'users',
    'ai_courses',
    'info_tech',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # ...
]

AUTH_USER_MODEL = 'users.CustomUser'  # 使用自定义用户模型

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# CORS（如果前后端在不同端口）
INSTALLED_APPS += ['corsheaders']
MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware'] + MIDDLEWARE
CORS_ALLOW_ALL_ORIGINS = True  # 开发环境，生产环境限制域名
```

---

## 7. 权限设计

沿用你现有的角色思路（Django 自带 + 自定义权限）：

```python
# 老师能做的：
- 管理所有学生信息
- 上传/删除 AI课题目
- 上传/删除信息课小测 JSON
- 上传/删除课件
- 查看所有学生成绩（两门课）

# 学生能做的：
- 查看自己的 AI课题目列表、做题、提交、查看成绩
- 查看信息课小测列表、做小测、查看成绩
- 查看课件
```

权限判断用 DRF 的 `IsAuthenticated` + 自定义 permission class：

```python
class IsTeacher(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'teacher'

class IsOwnerOrTeacher(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'teacher':
            return True
        return obj.user == request.user
```

---

## 8. 文件存储结构

```
backend/
    media/                      # 上传的文件（Django media/ 目录）
        quizzes/                # 小测 JSON 文件
            computer_basics_01.json
        materials/             # 课件（HTML zip 解压后）
            computer_basics_01/
                index.html
                img/

frontend/
    dist/                       # Vite 构建输出
        index.html
        assets/
    src/                        # TypeScript 源码
```

Django `settings.py` 配置：
```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

---

## 9. 实施路线图

**第一阶段：Django 项目搭建** ✅ 已完成（2026-04-21）
1. 创建 Django 项目 + 三个 app
2. 配置 AUTH_USER_MODEL、DRF、CORS
3. 写 CustomUser model + migration
4. 实现 Token 认证 API（/api/auth/login/）
5. admin 后台配置好

**第二阶段：AI课 API 迁移** ✅ 已完成（2026-04-22）
> 现有 server.py 中的 AI课逻辑已迁移到 Django ai_courses/ app
1. Problem / TestCase / Submission models ✅
2. 题目列表/详情/提交/评分 API ✅
3. 成绩 API（/api/ai/scores/ + /api/ai/student_stats/）✅
4. 完成后：旧 server.py 正式退役 ✅
5. 遗留：Problem.sync_from_disk() 写操作从 GET 请求移至 POST 同步端点 ✅

**第三阶段：信息科技课 API** 📋 待开始
1. Quiz / Material / QuizResult models
2. Quiz API（列表/详情/提交/评分）
3. Material API（课件列表）
4. 老师上传小测 JSON（文件上传视图）
5. 权限配置

**第四阶段：前端开发** 🔄 进行中（Vite + JS）
> 学生端基础已完成，老师端待开发
1. 项目初始化（Vite + JS，当前用 JS，暂缓 TS）🔄
2. 登录页 + Token 管理（api/client.ts）✅
3. 选课页（/student）✅
4. AI课学生端（题目列表/提交/成绩查看）✅
5. 信息科技课学生端（做小测为核心）📋
6. 老师管理后台（评分 + 双课统一视图）📋

**第五阶段：收尾** 📋 待开始
1. 课件上传功能（ZIP 解压）
2. 合并老师后台（两门课在一个界面）
3. 部署到服务器

---

## 10. 关键技术决策

| 决策点 | 方案 | 理由 |
|--------|------|------|
| 认证方式 | DRF Token Authentication | 简单，够用 |
| 前端路由 | Hash 路由（window.location.hash） | 无需服务器配置，GitHub Pages 也能跑 |
| 小测 JSON 解析 | 后端读取文件，题目全量返回前端 | 题目数量少，无需分页 |
| 评分方式 | 后端评分，返回结果 | 防止学生篡改答案 |
| 课件存储 | 文件系统（media/） | 比数据库存文件更高效 |
| 现有 users.db | 不迁移 | 现有 AI课系统独立运行 |

---

## 11. 信息科技课 — 完整设计（2026-04-22）

> **需求摘要（Alex 确认版）**
> - 教师后台：管理每个单元题库，增删改查小测（指定题目数量/范围/可见性/年级）
> - 学生端：随机抽题 + 随机打乱选项答题，支持重新作答（重新抽题），成绩最新覆盖

---

### 11.1 数据模型

```python
# =====================
# info_tech/models.py
# =====================

class Unit(models.Model):
    """单元目录（年级-大单元-小节 三级结构）"""
    name         = models.CharField('单元名称', max_length=100)         # 如 "第一单元"（大单元）或 "1.1 信息及其特征"（小节）
    display_name = models.CharField('显示名称', max_length=200, blank=True) # 如 "第一单元：走进人工智能"
    grade        = models.CharField('年级', max_length=20, blank=True)   # 如 "七年级"，大单元有值，小节继承
    order        = models.IntegerField('排序', default=0)
    parent       = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sections')
    # parent = null → 大单元（big_unit）；parent = Unit.id → 小节（section）
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['grade', 'order']

    def __str__(self):
        return f"{self.grade} - {self.name}"


class Question(models.Model):
    """题库题目（单选）"""
    DIFFICULTY_CHOICES = [
        ('easy',   '容易'),
        ('medium', '中等'),
        ('hard',   '困难'),
    ]

    unit         = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='questions')
    difficulty    = models.CharField('难度', max_length=10, choices=DIFFICULTY_CHOICES, default='easy')
    category     = models.CharField('知识点分类', max_length=100, blank=True)   # 如 "网络层级结构"
    grade        = models.CharField('年级', max_length=20, blank=True)            # 冗余字段，方便按年级筛选题库
    text         = models.TextField('题目正文')                                    # 含题目的完整文字
    answer       = models.CharField('正确答案', max_length=1)                       # 'A'/'B'/'C'/'D'
    explanation  = models.TextField('答案解析', blank=True)
    # 选项固定 A/B/C/D 四个，题目本身不存选项顺序（打乱在视图层做）
    option_a     = models.CharField('选项A', max_length=500)
    option_b     = models.CharField('选项B', max_length=500)
    option_c     = models.CharField('选项C', max_length=500)
    option_d     = models.CharField('选项D', max_length=500)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '题目'
        verbose_name_plural = '题库'

    def __str__(self):
        return f"{self.unit.name} - {self.text[:30]}..."


class QuizSession(models.Model):
    """老师发起的一场小测（配置型，不是预抽题）"""
    title          = models.CharField('小测标题', max_length=200)        # 如 "第四单元小测"
    created_by     = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    # 组题配置
    units          = models.ManyToManyField(Unit, related_name='quiz_sessions')  # 出题范围（大单元，被选中时自动包含其所有小节下的题目）
    num_questions  = models.IntegerField('题目数量')                              # 如 20
    difficulty_ratio = models.JSONField('难度比例', default=dict)                  # {"easy":7,"medium":2,"hard":1}
    time_limit     = models.IntegerField('时间限制(分钟)', null=True, blank=True)

    # 可见性
    is_visible     = models.BooleanField('对学生可见', default=False)
    visible_grades = models.JSONField('可见年级', default=list)                     # [] 表示全部年级可见

    # 防作弊：学生每次进入随机抽题，不需要存题
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class QuizSubmission(models.Model):
    """学生提交记录（每次作答都存，最新覆盖）"""
    user           = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    session        = models.ForeignKey(QuizSession, on_delete=models.CASCADE)
    score          = models.FloatField('得分')                       # 百分比，如 85.0
    correct_count  = models.IntegerField('正确题数')
    total_count    = models.IntegerField('总题数')
    answers_json   = models.TextField('学生答案')                    # {"q_id_1":"A", "q_id_2":"C", ...}
    submitted_at   = models.DateTimeField(auto_now_add=True)

    # 注意：没有 unique_together，成绩每次都保存，视图层返回最新一条
    # 如需取最高分，查 max(score) 即可

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = '小测提交'
        verbose_name_plural = '小测提交记录'

    def __str__(self):
        return f"{self.user.display_name} - {self.session.title}: {self.score}分"
```

**关键设计决策说明：**

1. **题目不预抽**：每次学生进入答题页时才随机抽题（`random.sample` 从 `session.units.all()` 的 Question 里选），这样每次作答都是全新的随机题目。

2. **选项不打存在数据库**：选项 A/B/C/D 固定字段，视图层返回时用 `random.shuffle` 打乱选项顺序，返回带 `shuffled_options` 的结构给学生。

3. **成绩最新覆盖**：提交记录全部保留（方便老师查看历史），学生端取 `submitted_at` 最新的一条作为"当前成绩"，最高分逻辑在查询层做 `Max('score')`。

4. **难度比例**：创建小测时指定 `{"easy":7,"medium":2,"hard":1}`，随机抽题时按比例分配名额。

5. **年级-大单元-小节三级结构**：Unit.parent=null 为大单元（属于某个年级），Unit.parent=Unit.id 为小节（属于某大单元）。大单元选中时，题目来源为该大单元下所有小节的 Question。

6. **QuizSubmission.grade 冗余字段**：数据库存学生作答时的 grade（如"七年级"），方便按年级筛选统计，不依赖 User 表。

---

### 11.2 JSON 导入格式（题库批量导入）

**题目库导入**（`POST /api/admin/info/questions/import/`）：

```json
{
  "unit": "第四单元",
  "unit_display_name": "第四单元：搭建校园网络系统——互联网的基本原理",
  "questions": [
    {
      "difficulty": "easy",
      "category": "网络层级结构",
      "text": "按照覆盖范围从小到大排列，网络的正确顺序是（）",
      "options": [
        {"key": "A", "text": "局域网 → 城域网 → 广域网"},
        {"key": "B", "text": "广域网 → 城域网 → 局域网"},
        {"key": "C", "text": "城域网 → 局域网 → 广域网"},
        {"key": "D", "text": "局域网 → 广域网 → 城域网"}
      ],
      "answer": "A",
      "explanation": "根据复习提纲，网络按覆盖范围分为局域网（LAN，覆盖范围最小，如学校内部）、城域网（MAN，覆盖一个城市）、广域网（WAN，覆盖大范围地理区域）。"
    }
  ]
}
```

> 和 Alex 现有的 HTML 小测题里的 `QUESTIONS_RAW` 数据结构完全一致，导入脚本只需要把 JS 对象语法转成 JSON 即可直接导入。

**单个题目编辑**（`POST /api/admin/info/questions/`）：
```json
{
  "unit": "第四单元",
  "difficulty": "easy",
  "category": "网络层级结构",
  "text": "按照覆盖范围从小到大排列，网络的正确顺序是（）",
  "option_a": "局域网 → 城域网 → 广域网",
  "option_b": "广域网 → 城域网 → 局域网",
  "option_c": "城域网 → 局域网 → 广域网",
  "option_d": "局域网 → 广域网 → 城域网",
  "answer": "A",
  "explanation": "根据复习提纲..."
}
```

---

### 11.3 API 设计

#### 11.3.1 学生端 — `/api/info/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/info/units/` | 单元列表（含题目数量） |
| GET | `/api/info/sessions/` | 可见的小测列表（只返回 `is_visible=True` 且年级匹配的） |
| GET | `/api/info/sessions/{id}/` | **进入答题页**，后端随机抽题 + 打乱选项，返回给前端 |
| POST | `/api/info/sessions/{id}/submit/` | 提交答案，后端评分，返回结果（含错题解析） |
| GET | `/api/info/submissions/?session={id}` | 我的某次小测提交记录（最新一条是当前成绩） |
| GET | `/api/info/submissions/{id}/result/` | 某次提交的成绩详情（含每题对错） |

**GET `/api/info/sessions/{id}/` 返回（学生看到的题目）：**

```json
{
  "session_id": 1,
  "title": "第四单元小测",
  "time_limit": 40,
  "total_count": 20,
  "questions": [
    {
      "q_id": 12,
      "text": "按照覆盖范围从小到大排列...",
      "shuffled_options": [
        {"key": "C", "text": "城域网 → 局域网 → 广域网"},
        {"key": "A", "text": "局域网 → 城域网 → 广域网"},
        {"key": "D", "text": "局域网 → 广域网 → 城域网"},
        {"key": "B", "text": "广域网 → 城域网 → 局域网"}
      ]
    }
    // ... 共 20 题
  ]
}
```

> **注意**：返回的题目里没有 `answer` 字段，评分在后端做。

**POST `/api/info/sessions/{id}/submit/` 请求体：

```json
{
  "answers": {"12": "A", "15": "C", "8": "B"}
}
```

> `answers` 的 key 是后端返回的 `q_id`，value 是学生选择的选项 key（'A'/'B'/'C'/'D'）。

**返回（提交后成绩）：**

```json
{
  "submission_id": 5,
  "score": 85.0,
  "correct_count": 17,
  "total_count": 20,
  "review": [
    {
      "q_id": 12,
      "text": "按照覆盖范围从小到大排列...",
      "your_answer": "A",
      "correct_answer": "A",
      "is_correct": true,
      "explanation": "...",
      "shuffled_options": [...]
    },
    {
      "q_id": 15,
      "text": "...",
      "your_answer": "C",
      "correct_answer": "B",
      "is_correct": false,
      "explanation": "...",
      "shuffled_options": [...]
    }
  ]
}
```

#### 11.3.2 教师管理端 — `/api/admin/info/`

|| 方法 | 路径 | 说明 |
||------|------|------|
|| GET | `/api/admin/info/units/` | 单元列表（支持 `?grade=` 过滤，返回嵌套结构） |
|| POST | `/api/admin/info/units/` | 新增单元（`grade`/`parent` 字段） |
|| PUT | `/api/admin/info/units/{id}/` | 修改单元 |
|| DELETE | `/api/admin/info/units/{id}/delete/` | 删除单元 |
|| GET | `/api/admin/info/questions/` | 题库列表（支持 `?grade=&unit=&difficulty=&q=` 过滤） |
|| POST | `/api/admin/info/questions/` | 新增单题 |
|| PUT | `/api/admin/info/questions/{id}/` | 修改题目 |
|| DELETE | `/api/admin/info/questions/{id}/delete/` | 删除题目 |
|| POST | `/api/admin/info/questions/import/` | **批量导入 JSON**（一次性导入整个单元） |
|| GET | `/api/admin/info/sessions/` | 小测列表 |
|| POST | `/api/admin/info/sessions/` | **创建小测**（选单元+定题量+难度比例+可见性） |
|| PUT | `/api/admin/info/sessions/{id}/` | 修改小测（增删改范围/题量/可见性） |
|| DELETE | `/api/admin/info/sessions/{id}/delete/` | 删除小测 |
|| GET | `/api/admin/info/stats/submissions/` | 成绩统计（支持 `?grade=&class_num=` 过滤，返回5×10矩阵） |
|| GET | `/api/admin/info/stats/overview/` | 全班统计概览（正确率分布） |
|| GET | `/api/admin/info/submissions/` | 某次小测的全班成绩（支持 `?session=&grade=&class_num=`） |

**POST `/api/admin/info/sessions/` 请求体：

```json
{
  "title": "第四单元小测",
  "units": [3, 4],
  "num_questions": 20,
  "difficulty_ratio": {"easy": 14, "medium": 4, "hard": 2},
  "time_limit": 40,
  "is_visible": false,
  "visible_grades": []
}
```

**`visible_grades` 说明**：
- `[]` = 全部年级可见
- `["初二"]` = 只有初二可见
- `["初二","初三"]` = 初二初三可见

---

### 11.4 随机抽题算法（后端 Python）

```python
import random

def draw_questions(session: QuizSession) -> list[Question]:
    """根据小测配置，从题库随机抽取题目"""
    ratio = session.difficulty_ratio  # {"easy":7,"medium":2,"hard":1}
    total = session.num_questions
    units = session.units.all()

    # 按难度分组
    questions = Question.objects.filter(unit__in=units)
    by_difficulty = {
        'easy':   list(questions.filter(difficulty='easy')),
        'medium': list(questions.filter(difficulty='medium')),
        'hard':   list(questions.filter(difficulty='hard')),
    }

    result = []
    for diff, count in ratio.items():
        count = min(count, len(by_difficulty[diff]))  # 题不够就全抽
        result.extend(random.sample(by_difficulty[diff], count))

    random.shuffle(result)  # 最终打乱题目顺序
    return result[:total]


def shuffle_options(question: Question) -> list:
    """打乱单个题目的选项顺序"""
    options = [
        {'key': 'A', 'text': question.option_a},
        {'key': 'B', 'text': question.option_b},
        {'key': 'C', 'text': question.option_c},
        {'key': 'D', 'text': question.option_d},
    ]
    random.shuffle(options)
    return options
```

---

### 11.5 前端页面结构

> **设计原则**：最小改动，复用现有页面和路由，新增页面尽量少。**
>
> - 学生端：复用 `StudentDashboard?course=info`，答题新建 `QuizPage`；AI课保持原样
> - 教师端：复用 `ProblemManagement` 和 `ScoreManagement` 的 `selectedCourse` 下拉框架构，扩展 info 接口；题库/小测管理新建页面

#### 11.5.1 文件结构

```
frontend/src/
  pages/
    student/
      StudentDashboard.jsx   ← 改动：course=info 时渲染小测卡片列表
      info/
        QuizPage.jsx        ← 新增：答题页（随机抽题展示+提交+重做）
        QuizResult.jsx      ← 新增：成绩+错题解析页

    teacher/
      TeacherDashboard.jsx  ← 已简化：删除课程Tab栏，保留3个管理卡片入口
      StudentManagement.jsx ← 学生管理（年级+班级筛选）
      AiAdmin.jsx           ← 新增（2026-04-23）：AI课题库管理(Tab0)+成绩统计(Tab1)
      InfoAdmin.jsx          ← 改动（2026-04-23）：Tab移至Header；Tab0=单元管理 + Tab1=题库管理 + Tab2=小测管理 + Tab3=成绩统计
  # 已删除：
  #   ProblemManagement.jsx  → 合并入 aiAdmin.jsx
  #   ScoreManagement.jsx    → 合并入 aiAdmin.jsx
```

#### 11.5.2 路由（App.jsx）

|| 路由 | 页面 | 说明 |
||------|------|------|
|| `/student/dashboard?course=info` | StudentDashboard | 复用，小测卡片列表 |
|| `/student/quiz/:sessionId` | QuizPage | 答题页 |
|| `/student/quiz-result/:submissionId` | QuizResult | 成绩+错题解析 |
|| `/teacher/dashboard` | TeacherDashboard | 老师首页（3卡片：AI课管理/信息课管理/学生管理） |
|| `/teacher/ai` | AiAdmin | AI课管理（Tab0题库+Tab1成绩统计） |
|| `/teacher/info` | InfoAdmin | 信息课管理（Header内Tab：单元/题库/小测/成绩统计） |
|| `/teacher/students` | StudentManagement | 学生管理 |
|| ~~`/teacher/problems`~~ | — | 已删除（合并入 AiAdmin） |
|| ~~`/teacher/scores`~~ | — | 已删除（合并入 AiAdmin） |

#### 11.5.3 StudentDashboard 改动说明

**现有逻辑（course=ai）**：API 返回 Problem 列表 → 渲染编程题卡片 → 点进去是 ProblemDetail

**改动后（course=info）**：
- 调用 `getInfoSessions()` → 返回可见小测列表
- 渲染小测卡片（标题 + 题目数量 + 状态：未做/已做/查看成绩）
- 点卡片 → 跳转 `/student/quiz/:sessionId`（QuizPage）
- 点"查看成绩" → 跳转 `/student/quiz-result/:submissionId`（QuizResult）

现有 AI课逻辑**完全不动**，同一个组件用 `getCourse()` 判断走哪套渲染逻辑。

---

### 11.6 进度追踪

|| 功能 | 状态 | 完成日期 |
||------|------|----------|
|| **后端** | | |
|| 数据模型（Unit/Question/QuizSession/QuizSubmission） | ✅ 完成 | 2026-04-22 |
|| Unit 三级结构（grade + parent）| ✅ 完成 | 2026-04-23 |
|| 题库管理 API（增删改查+JSON导入） | ✅ 完成 | 2026-04-22 |
|| 小测管理 API（创建+发布+修改+删除） | ✅ 完成 | 2026-04-22 |
|| 学生随机抽题 API | ✅ 完成 | 2026-04-22 |
|| 学生提交+评分 API（含错题解析） | ✅ 完成 | 2026-04-22 |
|| 成绩统计 API（含5×10矩阵，`?grade=&class_num=`过滤） | ✅ 完成 | 2026-04-23 |
|| **前端** | | |
|| 教师端合并（AiAdmin + InfoAdmin + TeacherDashboard） | ✅ 完成 | 2026-04-23 |
|| AiAdmin（Tab0题库管理 + Tab1成绩统计） | ✅ 完成 | 2026-04-23 |
|| InfoAdmin（Header内Tab：单元/题库/小测/成绩统计） | ✅ 完成 | 2026-04-23 |
|| TeacherDashboard 简化（删除课程Tab，3卡片入口） | ✅ 完成 | 2026-04-23 |
|| 七年级/八年级 单元目录预导入 | ✅ 完成 | 2026-04-23 |
|| **待开发** | | |
|| HTML 题目转 JSON 导入脚本 | 📋 待开发 | — |
|| AI课教师端 Tab 合并（题库+成绩） | ✅ 完成 | 2026-04-23 |
|| 学生端信息课 QuizPage + QuizResult | ✅ 完成 | 2026-04-22 |
|| 课件上传功能（ZIP 解压） | 📋 待开发 | — |
