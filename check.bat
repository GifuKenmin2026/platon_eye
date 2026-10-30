@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Not set up yet. Run setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "%~dp0server\check_net.py"
echo.
pause
