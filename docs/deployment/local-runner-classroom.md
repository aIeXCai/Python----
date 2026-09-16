# Local Runner 本机与 Windows 机房运行手册

更新日期：2026-09-15
适用路径：不接入 Docker，Django 和 Local Runner 在同一台受控电脑上运行。

## 1. 安全边界

Local Runner 会在操作系统本机子进程中运行学生 Python 代码，但它不是 Docker/VM 级别的强隔离。只适用于受管理的校园网和课堂环境。

- 用专用、非管理员的系统账号启动平台。
- 该账号不应能读取教师个人文件、浏览器密码或生产密钥。
- 不要把这种运行方式直接暴露在公网。公网部署前必须切换到 Docker 或更强的隔离环境。
- `.env.runner.local` 含 HMAC 密钥，不得提交 Git、传给学生或写入日志。

## 2. 首次安装

Python 3.10+、Node.js 20.19+ 安装完成后，在项目根目录执行：

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cd frontend && npm ci && cd ..
bash scripts/stage3_security_local.sh init
python scripts/init_local_runner.py
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
cd frontend
npm ci
cd ..
python scripts\init_local_runner.py
```

Windows 上的学生密码加密密钥按项目 `README.md` 第 4 节初始化。若 SQLite 本地演示因 `mysqlclient` 缺少编译环境而安装失败，可安装 README 中列出的非 MySQL 依赖，但必须包含 `psutil>=6.1,<8`。

## 3. 配置

`python scripts/init_local_runner.py` 只在首次创建 `.env.runner.local`，已有文件不会被覆盖，也不会显示密钥。检查配置：

```bash
python scripts/init_local_runner.py --check
```

课堂使用前重点确认：

```text
CODE_EXECUTION_ENABLED=true
EXECUTION_REQUIRE_HEALTHY_RUNNER=true
RUNNER_WEB_INTERNAL_URL=http://127.0.0.1:8080
RUNNER_CONCURRENCY=2
```

Mac 功能验收先使用 2 个并发槽。Windows 机房可在 Step 8 实测后调整为 4/6/8，不要为了减少排队盲目调大。

## 4. 一键启停

macOS/Linux：

```bash
bash start_all.sh
bash stop_all.sh
```

Windows 双击 `start_all.bat` / `stop_all.bat`，或在 `cmd.exe` 中执行。脚本按以下顺序选择 Python：

1. 项目 `.venv\Scripts\python.exe`；
2. `E:\Anaconda\envs\pylearn\python.exe`；
3. `PATH` 中的 `python`。

启动顺序为 Django → Runner 心跳验收 → Vite。任一环节失败会回收已启动的本项目进程。停止脚本同时校验 `.server_pids` 里的 PID 和命令行中的本项目绝对路径，不按端口强杀其他 Python/Node 程序。

## 5. 健康检查

```bash
cd backend
python manage.py runner_status
```

正常时会显示节点、`slots=已用/容量`、心跳年龄和“Local Runner 已就绪”。无健康节点时命令返回非零退出码。

日志位于 `logs/`：

- `django.log`：Web/API；
- `runner.log`：领取、执行和回写；
- `vite.log`：前端开发服务；
- Windows 另有同名 `.error.log`。

## 6. Windows 机房迁移

1. 将 MacBook 验收后的聚焦提交合并/挑选到 `jifang3`，不覆盖机房分支已有修改。
2. 在机房电脑拉取 `jifang3`，重建或更新 `.venv`。
3. 每台实际运行 Runner 的电脑都必须自行生成 `.env.runner.local`，不要从 Git 或群聊复制密钥文件。
4. 若 Django 和 Runner 在同一台主机，保持 `RUNNER_WEB_INTERNAL_URL=http://127.0.0.1:8080`。
5. 先用 SQLite 完成单机功能验收；40 人正式并发课堂按方案切换 MySQL。
6. 用非管理员账号启动，依次验证正常输出、语法错误、死循环、持续输出和子进程回收。

## 7. 常见故障

### 点击提交后提示执行服务未就绪

执行 `python manage.py runner_status`，然后查看 `logs/runner.log` 和 `logs/runner.error.log`。常见原因是 Django 未启动、密钥不一致、Runner 进程已退出或心跳超过 30 秒。

### 页面显示排队中

Runner 满载时排队是正常状态。先看 `runner_status` 的心跳和槽位；如果心跳健康，等待前面任务完成。如果 Runner 意外中断，重启后租约恢复机制会重排任务；达到重试上限则进入系统错误，不会伪造 0 分。

### 端口 8080/5173 被占用

脚本不会杀掉未记录的其他进程。请先确认占用者，再手动停止对应程序。

## 8. 回退

1. 设置 `CODE_EXECUTION_ENABLED=false`，阻止新代码任务。
2. 执行停止脚本。
3. 必要时在 `backend/` 执行 `python manage.py recover_execution_tasks`。
4. 登录、课程、选择题和历史成绩不依赖 Runner，仍可继续使用。
