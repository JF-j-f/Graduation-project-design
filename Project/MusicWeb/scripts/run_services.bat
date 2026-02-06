@echo off
cd /d "%~dp0.."
chcp 65001 >nul

rem ==========================================
rem  强制设置 JAVA_HOME（解决环境变量不生效问题）
rem ==========================================
set "JAVA_HOME=C:\Program Files\Java\jdk-25.0.2"

echo ============================================
echo   MusicWeb 一键启动脚本 (Enhanced v3.0)
echo ============================================
echo.

echo [1/5] 正在启动 Redis 服务...
start /b cmd /c "scripts\start_redis.bat"

echo.
echo 正在等待 Redis 初始化...
timeout /t 2 /nobreak >nul

echo.
echo [2/5] 正在启动 Python QQ Music API 服务...
start /b "Python API" cmd /c "scripts\start_qq_api.bat"

echo.
echo 正在等待 Python API 初始化...
timeout /t 3 /nobreak >nul

echo.
echo [3/5] 正在启动 Unblock 解灰服务 (端口 8081)...
start /b "Unblock" cmd /c "scripts\start_unblock.bat"

echo.
echo 正在等待 Unblock 服务初始化...
timeout /t 2 /nobreak >nul

echo.
echo [4/5] 正在启动 Node.js 音乐 API 服务...
start /b cmd /c "scripts\start.bat"

echo.
echo 正在等待 Node.js 初始化输出...
timeout /t 3 /nobreak >nul

echo.
echo =================================================================
echo [5/5] 正在启动 Java Web 应用...
echo.
echo [提示] 当您看到 "[INFO] Tomcat ... started on port [8082]" 时：
echo        说明 Java 服务启动成功！
echo.
echo [提示] 服务地址:
echo        - Web 应用: http://localhost:8082/musicweb/
echo        - QQ Music API: http://localhost:8000/docs
echo        - Node.js API: http://localhost:3000/health
echo        - Unblock 解灰: http://localhost:8081/
echo =================================================================
echo.
call scripts\mvnw.cmd package cargo:run

pause
