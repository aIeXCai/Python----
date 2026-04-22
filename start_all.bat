@echo off
chcp 65001 >nul
REM ============================================================
REM Python 学习平台 — 一键启动所有服务（Windows）
REM ============================================================
REM 端口：8080=Django，5173=Vite，5000=server.py
REM ============================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PYTHON=python"
set "LOG_DIR=%SCRIPT_DIR%logs"
set "DJANGO_PID="
set "VITE_PID="
set "SERVER_PID="

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo ========================================
echo   Python 学习平台 — 启动脚本
echo ========================================
echo.

REM 清理旧进程
echo [停止] 正在停止已有服务...
for %%P in (8080 5173 5000) do (
    for /f "tokens=5" %%I in ('netstat -ano 2^>nul ^| findstr :%%P') do (
        taskkill /PID %%I /F >nul 2>&1
    )
)
timeout /t 2 >nul

REM 检查 Python
%PYTHON% -c "import django" 2>nul
if errorlevel 1 (
    echo [错误] Django 未安装，请先运行：pip install django djangorestframework django-cors-headers
    pause
    exit /b 1
)
echo [ OK ] Python 环境检查通过

REM 检查 npm
where npm >nul 2>&1
if errorlevel 1 (
    echo [错误] npm 未安装，请先安装 Node.js
    pause
    exit /b 1
)
echo [ OK ] npm 检查通过

REM 1. 启动 Django
echo.
echo [启动] Django 后端 (端口 8080)...
cd /d "%SCRIPT_DIR%backend"
start /min "Django" cmd /c "%PYTHON% manage.py runserver 8080 >> ..\logs\django.log 2>&1"

REM 2. 启动 Vite
echo [启动] Vite 前端 (端口 5173)...
cd /d "%SCRIPT_DIR%frontend"
start /min "Vite" cmd /c "npm run dev >> ..\logs\vite.log 2>&1"

REM 3. 启动 server.py
if exist "%SCRIPT_DIR%server.py" (
    echo [启动] server.py (端口 5000，可选)...
    cd /d "%SCRIPT_DIR%"
    start /min "server" cmd /c "%PYTHON% server.py >> logs\server.log 2>&1"
)

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
echo   老师账号：  alex / teacher123
echo   学生账号：  張小華 / pass123（八年級/7班）
echo.
echo   停止服务请运行 stop_all.bat
echo ========================================
pause
