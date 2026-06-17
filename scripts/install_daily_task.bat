@echo off
setlocal EnableExtensions

set "TASK_NAME=DNS Watch Parser Daily"
set "RUNNER=%~dp0run_dns_parser.bat"
set "TASK_ACTION=cmd.exe /c ""%RUNNER%"""

echo Creating Windows Task Scheduler task: %TASK_NAME%
echo Runner: %RUNNER%

schtasks /Create /TN "%TASK_NAME%" /SC DAILY /ST 17:00 /TR "%TASK_ACTION%" /F /RL HIGHEST /IT
if errorlevel 1 (
    echo Failed to create scheduled task.
    exit /b 1
)

echo Scheduled task created.
schtasks /Query /TN "%TASK_NAME%"
