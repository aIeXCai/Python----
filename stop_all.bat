@echo off
chcp 936 >nul
echo.
echo ========================================
echo   停止全部服务
echo ========================================
echo.
echo [停止] 正在关闭 Django / Vite 进程（含 reloader 父进程）...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'manage\.py runserver 8080' -or $_.CommandLine -match 'vite[\\/]bin[\\/]vite\.js' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo.
echo   端口释放检查：
netstat -ano | findstr ":8080" | findstr "LISTENING" >nul
if errorlevel 1 (echo   [已释放] 8080) else (echo   [仍占用] 8080)
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul
if errorlevel 1 (echo   [已释放] 5173) else (echo   [仍占用] 5173)
echo ========================================
pause
