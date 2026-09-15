@echo off
chcp 65001 >nul
setlocal EnableExtensions DisableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "PID_FILE=%SCRIPT_DIR%.server_pids"
set "PLATFORM_ROOT=%SCRIPT_DIR%"
set "QUIET=0"
if /i "%~1"=="--quiet" set "QUIET=1"

if "%QUIET%"=="0" (
    echo.
    echo ========================================
    echo   停止 Python 学习平台
    echo ========================================
)

if exist "%PID_FILE%" (
    for %%S in (runner django vite) do (
        for /f "usebackq tokens=1,2 delims==" %%A in ("%PID_FILE%") do (
            if /i "%%A"=="%%S" call :stop_tree "%%A" "%%B"
        )
    )
    del /q "%PID_FILE%" >nul 2>&1
)

for %%P in (8080 5173) do (
    netstat -ano | findstr ":%%P" | findstr "LISTENING" >nul
    if not errorlevel 1 if "%QUIET%"=="0" echo [警告] 端口 %%P 仍被其他进程占用（未自动终止）。
)
if "%QUIET%"=="0" echo [ OK ] 本项目记录的服务已停止。
exit /b 0

:stop_tree
set "SERVICE_NAME=%~1"
set "SERVICE_PID=%~2"
echo(%SERVICE_PID%| findstr /r "^[0-9][0-9]*$" >nul || exit /b 0
tasklist /fi "PID eq %SERVICE_PID%" 2>nul | findstr /r /c:"[ ]%SERVICE_PID%[ ]" >nul
if errorlevel 1 exit /b 0
set "SERVICE_MARKER=__invalid_service__"
if /i "%SERVICE_NAME%"=="django" set "SERVICE_MARKER=%SCRIPT_DIR%backend\manage.py"
if /i "%SERVICE_NAME%"=="runner" set "SERVICE_MARKER=%SCRIPT_DIR%scripts\run_local_runner.py"
if /i "%SERVICE_NAME%"=="vite" set "SERVICE_MARKER=%SCRIPT_DIR%frontend"
set "PLATFORM_SERVICE_PID=%SERVICE_PID%"
set "PLATFORM_SERVICE_MARKER=%SERVICE_MARKER%"
powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$env:PLATFORM_SERVICE_PID); if ($p -and $p.CommandLine -and $p.CommandLine.Contains($env:PLATFORM_SERVICE_MARKER)) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    if "%QUIET%"=="0" echo [警告] PID %SERVICE_PID% 不再属于本项目 %SERVICE_NAME%，已跳过。
    exit /b 0
)
taskkill /pid %SERVICE_PID% /t >nul 2>&1
for /l %%N in (1,1,10) do (
    tasklist /fi "PID eq %SERVICE_PID%" 2>nul | findstr /r /c:"[ ]%SERVICE_PID%[ ]" >nul
    if errorlevel 1 goto :stopped
    timeout /t 1 /nobreak >nul
)
taskkill /pid %SERVICE_PID% /t /f >nul 2>&1
:stopped
if "%QUIET%"=="0" echo [ OK ] 已停止 %SERVICE_NAME% (PID %SERVICE_PID%)
exit /b 0
