@echo off
cd /d "%~dp0..\src\main\webapp\MusicServer\qq_api"
chcp 65001 >nul

echo ============================================
echo   QQ Music Python API 服务启动
echo ============================================
echo.

REM 检查 Python 是否可用
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到 Python，请确保已安装 Python 并添加到 PATH
    pause
    exit /b 1
)

echo [1/2] 检查并安装依赖...
pip install -r requirements.txt -q
if %ERRORLEVEL% neq 0 (
    echo [警告] 依赖安装可能存在问题，尝试继续启动...
)

echo.
echo [2/2] 启动 FastAPI 服务 (端口 8000)...
echo.
echo 服务地址: http://localhost:8000
echo API 文档: http://localhost:8000/docs
echo.
echo 按 Ctrl+C 停止服务
echo ============================================
echo.

python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload


