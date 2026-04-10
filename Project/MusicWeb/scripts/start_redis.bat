@echo off
echo [Redis] 正在启动 Redis 服务...
:: 使用绝对路径启动 Redis，避免环境变量未生效的问题
"C:\Program Files\Redis\redis-server.exe" --dir "F:\Graduation-project-design\Project\MusicWeb\src\main\webapp\log"
