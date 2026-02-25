@echo off
chcp 65001 >nul
echo ===================================================
echo     MusicWeb Daily Recommendation Task
echo     Start Time: %date% %time%
echo ===================================================

cd /d E:\Graduation-project-design\Project\MusicMode\Project
set PYTHONIOENCODING=utf-8

echo 🚀 Running sync_recs_v2.py...
python sync_recs_v2.py

echo.
echo ===================================================
echo     Task Finished: %date% %time%
echo ===================================================
exit /b 0
