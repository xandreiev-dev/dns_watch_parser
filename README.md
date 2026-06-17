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
chrome.exe --remote-debugging-port=9223 --user-data-dir=C:\work\dns_watch_parser\tmp\chrome-profile
python run_parser.py --browser-mode cdp --limit 50
```

Or use the helper:

```powershell
python scripts\start_chrome_cdp.py
```

If Playwright browser binaries are missing:

```powershell
python -m playwright install chromium
```

Do not store account passwords in `.env`. The parser can reuse cookies from the
browser profile or `tmp/state/dns_browser_state.json`.

Recommended production ramp-up:

```powershell
python run_parser.py --browser-mode cdp --catalog-only --limit 30 --reset-state --no-telegram
python run_parser.py --browser-mode cdp --limit 3 --reset-state --dry-run --no-telegram
python run_parser.py --browser-mode cdp --limit 30 --reset-state --no-telegram
python run_parser.py --browser-mode cdp --limit 100 --reset-state --no-telegram
python run_parser.py --browser-mode cdp --reset-state --no-telegram
```

Use `--catalog-only` for the fast matcher-oriented export. It reads product
cards from catalog pages and does not open every product URL. Product pages are
still useful for enriched fields such as full specs and numeric DNS SKU.
The parser also stops catalog pagination when a page contains no new products,
so repeated DNS pages do not turn into a long no-op run.
The default config targets the DNS search page for smart watches and bracelets.
DNS loads this page lazily while scrolling, so `scroll_steps` is intentionally
high enough to reach the full search result set shown by the site.
If a long run leaves Chrome tabs at `chrome-error://chromewebdata/`, close the
CDP Chrome window and start it again with `python scripts\start_chrome_cdp.py`.

If some cards fail, inspect `tmp/state/dns_parser_state.json`. It stores both
`failed_urls` and `failed_reasons`. To retry only failed cards:

```powershell
python run_parser.py --browser-mode cdp --retry-failed --limit 20 --no-telegram
```

Telegram is intended for run-level summaries only. Use `--no-telegram` while
debugging parser quality.

## Tests

```powershell
pytest
```

## Windows Server Daily Run

Install dependencies once:

```bat
cd /d C:\work\dns_watch_parser
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

Create the daily Windows Task Scheduler task at 17:00:

```bat
scripts\install_daily_task.bat
```

Manual server run:

```bat
scripts\run_dns_parser.bat
```

The runner uses Chrome CDP on `127.0.0.1:9223`, so it does not conflict with
the Ozon parser on `9222`. Logs are appended to `logs\dns_watch_parser_daily.log`.

## Notes

- `.env`, `tmp`, cache/debug files, and XLSX exports are ignored by git.
- Telegram reads `TELEGRAM_*` variables from `.env` or the environment.
- Public GitHub search did not reveal a suitable licensed DNS catalog parser. This implementation is standalone and uses only high-level ideas: catalog pagination, product-card extraction, retry/backoff, and resume state.
