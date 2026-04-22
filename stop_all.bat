@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   停止全部服务
echo ========================================
echo.
for %%P in (8080 5173 5000) do (
    for /f "tokens=5" %%I in ('netstat -ano 2^>nul ^| findstr :%%P') do (
        echo [停止] 关闭端口 %%P (PID %%I)
        taskkill /PID %%I /F >nul 2>&1
    )
)
echo.
echo   所有服务已停止
echo ========================================
pause
