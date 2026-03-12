@echo off
cd /d "%~dp0.."
chcp 65001 >nul

rem ==========================================
rem  MusicWeb 一键启动脚本 v4.0
rem  严格顺序启动，端口就绪后才启动下一项
rem  任何服务启动失败则终止后续启动
rem ==========================================
set "JAVA_HOME=C:\Program Files\Java\jdk-25.0.2"

echo ============================================
echo   MusicWeb 一键启动脚本 (Enhanced v4.0)
echo ============================================
echo.

rem ========== [1/5] Redis ==========
echo [1/5] 正在启动 Redis 服务...
start /b cmd /c "scripts\start_redis.bat"
call :wait_for_port 6379 15
if %ERRORLEVEL% neq 0 (
    echo   [FAIL] Redis 启动超时，终止后续服务！
    goto :startup_fail
)
echo   [OK] Redis 已就绪 (端口 6379)
echo.

rem ========== [2/5] Python QQ Music API ==========
echo [2/5] 正在启动 Python QQ Music API 服务...
start /b "Python API" cmd /c "scripts\start_qq_api.bat"
call :wait_for_port 8000 30
if %ERRORLEVEL% neq 0 (
    echo   [FAIL] QQ Music API 启动超时，终止后续服务！
    goto :startup_fail
)
echo   [OK] QQ Music API 已就绪 (端口 8000)
echo.

rem ========== [3/5] Unblock ==========
echo [3/5] 正在启动 Unblock 解灰服务...
start /b "Unblock" cmd /c "scripts\start_unblock.bat"
call :wait_for_port 8081 15
if %ERRORLEVEL% neq 0 (
    echo   [FAIL] Unblock 服务启动超时，终止后续服务！
    goto :startup_fail
)
echo   [OK] Unblock 解灰服务已就绪 (端口 8081)
echo.

rem ========== [4/5] Node.js API ==========
echo [4/5] 正在启动 Node.js 音乐 API 服务...
start /b cmd /c "scripts\start.bat"
call :wait_for_port 3000 20
if %ERRORLEVEL% neq 0 (
    echo   [FAIL] Node.js API 启动超时，终止后续服务！
    goto :startup_fail
)
echo   [OK] Node.js API 已就绪 (端口 3000)
echo.

rem ========== [5/5] Java/Tomcat ==========
echo =================================================================
echo [5/5] 正在启动 Java Web 应用 (Maven 编译 + Tomcat)...
echo.
echo   服务地址:
echo     - Web 应用:     http://localhost:8082/musicweb/
echo     - QQ Music API: http://localhost:8000/docs
echo     - Node.js API:  http://localhost:3000/health
echo     - Unblock 解灰: http://localhost:8081/
echo =================================================================
echo.
call scripts\mvnw.cmd package cargo:run
if %ERRORLEVEL% neq 0 (
    echo.
    echo   [FAIL] Java Web 应用启动失败！
    goto :startup_fail
)

pause
goto :eof

rem ==========================================
rem  启动失败处理
rem ==========================================
:startup_fail
echo.
echo ============================================
echo   启动失败！请检查上方错误后重试。
echo   可运行 stop_services.bat 清理残留进程。
echo ============================================
pause
goto :eof

rem ==========================================
rem  端口等待函数
rem  用法: call :wait_for_port <端口> <超时秒数>
rem  成功返回 ERRORLEVEL=0，超时返回 ERRORLEVEL=1
rem ==========================================
:wait_for_port
set "_port=%~1"
set /a "_max=%~2"
set /a "_count=0"
:_wp_loop
if %_count% geq %_max% (
    exit /b 1
)
netstat -an 2>nul | findstr /R /C:":%_port% .*LISTENING" >nul 2>&1
if %ERRORLEVEL%==0 (
    exit /b 0
)
set /a "_count+=1"
timeout /t 1 /nobreak >nul
goto :_wp_loop
