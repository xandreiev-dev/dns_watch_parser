@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment was not found in "%CD%\.venv"
  exit /b 1
)
call .venv\Scripts\activate

if not exist logs mkdir logs

echo.>> logs\scheduled_run.log
echo ============================================================>> logs\scheduled_run.log
echo [%DATE% %TIME%] DNS parser scheduled run started>> logs\scheduled_run.log

python scripts\run_daily_cdp.py --port 9223 --wait-timeout 120 --settle-seconds 45 --parser-timeout-minutes 180 --min-exported-rows 1000 >> logs\scheduled_run.log 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%DATE% %TIME%] DNS parser scheduled run finished with code %EXIT_CODE%>> logs\scheduled_run.log
exit /b %EXIT_CODE%
