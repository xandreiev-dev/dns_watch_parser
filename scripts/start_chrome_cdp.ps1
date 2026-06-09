param(
    [int]$Port = 9222,
    [string]$ProfileDir = "C:\work\dns_watch_parser\tmp\chrome-profile",
    [string]$StartUrl = "https://www.dns-shop.ru/"
)

$ErrorActionPreference = "Stop"

$candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe"
)

$browser = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) {
    throw "Chrome or Edge executable was not found."
}

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null

$args = @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$ProfileDir",
    "--no-first-run",
    "--no-default-browser-check",
    $StartUrl
)

Start-Process -FilePath $browser -ArgumentList $args
Write-Host "Browser started on CDP port $Port with profile $ProfileDir"
Write-Host "Open DNS/login once, then run: python run_parser.py --browser-mode cdp --limit 50"
