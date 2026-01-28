@echo off
chcp 65001 >nul
echo ========================================
echo   MusicWeb API Server 启动脚本
echo ========================================
echo.

cd /d "%~dp0..\src\main\webapp\MusicServer"

echo 正在检查 Node.js 环境...
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装 Node.js
    pause
    exit /b 1
)

echo 正在检查依赖...
if not exist "node_modules" (
    echo [提示] 首次运行，正在安装依赖...
    npm install
)

echo.
echo 正在启动 API 服务...
echo.
node ..\js\server.js
