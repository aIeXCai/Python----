# Python 学习平台：在另一台电脑运行

本文只说明一件事：把项目从 GitHub 克隆到另一台电脑，然后使用本地 SQLite 数据库运行。

这种方式不需要安装 MySQL、Nginx 或 Docker，适合在另一台电脑继续开发、演示和验收网站。

## 1. 准备环境

新电脑需要安装：

- Git
- Python 3.10 或更高版本
- Node.js 20.19+ 或 22.12+

检查版本：

```bash
git --version
python3 --version
node --version
npm --version
```

Windows 如果没有 `python3` 命令，后续使用 `python`。

## 2. 从 GitHub 克隆项目

```bash
git clone https://github.com/aIeXCai/Python----.git
cd Python----
```

克隆完成后，项目根目录中应当能看到：

```text
backend/
frontend/
problems/
requirements.txt
start_all.sh
start_all.bat
```

## 3. 创建 Python 虚拟环境

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install "django>=5.0" djangorestframework django-cors-headers \
  python-dotenv "cryptography>=44,<47" "openai>=1.0.0" requests
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install "django>=5.0" djangorestframework django-cors-headers python-dotenv "cryptography>=44,<47" "openai>=1.0.0" requests
```

这里没有使用根目录的 `requirements.txt`，因为其中包含正式 MySQL 环境需要的 `mysqlclient`；本地 SQLite 运行不需要它，也不需要安装 MySQL 开发库。

如果 PowerShell 阻止激活虚拟环境，可为当前用户执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

以后每次重新打开终端，都要先进入项目目录并激活虚拟环境。

## 4. 生成本地学生密码加密密钥

该密钥只保存在新电脑本地，不会上传 GitHub。没有它时，教师创建学生或查看学生密码的功能无法正常工作。

### macOS/Linux

在项目根目录执行：

```bash
bash scripts/stage3_security_local.sh init
```

成功时会生成被 Git 忽略的：

```text
backend/.env.security.local
```

macOS 可以继续验证密钥配置：

```bash
bash scripts/stage3_security_local.sh status
```

Linux 当前使用下面的命令检查文件权限，预期输出 `600`：

```bash
stat -c '%a' backend/.env.security.local
```

### Windows PowerShell

在项目根目录执行：

```powershell
$key = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
@"
DJANGO_STUDENT_PASSWORD_KEYS=stage3-v1:$key
DJANGO_STUDENT_PASSWORD_PRIMARY_KEY_ID=stage3-v1
DJANGO_TOKEN_TTL_HOURS=12
DJANGO_PASSWORD_REVEAL_LIMIT=30
DJANGO_PASSWORD_REVEAL_SECONDS=30
"@ | Set-Content -Encoding ascii backend\.env.security.local
```

不要把 `backend/.env.security.local` 提交到 GitHub。

## 5. 初始化本地 SQLite 数据库

项目默认使用 SQLite，因此不需要安装 MySQL。

### macOS/Linux

```bash
cd backend
DJANGO_ENV=development DJANGO_DB_ENGINE=sqlite python manage.py migrate
DJANGO_ENV=development DJANGO_DB_ENGINE=sqlite python manage.py loaddata \
  info_tech/fixtures/current_curriculum.json \
  ai_courses/fixtures/current_ai_catalog.json
