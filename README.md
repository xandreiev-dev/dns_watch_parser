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

## Tests

```powershell
pytest
```

## Notes

- `.env`, `tmp`, cache/debug files, and XLSX exports are ignored by git.
- Telegram reads `TELEGRAM_*` variables from `.env` or the environment.
- Public GitHub search did not reveal a suitable licensed DNS catalog parser. This implementation is standalone and uses only high-level ideas: catalog pagination, product-card extraction, retry/backoff, and resume state.
