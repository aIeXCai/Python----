# Python 学习平台：新电脑部署指南

本文说明从 GitHub 克隆项目后，如何在一台新电脑上恢复教学内容并启动网站。项目包含 React 前端、Django 后端和 MySQL 数据库；正式对外部署推荐使用 Ubuntu + Gunicorn + Nginx。

> 当前独立代码 Runner 与 Docker 沙箱尚未完成。部署期间必须设置 `CODE_EXECUTION_ENABLED=false`，网站的登录、课程、题库、小测和成绩功能可以使用，但学生代码运行与自动评测暂不开放。

## 1. 部署后会恢复什么

Git 仓库包含：

- 前后端源代码和数据库 migration。
- 9 道 AI 题目的描述、模板、测试输入与标准输出。
- 9 道 AI 题目的数据库元数据和 18 条发布范围。
- 58 个信息课单元/小节和 17 道信息课题目。

Git 仓库不包含：

- `.env` 中的数据库密码、Django 密钥、学生密码加密密钥和 AI API Key。
- 教师、学生账号及其密码。
- 学生作答、成绩、聊天记录和历史小测场次。
- 原电脑上的 MySQL 数据库、Python 虚拟环境和 `node_modules`。

如果新电脑需要保留旧电脑的账号和成绩，不能只执行本文的教学内容导入，还需要单独进行完整数据库迁移。

## 2. 环境要求

- Git。
- Python 3.10 或更高版本；推荐使用当前已验证的 Python 3.13。
- Node.js 20.19+ 或 22.12+；推荐 Node.js 22 LTS。
- MySQL 8.0.x。
- Nginx：本地开发可以不安装，正式部署需要安装。

检查已有环境：

```bash
git --version
python3 --version
node --version
npm --version
```

Windows 中如果没有 `python3` 命令，使用 `python`。

## 3. 克隆代码

```bash
git clone https://github.com/aIeXCai/Python----.git
cd Python----
```

以后本文中的“项目根目录”均指克隆后包含 `backend/`、`frontend/` 和 `requirements.txt` 的目录。

## 4. 安装 MySQL 和 Nginx

### 4.1 Ubuntu 22.04/24.04（正式部署推荐）

```bash
sudo apt update
sudo apt install -y mysql-server nginx \
  build-essential pkg-config python3-dev python3-venv \
  default-libmysqlclient-dev

sudo systemctl enable --now mysql
sudo systemctl enable --now nginx

mysql --version
nginx -v
sudo systemctl status mysql --no-pager
sudo systemctl status nginx --no-pager
```

项目已针对 MySQL 8.0 验证。如果系统仓库提供的不是 8.0.x，请按照 MySQL 官方 APT Repository 文档安装 8.0，不要在未验证的数据库大版本上直接上线。

### 4.2 macOS（适合本地开发和验收）

