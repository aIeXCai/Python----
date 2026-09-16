@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "LOG_DIR=%SCRIPT_DIR%logs"
set "PID_FILE=%SCRIPT_DIR%.server_pids"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo ========================================
echo   Python 学习平台 - 一键启动
echo ========================================
echo.

set "PYTHON="
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" set "PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"
if not defined PYTHON if exist "E:\Anaconda\envs\pylearn\python.exe" set "PYTHON=E:\Anaconda\envs\pylearn\python.exe"
if not defined PYTHON set "PYTHON=python"

"%PYTHON%" -c "import django, psutil, requests" 2>nul
if errorlevel 1 (
    echo [错误] Python 依赖不完整：%PYTHON%
    echo        请在虚拟环境中安装 requirements.txt。
    goto :fail
)
where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo [错误] npm 未安装，请先安装 Node.js。
    goto :fail
)
where node.exe >nul 2>&1
if errorlevel 1 (
    echo [错误] node.exe 不可用。
    goto :fail
)
if not exist "%SCRIPT_DIR%frontend\node_modules" (
    echo [错误] 前端依赖不存在，请先在 frontend 目录执行 npm ci。
    goto :fail
)
echo [ OK ] 环境检查通过：%PYTHON%

call "%SCRIPT_DIR%stop_all.bat" --quiet
for %%P in (8080 5173) do (
    netstat -ano | findstr ":%%P" | findstr "LISTENING" >nul
    if not errorlevel 1 (
        echo [错误] 端口 %%P 已被非本项目进程占用。
        goto :fail
    )
)

"%PYTHON%" "%SCRIPT_DIR%scripts\init_local_runner.py"
if errorlevel 1 goto :fail
if not exist "%SCRIPT_DIR%backend\.env.security.local" (
    echo [警告] 未找到 backend\.env.security.local，教师创建学生/查看密码功能将不可用。
)

set "DJANGO_ENV=development"
if not defined DJANGO_DB_ENGINE set "DJANGO_DB_ENGINE=sqlite"
set "PLATFORM_PYTHON=%PYTHON%"
set "PLATFORM_NODE=node.exe"
set "PLATFORM_ROOT=%SCRIPT_DIR%"
set "PLATFORM_BACKEND=%SCRIPT_DIR%backend"
set "PLATFORM_FRONTEND=%SCRIPT_DIR%frontend"
set "PLATFORM_LOGS=%LOG_DIR%"
break > "%PID_FILE%"

echo [启动] Django 后端 (127.0.0.1:8080)...
del /q "%LOG_DIR%\django.pid" >nul 2>&1
powershell -NoProfile -Command "$manage=([char]34)+$env:PLATFORM_BACKEND+'\manage.py'+([char]34); $p=Start-Process -FilePath $env:PLATFORM_PYTHON -ArgumentList @($manage,'runserver','127.0.0.1:8080','--noreload') -WorkingDirectory $env:PLATFORM_BACKEND -RedirectStandardOutput ($env:PLATFORM_LOGS+'\django.log') -RedirectStandardError ($env:PLATFORM_LOGS+'\django.error.log') -WindowStyle Hidden -PassThru; [IO.File]::WriteAllText($env:PLATFORM_LOGS+'\django.pid',[string]$p.Id)" >nul
if not exist "%LOG_DIR%\django.pid" goto :start_failed
set /p DJANGO_PID=<"%LOG_DIR%\django.pid"
if not defined DJANGO_PID goto :start_failed
echo django=%DJANGO_PID%>> "%PID_FILE%"
call :wait_port 8080 Django
if errorlevel 1 goto :start_failed

echo [启动] Local Runner...
del /q "%LOG_DIR%\runner.pid" >nul 2>&1
powershell -NoProfile -Command "$script=([char]34)+$env:PLATFORM_ROOT+'scripts\run_local_runner.py'+([char]34); $p=Start-Process -FilePath $env:PLATFORM_PYTHON -ArgumentList @($script) -WorkingDirectory $env:PLATFORM_ROOT -RedirectStandardOutput ($env:PLATFORM_LOGS+'\runner.log') -RedirectStandardError ($env:PLATFORM_LOGS+'\runner.error.log') -WindowStyle Hidden -PassThru; [IO.File]::WriteAllText($env:PLATFORM_LOGS+'\runner.pid',[string]$p.Id)" >nul
if not exist "%LOG_DIR%\runner.pid" goto :start_failed
set /p RUNNER_PID=<"%LOG_DIR%\runner.pid"
if not defined RUNNER_PID goto :start_failed
echo runner=%RUNNER_PID%>> "%PID_FILE%"
pushd "%SCRIPT_DIR%backend"
"%PYTHON%" manage.py runner_status --wait 20
set "STATUS_RESULT=%ERRORLEVEL%"
popd
if not "%STATUS_RESULT%"=="0" goto :start_failed

echo [启动] Vite 前端 (0.0.0.0:5173)...
del /q "%LOG_DIR%\vite.pid" >nul 2>&1
powershell -NoProfile -Command "$script=([char]34)+$env:PLATFORM_FRONTEND+'\node_modules\vite\bin\vite.js'+([char]34); $p=Start-Process -FilePath $env:PLATFORM_NODE -ArgumentList @($script) -WorkingDirectory $env:PLATFORM_FRONTEND -RedirectStandardOutput ($env:PLATFORM_LOGS+'\vite.log') -RedirectStandardError ($env:PLATFORM_LOGS+'\vite.error.log') -WindowStyle Hidden -PassThru; [IO.File]::WriteAllText($env:PLATFORM_LOGS+'\vite.pid',[string]$p.Id)" >nul
if not exist "%LOG_DIR%\vite.pid" goto :start_failed
set /p VITE_PID=<"%LOG_DIR%\vite.pid"
if not defined VITE_PID goto :start_failed
echo vite=%VITE_PID%>> "%PID_FILE%"
call :wait_port 5173 Vite
if errorlevel 1 goto :start_failed

echo.
echo ========================================
echo [ OK ] Django、Local Runner 和 Vite 已全部就绪
echo ========================================
echo   学生登录：http://localhost:5173/login
echo   教师登录：http://localhost:5173/teacher-login
echo   Runner 状态：cd backend ^&^& "%PYTHON%" manage.py runner_status
echo   停止：stop_all.bat
echo.
echo   提示：三个服务已在后台独立运行，关闭本窗口不会停止服务。
call :wait_key
exit /b 0

:wait_key
rem 仅当"双击运行"时停住窗口，供人查看结果；被其他脚本调用时不阻塞。
echo %cmdcmdline% | find /i "%~nx0" >nul
if errorlevel 1 exit /b 0
echo.
echo   按任意键关闭此窗口...
pause
exit /b 0

:wait_port
for /l %%N in (1,1,20) do (
    netstat -ano | findstr ":%~1" | findstr "LISTENING" >nul
    if not errorlevel 1 (
        echo [ OK ] %~2 已就绪
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)
echo [错误] %~2 启动超时，请查看 logs 目录。
exit /b 1

:start_failed
echo [错误] 启动未完成，正在回收已启动的本项目进程。
call "%SCRIPT_DIR%stop_all.bat" --quiet
goto :fail

:fail
echo.
call :wait_key
exit /b 1
