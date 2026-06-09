# DNS Watch Parser

Project parser for smart watches from DNS (`dns-shop.ru`).

The parser reads `config.toml`, collects product URLs from catalog pages, extracts product data, writes checkpoints after each processed URL, and exports rows to XLSX.

## Run

```powershell
python run_parser.py
python run_parser.py --config config.toml
python run_parser.py --resume
python run_parser.py --reset-state
python run_parser.py --limit 50
python run_parser.py --brand Garmin
python run_parser.py --dry-run
```

## Browser/CDP mode

DNS can return anti-bot `401 Unauthorized` for plain HTTP clients. The stable
mode is to run Chrome manually, log in/open DNS once, and let the parser reuse
that browser profile through CDP:

```powershell
chrome.exe --remote-debugging-port=9222 --user-data-dir=C:\work\dns_watch_parser\tmp\chrome-profile
python run_parser.py --browser-mode cdp --limit 50
```

Or use the helper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_chrome_cdp.ps1
```

If Playwright browser binaries are missing:

```powershell
python -m playwright install chromium
```

Do not store account passwords in `.env`. The parser can reuse cookies from the
browser profile or `tmp/state/dns_browser_state.json`.

## Tests

```powershell
pytest
```

## Notes

- `.env`, `tmp`, cache/debug files, and XLSX exports are ignored by git.
- Telegram reads `TELEGRAM_*` variables from `.env` or the environment.
- Public GitHub search did not reveal a suitable licensed DNS catalog parser. This implementation is standalone and uses only high-level ideas: catalog pagination, product-card extraction, retry/backoff, and resume state.
