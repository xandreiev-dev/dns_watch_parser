@echo off
setlocal

cd /d "%~dp0"
if not exist logs mkdir logs

if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

for /f %%I in ('powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Date -Format yyyyMMdd"') do set "RUN_STAMP=%%I"

python download_latest_from_ftp.py >> "logs\ftp_pull_%RUN_STAMP%.log" 2>&1
exit /b %ERRORLEVEL%
