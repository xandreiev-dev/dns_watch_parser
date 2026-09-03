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

## Browser/CDP Mode

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

Recommended ramp-up:

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
Before writing XLSX rows, the exporter validates `price` and `old_price` as
separate numeric fields. A `price` above `1_000_000` is treated as suspicious:
known DNS current-price + old-price concatenations are repaired, and
unrepairable rows are skipped to `debug/*_price_debug.csv`.
XLSX export is committed atomically: rows are first written to a temporary
`.tmp.xlsx` file, and the final `DNS_watch_ru_YYYYMMDD.xlsx` is replaced only
after a successful parser finish. Interrupted runs therefore cannot silently
leave a half-written file as the daily export.
After a run, validate the matcher-ready XLSX before import:

```powershell
python scripts\audit_price_quality.py brand_exports\DNS_watch_ru_YYYYMMDD.xlsx
```

For a broader health check, inspect recent XLSX files and the scheduled run
log together:

```powershell
python scripts\diagnose_exports.py
```

The parser also stops catalog pagination when a page contains no new products,
so repeated DNS pages do not turn into a long no-op run.
During catalog collection, the log prints per-page progress:
`Catalog record page N: parsed=..., new=..., total=...`. This helps separate a
slow DNS page from a real parser hang during scheduled runs.
The production CDP helper also enforces a minimum row count by default:

```powershell
python scripts\run_daily_cdp.py --port 9223 --parser-timeout-minutes 180 --min-exported-rows 1000
```

If DNS returns too few rows, the run exits with an error and keeps the previous
valid XLSX untouched.
The default config targets the DNS search page for smart watches and bracelets.
DNS loads this page lazily while scrolling, so `scroll_steps` is intentionally
high enough to reach the full search result set shown by the site.
If a long run leaves Chrome tabs at `chrome-error://chromewebdata/`, close the
CDP Chrome window and start it again with `python scripts\start_chrome_cdp.py`.

## Daily Windows Run

Use `run_dns_watch.bat` for the scheduled production run. The wrapper starts a
short-lived CDP Chrome on port `9223`, waits for DNS to settle, runs the parser,
writes logs to `logs\scheduled_run.log`, and closes only that CDP Chrome
instance when finished.

The BAT files use their own folder as the project root, so the same files work
from `C:\work\dns_watch_parser` locally and from `C:\parsers\dns_watch_parser`
on the server. They also run the explicit `.venv\Scripts\python.exe`, which
keeps Task Scheduler from accidentally using a different Python installation.
Each scheduled run logs a small runtime fingerprint: project path, Python
version, git revision when available, and hashes of the key parser files.

Task Scheduler example:

```powershell
schtasks /Create /TN "DNS Watch Parser" /TR "C:\parsers\dns_watch_parser\run_dns_watch.bat" /SC DAILY /ST 15:00 /RL HIGHEST /F
```

Manual production-equivalent run:

```powershell
run_dns_watch.bat
```

Debug run:

```powershell
run_dns_watch_test.bat
```

If some cards fail, inspect `tmp/state/dns_parser_state.json`. It stores both
`failed_urls` and `failed_reasons`. To retry only failed cards:

```powershell
python run_parser.py --browser-mode cdp --retry-failed --limit 20 --no-telegram
```

Telegram is intended for run-level summaries only. Use `--no-telegram` while
debugging parser quality.

## FTP Pull

If the parser runs on a separate server, the import/matcher server can download
the ready XLSX by FTP instead of receiving an upload from the parser server:

```powershell
python download_latest_from_ftp.py
```

For Windows Task Scheduler, use the wrapper:

```powershell
C:\work\dns_watch_parser\pull_dns_watch_from_ftp.bat
```

Hourly schedule example:

```powershell
schtasks /Create /TN "Pull DNS Watch XLSX" /TR "C:\work\dns_watch_parser\pull_dns_watch_from_ftp.bat" /SC HOURLY /MO 1 /RL HIGHEST /F
```

Configure `.env` on the server that downloads the file:

```env
FTP_SOURCE_HOST=157.22.253.66
FTP_SOURCE_PATH=/dns_parser/brand_exports/
FTP_FILE_PREFIX=DNS_watch_ru
FTP_TARGET_DIR=brand_exports
FTP_PORT=1029
FTP_USER=guser
FTP_PASS=...
FTP_PASSIVE=true
```

Use the prefix that actually exists on the source FTP. For example, if the
source server exports `DNS_ru_YYYYMMDD.xlsx`, set `FTP_FILE_PREFIX=DNS_ru`.

## Tests

```powershell
pytest
```

## Notes

- `.env`, `tmp`, cache/debug files, and XLSX exports are ignored by git.
- Telegram reads `TELEGRAM_*` variables from `.env` or the environment.
- Public GitHub search did not reveal a suitable licensed DNS catalog parser. This implementation is standalone and uses only high-level ideas: catalog pagination, product-card extraction, retry/backoff, and resume state.
