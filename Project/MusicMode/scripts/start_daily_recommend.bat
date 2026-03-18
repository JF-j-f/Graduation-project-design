@echo off
chcp 65001 >nul
echo ===================================================
echo     MusicWeb Daily Recommendation Task
echo     Start Time: %date% %time%
echo ===================================================

cd /d "%~dp0..\Project"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo [*] Running sync_recs_v3.py...
C:\Users\君拂\AppData\Local\Programs\Python\Python312\python.exe sync_recs_v3.py

echo.
echo ===================================================
echo     Task Finished: %date% %time%
echo ===================================================
exit /b %ERRORLEVEL%
