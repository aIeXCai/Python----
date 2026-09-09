@echo off
chcp 936 >nul
REM ============================================================
REM Python 学习平台 - 一键启动所有服务（Windows）
REM 端口：8080=Django，5173=Vite，5000=server.py(可选)
REM ============================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "LOG_DIR=%SCRIPT_DIR%logs"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo ========================================
echo   Python 学习平台 - 启动脚本
echo ========================================
echo.

REM --- 清理旧进程 ---
REM runserver 是 reloader父进程 + server子进程的结构，子进程被杀后父进程
REM 会自动把它重新拉起；因此必须按命令行匹配把整棵进程树一起停掉。
echo [停止] 正在停止已有服务...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'manage\.py runserver 8080' -or $_.CommandLine -match 'vite[\\/]bin[\\/]vite\.js' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
timeout /t 1 >nul

REM --- 选择 Python：优先项目 .venv，其次 conda pylearn，最后系统 python ---
set "PYTHON="
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" set "PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"
if not defined PYTHON if exist "E:\Anaconda\envs\pylearn\python.exe" set "PYTHON=E:\Anaconda\envs\pylearn\python.exe"
if not defined PYTHON set "PYTHON=python"

REM --- 检查 Python / Django ---
"%PYTHON%" -c "import django" 2>nul
if errorlevel 1 (
    echo [错误] 当前选中的 Python 里没有 Django：
    echo        %PYTHON%
    echo 请先运行：pip install django djangorestframework django-cors-headers python-dotenv cryptography openai requests
    pause
    exit /b 1
)
echo [ OK ] Python 环境检查通过：%PYTHON%

REM --- 检查本地学生密码密钥文件（README 第 4 节生成）---
if not exist "%SCRIPT_DIR%backend\.env.security.local" (
    echo [警告] 未找到 backend\.env.security.local
    echo        教师端“创建学生 / 查看密码”功能将不可用，请按 README 第 4 节生成。
)

REM --- 检查 npm ---
where npm >nul 2>&1
if errorlevel 1 (
    echo [错误] npm 未安装，请先安装 Node.js
    pause
    exit /b 1
)
echo [ OK ] npm 检查通过

REM --- 1. 启动 Django（SQLite 开发环境）---
echo.
echo [启动] Django 后端（端口 8080）...
cd /d "%SCRIPT_DIR%backend"
set "DJANGO_ENV=development"
set "DJANGO_DB_ENGINE=sqlite"
start /min "Django" cmd /c ""%PYTHON%" manage.py runserver 8080 >> ..\logs\django.log 2>&1"
cd /d "%SCRIPT_DIR%"

REM --- 2. 启动 Vite ---
echo [启动] Vite 前端（端口 5173）...
cd /d "%SCRIPT_DIR%frontend"
start /min "Vite" cmd /c "npm run dev >> ..\logs\vite.log 2>&1"
cd /d "%SCRIPT_DIR%"

REM --- 3. 启动 server.py（可选，根目录没有则自动跳过）---
if exist "%SCRIPT_DIR%server.py" (
    echo [启动] server.py（端口 5000，可选）...
    cd /d "%SCRIPT_DIR%"
    start /min "server" cmd /c ""%PYTHON%" server.py >> logs\server.log 2>&1"
    cd /d "%SCRIPT_DIR%"
)

REM --- 等几秒后检查端口是否真的起来 ---
echo.
echo [检查] 等待服务启动...
timeout /t 5 >nul
netstat -ano | findstr ":8080" | findstr "LISTENING" >nul
if errorlevel 1 echo [警告] Django 未能在 8080 端口监听，请查看 logs\django.log
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul
if errorlevel 1 echo [警告] Vite 未能在 5173 端口监听，请查看 logs\vite.log

echo.
echo ========================================
echo   全部服务已启动！
echo ========================================
echo.
echo   前端页面：  http://localhost:5173
echo   学生登录：  http://localhost:5173/login
echo   老师登录：  http://localhost:5173/teacher-login
echo   Django API：http://localhost:8080
echo.
echo   停止服务请运行 stop_all.bat
echo ========================================
pause
