@echo off
setlocal EnableExtensions

set "PROJECT_DIR=%~dp0.."
pushd "%PROJECT_DIR%" || exit /b 1

if not exist "logs" mkdir "logs"
set "LOG_FILE=%PROJECT_DIR%\logs\dns_watch_parser_daily.log"

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"

set "DNS_BROWSER_MODE=cdp"
set "DNS_CDP_URL=http://127.0.0.1:9223"
set "DNS_SHOP_ID=6"

echo.>> "%LOG_FILE%"
echo ============================================================>> "%LOG_FILE%"
echo [%DATE% %TIME%] DNS parser daily run started>> "%LOG_FILE%"

"%PYTHON_EXE%" scripts\start_chrome_cdp.py --port 9223 --wait-timeout 60 >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [%DATE% %TIME%] Failed to start/check Chrome CDP>> "%LOG_FILE%"
    popd
    exit /b 1
)

"%PYTHON_EXE%" run_parser.py --browser-mode cdp --cdp-url http://127.0.0.1:9223 --catalog-only --reset-state >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo [%DATE% %TIME%] DNS parser daily run finished with code %EXIT_CODE%>> "%LOG_FILE%"
popd
exit /b %EXIT_CODE%