先安装 [Homebrew](https://brew.sh/)，然后执行：

```bash
brew install mysql@8.0 nginx pkg-config
brew services start mysql@8.0
brew services start nginx

echo 'export PATH="/opt/homebrew/opt/mysql@8.0/bin:$PATH"' >> ~/.zprofile
source ~/.zprofile

mysql --version
nginx -v
```

Intel Mac 的 Homebrew 通常位于 `/usr/local`。如果上面的 MySQL 路径不存在，执行 `brew --prefix mysql@8.0` 查看实际路径并加入 `PATH`。

### 4.3 Windows 10/11（仅建议本地验收）

1. 从 [MySQL Installer](https://dev.mysql.com/downloads/installer/) 下载 MySQL 8.0 Installer。
2. 选择 `Server Only`，安装 MySQL Server 8.0，并设置 root 管理密码。
3. 将 MySQL 配置为 Windows 服务，确认服务已启动。
4. 将 MySQL 的 `bin` 目录加入 `PATH`，然后在 PowerShell 执行 `mysql --version`。

Nginx 官方 Windows 版本仍被标记为 beta，不适合作为正式课堂服务器。Windows 本地验收可直接使用 Django + Vite；正式部署请使用 Ubuntu 服务器。

## 5. 创建 Python 虚拟环境并安装后端依赖

### macOS/Linux

```bash
cd Python----
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
cd Python----
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果 PowerShell 禁止激活脚本，可为当前用户执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

如果 `mysqlclient` 安装失败：

- Ubuntu：确认已安装 `default-libmysqlclient-dev`、`pkg-config` 和 `python3-dev`。
- macOS：确认已安装 `mysql@8.0` 和 `pkg-config`，并重新打开终端。
- Windows：优先使用与当前 Python 版本兼容的预编译 wheel；正式部署建议切换到 Ubuntu。

## 6. 安装前端依赖

```bash
cd frontend
npm ci
npm run build
cd ..
```

成功后会生成 `frontend/dist/`。该目录由当前电脑构建，不提交 Git。

## 7. 创建 MySQL 数据库和专用账号

进入 MySQL 管理终端：

```bash
sudo mysql
```

macOS 或 Windows 如果 `sudo mysql` 不可用，使用：

```bash
mysql -u root -p
```

在 MySQL 中执行以下 SQL。请把示例密码替换为新的强密码：

```sql
CREATE DATABASE python_learning
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER 'python_learning'@'localhost'
  IDENTIFIED BY '请替换为新的数据库强密码';

GRANT ALL PRIVILEGES ON python_learning.*
  TO 'python_learning'@'localhost';

FLUSH PRIVILEGES;
EXIT;
```

验证账号：

```bash
mysql -u python_learning -p -h 127.0.0.1 python_learning
```

连接成功后执行 `EXIT;` 退出。不要把真实数据库密码写进 README、Git commit、聊天记录或终端截图。

## 8. 创建后端环境变量

在项目根目录执行：

```bash
cp backend/.env.example backend/.env
```

Windows PowerShell 使用：

```powershell
Copy-Item backend\.env.example backend\.env
```

先生成两个互不相同的密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

编辑 `backend/.env`，至少正确填写以下内容：

```dotenv
DJANGO_ENV=production
DJANGO_SECRET_KEY=粘贴第一条命令生成的Django密钥
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=你的域名或服务器IP
DJANGO_CORS_ALLOWED_ORIGINS=
DJANGO_CSRF_TRUSTED_ORIGINS=https://你的域名
DJANGO_LOG_LEVEL=INFO

DJANGO_DB_ENGINE=mysql
DJANGO_DB_NAME=python_learning
DJANGO_DB_USER=python_learning
DJANGO_DB_PASSWORD=第7步设置的数据库密码
DJANGO_DB_HOST=127.0.0.1
DJANGO_DB_PORT=3306
DJANGO_DB_CONN_MAX_AGE=60
DJANGO_DB_CONNECT_TIMEOUT=5
DJANGO_DB_TEST_NAME=test_python_learning

DJANGO_STUDENT_PASSWORD_KEYS=stage3-v1:粘贴第二条命令生成的Fernet密钥
DJANGO_STUDENT_PASSWORD_PRIMARY_KEY_ID=stage3-v1
DJANGO_TOKEN_TTL_HOURS=12
DJANGO_PASSWORD_REVEAL_LIMIT=30
DJANGO_PASSWORD_REVEAL_SECONDS=30

CODE_EXECUTION_ENABLED=false
RUNNER_SERVICE_SECRET=

DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true

MINIMAX_API_KEY=需要AI助手时填写真实Key
```

说明：

- 使用域名时，`DJANGO_ALLOWED_HOSTS` 只写主机名，如 `learn.example.com`。
- `DJANGO_CSRF_TRUSTED_ORIGINS` 必须包含协议，如 `https://learn.example.com`。
- 如果只是局域网 HTTP 验收，暂时把三个 `DJANGO_*_SECURE` 变量设为 `false`，并把 CSRF 来源改为实际访问地址；正式公网部署完成 HTTPS 后再全部改为 `true`。
- `.env` 已被 `.gitignore` 排除，不要使用 `git add -f` 上传。
- 如果从旧数据库迁移学生数据，必须使用旧环境的学生密码加密密钥，否则教师无法解密查看原密码。

## 9. 初始化数据库并恢复教学内容

```bash
cd backend
python manage.py check --database default
python manage.py migrate
python manage.py loaddata \
  info_tech/fixtures/current_curriculum.json \
  ai_courses/fixtures/current_ai_catalog.json
```

Windows PowerShell 可把最后一条命令写成一行：

```powershell
python manage.py loaddata info_tech/fixtures/current_curriculum.json ai_courses/fixtures/current_ai_catalog.json
```

预期提示：

```text
Installed 102 object(s) from 2 fixture(s)
```

这些 fixture 适合全新数据库。已有教学数据的数据库可能发生主键冲突，导入前必须先备份。

检查恢复数量：

```bash
python manage.py shell -c "from info_tech.models import Unit,Question; from ai_courses.models import Problem,ProblemAudience; print({'units':Unit.objects.count(),'questions':Question.objects.count(),'ai_problems':Problem.objects.count(),'ai_audiences':ProblemAudience.objects.count()})"
```

预期结果：

```text
{'units': 58, 'questions': 17, 'ai_problems': 9, 'ai_audiences': 18}
```

## 10. 创建第一个教师管理员

```bash
python manage.py createsuperuser
```

按提示输入用户名和密码。创建后还需确保该用户是教师角色：

```bash
python manage.py shell
```

进入 Django shell 后执行，把 `你的管理员用户名` 替换为实际用户名：

```python
from users.models import CustomUser
user = CustomUser.objects.get(username='你的管理员用户名')
user.role = 'teacher'
user.is_staff = True
user.is_superuser = True
user.save(update_fields=['role', 'is_staff', 'is_superuser'])
exit()
```

不要使用仓库历史启动脚本中出现过的演示密码作为正式密码。

## 11. 本地验收启动

本地开发不需要 Nginx。打开两个终端，并激活同一个 Python 虚拟环境。

终端一：

```bash
cd Python----/backend
python manage.py runserver 8080
```

终端二：

```bash
cd Python----/frontend
npm run dev
```

访问：

- 学生登录：<http://localhost:5173/login>
- 教师登录：<http://localhost:5173/teacher-login>
- 后端存活检查：<http://localhost:8080/api/health/live/>
- 数据库就绪检查：<http://localhost:8080/api/health/ready/>

本地跑通标志：学生和教师都能登录；学生能看到课程并完成一次信息课小测；教师端能查看题库和成绩。

## 12. Ubuntu 正式部署：Gunicorn

Django 官方不建议使用 `runserver` 提供生产服务。当前 `requirements.txt` 尚未包含生产 WSGI 服务器，因此 Ubuntu 上额外安装 Gunicorn：

```bash
source .venv/bin/activate
pip install gunicorn
cd backend
python manage.py collectstatic --noinput
gunicorn school_platform.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 3 \
  --timeout 60
```

先用上述命令确认 Gunicorn 能启动，再按下面示例创建 systemd 服务。将路径和 Linux 用户替换为真实值：

```ini
# /etc/systemd/system/python-learning.service
[Unit]
Description=Python Learning Django Service
After=network.target mysql.service

[Service]
User=你的Linux用户
Group=www-data
WorkingDirectory=/srv/Python----/backend
ExecStart=/srv/Python----/.venv/bin/gunicorn school_platform.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 60
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

加载并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now python-learning
sudo systemctl status python-learning --no-pager
```

## 13. Ubuntu 正式部署：Nginx

确认已经执行过 `npm run build` 和 `python manage.py collectstatic --noinput`。创建配置文件：

```nginx
# /etc/nginx/sites-available/python-learning
server {
    listen 80;
    server_name 你的域名或服务器IP;

    client_max_body_size 10m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /srv/Python----/backend/staticfiles/;
    }

    location /media/ {
        alias /srv/Python----/backend/media/;
    }

    location / {
        root /srv/Python----/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/python-learning /etc/nginx/sites-enabled/python-learning
sudo nginx -t
sudo systemctl reload nginx
```

如果默认站点与新站点冲突，可在确认新配置正确后移除 `/etc/nginx/sites-enabled/default`，再执行 `sudo nginx -t && sudo systemctl reload nginx`。

公网部署必须配置域名和 HTTPS。Ubuntu 可安装 Certbot：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d 你的域名
```

证书生效后，确认 `backend/.env` 中三个安全开关均为 `true`，然后重启后端：

```bash
sudo systemctl restart python-learning
```

## 14. 防火墙与端口

公网只开放：

- `80/tcp`：HTTP，用于跳转 HTTPS 和签发证书。
- `443/tcp`：HTTPS。
- `22/tcp`：SSH，最好限制为管理员固定 IP。

不要开放：

- MySQL `3306` 到公网。
- Gunicorn `8000` 到公网。
- Django 开发端口 `8080` 和 Vite 开发端口 `5173` 到公网。
- `/internal/runner/v1/` Runner 私有接口到公网。

## 15. 上线前验证

```bash
curl -i http://127.0.0.1:8000/api/health/live/
curl -i http://127.0.0.1:8000/api/health/ready/
curl -I http://你的域名或服务器IP/
sudo systemctl status python-learning --no-pager
sudo systemctl status nginx --no-pager
sudo nginx -t
```

浏览器验收：

1. 教师管理员能够登录。
2. 教师端能看到 58 个单元/小节、17 道信息课题和 9 道 AI 题。
3. 教师能创建测试学生和信息课小测。
4. 学生能登录、看到符合年级班级范围的课程并完成一次小测。
5. 教师端能看到该学生的最近一次成绩。
6. 代码运行按钮处于安全关闭状态，不能回退到 Django Web 进程执行代码。

## 16. 更新部署

更新前先备份 MySQL。然后在项目目录执行：

```bash
git pull --ff-only origin main
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
npm ci
npm run build

cd ../backend
python manage.py migrate
python manage.py collectstatic --noinput

sudo systemctl restart python-learning
sudo nginx -t
sudo systemctl reload nginx
```

不要在已有教学数据库上重复执行 `loaddata`，除非明确需要重置固定教学内容并已完成备份。

## 17. 常见问题

### 页面能打开，但 API 返回 502

检查 Gunicorn：

```bash
sudo systemctl status python-learning --no-pager
sudo journalctl -u python-learning -n 100 --no-pager
```

### `/api/health/ready/` 返回 503

检查 MySQL 是否运行、数据库账号密码是否正确，以及 `backend/.env` 中的主机和端口：

```bash
sudo systemctl status mysql --no-pager
mysql -u python_learning -p -h 127.0.0.1 python_learning
```

### 页面刷新后出现 Nginx 404

确认 Nginx 的前端配置包含：

```nginx
try_files $uri $uri/ /index.html;
```

### 浏览器出现 CSRF 或 Host 错误

检查：

- `DJANGO_ALLOWED_HOSTS` 是否包含当前域名或 IP，且不带协议。
- `DJANGO_CSRF_TRUSTED_ORIGINS` 是否包含完整的 `https://域名`。
- 修改 `.env` 后是否重启 Gunicorn。

### AI 助手不可用

确认 `MINIMAX_API_KEY` 已配置。AI 助手与代码 Runner 是不同功能；设置 AI Key 不会启用学生代码执行。

## 18. 相关文档与官方资料

- [教学内容恢复说明](docs/deployment/teaching-content-fixtures.md)
- [阿里云部署路线图](docs/2026-09-01-alicloud-deployment-roadmap.md)
- [MySQL 8.0 安装文档](https://dev.mysql.com/doc/refman/8.0/en/installing.html)
- [MySQL Windows Installer](https://dev.mysql.com/doc/refman/8.0/en/windows-installation.html)
- [Nginx Linux 软件包](https://nginx.org/en/linux_packages.html)
- [Nginx Windows 说明](https://nginx.org/en/docs/windows.html)
- [Django 使用 Gunicorn 部署](https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/gunicorn/)
- [Vite 入门与 Node.js 版本要求](https://vite.dev/guide/)
