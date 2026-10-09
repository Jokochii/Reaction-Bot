@echo off
cd /d "%~dp0.."
start "" /b ".venv\Scripts\python.exe" -u Python\bot.py >> "Local-Cache\bot.log" 2>&1
exit