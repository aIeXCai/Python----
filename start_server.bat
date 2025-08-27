@echo off
REM 一键启动Python学习网站服务器
cd /d %~dp0

REM 检查Python环境
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo 未检测到python，请先安装Python。
    exit /b 1
)

REM 启动服务器
python server.py
