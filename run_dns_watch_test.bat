@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment was not found in "%CD%\.venv"
  pause
  exit /b 1
)
call .venv\Scripts\activate

if not exist logs mkdir logs

python scripts\run_daily_cdp.py --port 9223 --wait-timeout 120 --settle-seconds 45 --parser-timeout-minutes 180 --min-exported-rows 1000 --no-telegram --keep-browser-on-fail
pause
