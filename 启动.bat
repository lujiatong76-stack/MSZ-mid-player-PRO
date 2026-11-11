@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Please install Python 3.8 or newer, then run again.
  pause
  exit /b 1
)
python "%~dp0run.py"
if errorlevel 1 pause