```

### Windows PowerShell

```powershell
cd backend
$env:DJANGO_ENV = "development"
$env:DJANGO_DB_ENGINE = "sqlite"
python manage.py migrate
python manage.py loaddata info_tech/fixtures/current_curriculum.json ai_courses/fixtures/current_ai_catalog.json
```

导入成功时会显示：

```text
Installed 102 object(s) from 2 fixture(s)
```

导入后包括：

- 58 个信息课单元及小节
- 17 道信息课题目
- 9 道 AI 课题目
- 18 条 AI 题目可见范围

这一步只应在新生成的空数据库中执行一次。重复执行可能发生主键冲突。

## 6. 创建教师管理员账号

保持在 `backend/` 目录：

```bash
python manage.py createsuperuser
```

按照提示输入管理员用户名、邮箱和密码。

创建完成后，把该账号设置为教师角色。将下面的 `你的用户名` 替换为刚才创建的用户名：

```bash
python manage.py shell -c "from users.models import CustomUser; u=CustomUser.objects.get(username='你的用户名'); u.role='teacher'; u.is_staff=True; u.is_superuser=True; u.save(update_fields=['role','is_staff','is_superuser']); print('教师管理员已配置')"
```

Windows PowerShell 也可以执行同一条命令。

## 7. 安装前端依赖

回到项目根目录，然后进入前端：

```bash
cd ..
cd frontend
npm ci
```

`npm ci` 会根据仓库中的 `package-lock.json` 安装前端依赖。

## 8. 启动网站

网站需要同时启动 Django 后端和 Vite 前端。

### 终端一：启动后端

macOS/Linux：

```bash
cd Python----
source .venv/bin/activate
cd backend
DJANGO_ENV=development DJANGO_DB_ENGINE=sqlite python manage.py runserver 8080
```

Windows PowerShell：

```powershell
cd Python----
.\.venv\Scripts\Activate.ps1
cd backend
$env:DJANGO_ENV = "development"
$env:DJANGO_DB_ENGINE = "sqlite"
python manage.py runserver 8080
```

看到下面的地址表示后端已启动：

```text
http://127.0.0.1:8080/
```

### 终端二：启动前端

```bash
cd Python----/frontend
npm run dev
```

看到下面的地址表示前端已启动：

```text
http://localhost:5173/
```

## 9. 打开网站

- 学生登录：<http://localhost:5173/login>
- 教师登录：<http://localhost:5173/teacher-login>
- 后端存活检查：<http://localhost:8080/api/health/live/>
- 数据库检查：<http://localhost:8080/api/health/ready/>

使用第 6 步创建的教师管理员账号登录教师端。

新数据库没有学生账号和小测场次。登录教师端后，可以创建测试学生，再创建并开放一个信息课小测。

## 10. 什么算运行成功

满足以下条件即表示项目已经在新电脑跑通：

1. 教师管理员能够登录。
2. 教师端能够看到信息课单元、题目和 AI 题目。
3. 教师能够创建测试学生和信息课小测。
4. 学生能够登录、看到课程并完成一次小测。
5. 教师端能够看到学生最近一次小测成绩。

当前 Docker Runner 尚未完成，因此学生代码运行和自动评测不可用属于已知限制，不影响上述本地验收。

## 11. 停止网站

分别在两个运行服务的终端按：

```text
Ctrl + C
```

即可停止 Django 和 Vite。

## 12. 下次重新启动

不需要重新执行 migration、`loaddata` 或 `npm ci`。

只需打开两个终端，分别重新启动后端和前端：

```bash
# 终端一
cd Python----
source .venv/bin/activate
cd backend
DJANGO_ENV=development DJANGO_DB_ENGINE=sqlite python manage.py runserver 8080
```

```bash
# 终端二
cd Python----/frontend
npm run dev
```

Windows 使用对应的虚拟环境激活命令和 PowerShell 环境变量命令。

## 13. 从 GitHub 获取后续更新

停止前后端服务后，在项目根目录执行：

```bash
git pull --ff-only origin main
source .venv/bin/activate
pip install "django>=5.0" djangorestframework django-cors-headers \
  python-dotenv "cryptography>=44,<47" "openai>=1.0.0" requests
cd backend
DJANGO_ENV=development DJANGO_DB_ENGINE=sqlite python manage.py migrate
cd ../frontend
npm ci
```

Windows 将 `source .venv/bin/activate` 换成：

```powershell
.\.venv\Scripts\Activate.ps1
```

不要再次执行 `loaddata`，除非本地数据库已经删除并准备从头恢复。

## 14. 常见问题

### 前端页面能打开，但无法登录

通常是 Django 后端没有启动。确认终端一仍在运行，并访问：

<http://localhost:8080/api/health/live/>

### 出现 “No module named django”

说明没有激活虚拟环境，或尚未安装后端依赖：

```bash
source .venv/bin/activate
pip install "django>=5.0" djangorestframework django-cors-headers \
  python-dotenv "cryptography>=44,<47" "openai>=1.0.0" requests
```

### 出现 “npm: command not found”

说明 Node.js 没有正确安装或没有加入系统 `PATH`。

### 出现端口被占用

检查是否已经启动过项目。也可以停止占用 `8080` 或 `5173` 的旧进程后再启动。

### 教师无法创建学生或查看学生密码

检查本地密钥文件是否存在：

```text
backend/.env.security.local
```

macOS 可运行：

```bash
bash scripts/stage3_security_local.sh status
```

Linux 可运行 `stat -c '%a' backend/.env.security.local`，预期权限为 `600`。

### 教学内容重复或导入失败

`loaddata` 只用于新的空数据库。已经成功导入过 102 个对象后，不要再次执行。

## 15. 本地文件说明

以下文件只存在于新电脑本地，不会被 Git 上传：

- `.venv/`：Python 虚拟环境。
- `frontend/node_modules/`：前端依赖。
- `backend/db.sqlite3`：本地账号、题目、作答和成绩数据库。
- `backend/.env.security.local`：学生密码加密密钥。
- `frontend/dist/`：前端生产构建文件，本地运行 `npm run dev` 时不需要。

如果以后要把新电脑上的学生账号和成绩迁移到另一台电脑，需要单独安全迁移 `backend/db.sqlite3` 和对应的 `backend/.env.security.local`，不能只依赖 Git。
