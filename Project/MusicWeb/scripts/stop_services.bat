@echo off
chcp 65001 >nul
echo ============================================
echo   MusicWeb 服务停止脚本 (Enhanced v3.0)
echo ============================================
echo.

echo [1/5] 正在检查并停止 Redis 服务...
tasklist /FI "IMAGENAME eq redis-server.exe" 2>NUL | find /I /N "redis-server.exe">NUL
if "%ERRORLEVEL%"=="0" (
    taskkill /F /IM redis-server.exe >nul 2>&1
    echo   [成功] Redis 服务已停止
) else (
    echo   [提示] Redis 服务未运行
)

echo.
echo [2/5] 正在检查并停止 Python QQ 音乐服务...
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    taskkill /F /IM python.exe >nul 2>&1
    echo   [成功] Python 服务已停止
) else (
    echo   [提示] Python 服务未运行
)

echo.
echo [3/5] 正在检查并停止 Unblock 解灰服务...
echo   [提示] Unblock 与 Node.js API 共用进程，将在下一步一并停止

echo.
echo [4/5] 正在检查并停止 Node.js 音乐服务...
tasklist /FI "IMAGENAME eq node.exe" 2>NUL | find /I /N "node.exe">NUL
if "%ERRORLEVEL%"=="0" (
    taskkill /F /IM node.exe >nul 2>&1
    echo   [成功] Node.js 服务已停止 (含 Unblock)
) else (
    echo   [提示] Node.js 服务未运行
)

echo.
echo [5/5] 正在检查并停止 Java/Tomcat 服务...
tasklist /FI "IMAGENAME eq java.exe" 2>NUL | find /I /N "java.exe">NUL
if "%ERRORLEVEL%"=="0" (
    taskkill /F /IM java.exe >nul 2>&1
    echo   [成功] Java 服务已停止
) else (
    echo   [提示] Java 服务未运行
)

echo.
echo ============================================
echo   所有服务清理完毕！
echo ============================================
pause
