@echo off
setlocal
cd /d "%~dp0"

if not exist logs mkdir logs
set "PYTHON=%CD%\.venv\Scripts\python.exe"

echo.>> logs\scheduled_run.log
echo ============================================================>> logs\scheduled_run.log
echo [%DATE% %TIME%] DNS parser scheduled run started>> logs\scheduled_run.log
echo Project: %CD%>> logs\scheduled_run.log

if not exist "%PYTHON%" (
  echo [%DATE% %TIME%] Virtual environment was not found: %PYTHON%>> logs\scheduled_run.log
  exit /b 1
)

"%PYTHON%" scripts\run_daily_cdp.py --port 9223 --wait-timeout 120 --settle-seconds 45 --parser-timeout-minutes 180 --min-exported-rows 1000 >> logs\scheduled_run.log 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%DATE% %TIME%] DNS parser scheduled run finished with code %EXIT_CODE%>> logs\scheduled_run.log
exit /b %EXIT_CODE%
