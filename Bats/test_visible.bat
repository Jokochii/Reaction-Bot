@echo off
cd /d "%~dp0"
start "" /B python -u bot.py > "%~dp0bot.log" 2>&1
exit