@echo off
cd /d "%~dp0..\src\main\webapp\MusicServer\unblock"
chcp 65001 >nul

echo.
echo [Unblock] 启动解灰服务 v0.28.0 (端口 8081)
echo [Unblock] 使用代理: http://127.0.0.1:7898
echo.

node src/app.js -p 8081 -u http://127.0.0.1:7898
