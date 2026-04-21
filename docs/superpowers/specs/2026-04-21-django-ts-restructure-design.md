# 项目重构设计方案：Django REST + TypeScript 前端

**作者**: Alex 老师 & Hermes Agent
**日期**: 2026-04-21
**状态**: 进行中（第一阶段 ✅ | 第三阶段 🔄 AI课迁移（优先）| 第二阶段 🔄 进行中）

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

**第二阶段：AI课 API 迁移（优先）** 🔄 进行中
> 将现有 server.py 中的 AI课逻辑迁移到 Django ai_courses/ app
1. Problem / TestCase / Submission models
2. 题目列表/详情/提交/评分 API
3. 成绩 API
4. 完成后：旧 server.py 正式退役

**第三阶段：信息科技课 API** 📋 待开始
1. Quiz / Material / QuizResult models
2. Quiz API（列表/详情/提交/评分）
3. Material API（课件列表）
4. 老师上传小测 JSON（文件上传视图）
5. 权限配置

**第四阶段：前端开发** 📋 待开始
1. 项目初始化（Vite + TypeScript）
2. 登录页 + Token 管理（api/client.ts）
3. 选课页
4. 信息科技课学生端（做小测为核心）
5. AI课学生端
6. 老师管理后台

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
