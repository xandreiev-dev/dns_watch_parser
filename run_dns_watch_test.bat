@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo Virtual environment was not found: %PYTHON%
  pause
  exit /b 1
)

if not exist logs mkdir logs

"%PYTHON%" scripts\run_daily_cdp.py --port 9223 --wait-timeout 120 --settle-seconds 45 --parser-timeout-minutes 180 --min-exported-rows 1000 --no-telegram --keep-browser-on-fail
pause
