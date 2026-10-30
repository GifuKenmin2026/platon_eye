@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Not set up yet. Run setup.bat first.
  pause
  exit /b 1
)

set "URL=http://localhost:8000"

rem Start the server in its own window (keep that window open)
start "PlatonEye server" cmd /k ""%~dp0.venv\Scripts\python.exe" "%~dp0server\app.py""

rem Wait until the server answers (up to 30 seconds)
echo Waiting for the server...
set /a TRIES=0
:wait
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 '%URL%/api/status'; exit 0 } catch { exit 1 }" > nul 2>&1
if not errorlevel 1 goto open
set /a TRIES+=1
if %TRIES% geq 30 goto open
timeout /t 1 /nobreak > nul
goto wait
:open

rem Open Chrome in kiosk (full screen). Fall back to Edge, then the default browser.
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if exist "%CHROME%" (
  start "" "%CHROME%" --kiosk "%URL%"
  exit /b 0
)

set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if exist "%EDGE%" (
  start "" "%EDGE%" --kiosk "%URL%" --edge-kiosk-type=fullscreen
  exit /b 0
)

start "" "%URL%"
