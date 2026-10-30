@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo  Platon's Eye - first time setup
echo ========================================================

set "PY="
where py > nul 2>&1 && set "PY=py -3"
if not defined PY (
  where python > nul 2>&1 && set "PY=python"
)
if defined PY (
  %PY% --version > nul 2>&1 || set "PY="
)
if not defined PY (
  echo.
  echo [ERROR] Python was not found.
  echo Install Python 3.10 or later from https://www.python.org/downloads/
  echo and check "Add python.exe to PATH" on the first screen.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv .venv
  if errorlevel 1 goto fail
)

echo Installing OpenCV and NumPy...
".venv\Scripts\python.exe" -m pip install --upgrade pip > nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail

if not exist ".env" (
  copy ".env.example" ".env" > nul
  echo Created .env - paste your Gemini API key into it.
)

echo.
echo Setup finished. Run start.bat to start.
echo.
pause
exit /b 0

:fail
echo.
echo [ERROR] Setup failed. Check the internet connection and run setup.bat again.
pause
exit /b 1
