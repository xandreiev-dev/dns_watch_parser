from __future__ import annotations

import ftplib
import os
import re
import time
from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DEFAULT_FILE_PREFIX = "DNS_watch_ru"
DEFAULT_REMOTE_DIR = "/dns_parser/brand_exports/"


@dataclass(slots=True)
class RemoteFile:
    name: str
    run_date: datetime
    size: int | None = None


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip().strip('"')


def _file_re(prefix: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(prefix)}_(\d{{8}}|\d{{4}}-\d{{2}}-\d{{2}})\.xlsx$", re.IGNORECASE)


def _parse_run_date(name: str, prefix: str) -> datetime | None:
    match = _file_re(prefix).match(name)
    if not match:
        return None
    raw = match.group(1)
    fmt = "%Y%m%d" if "-" not in raw else "%Y-%m-%d"
    return datetime.strptime(raw, fmt)


def _target_name(remote_name: str, prefix: str) -> str:
    run_date = _parse_run_date(remote_name, prefix)
    if not run_date:
        return remote_name
    return f"{prefix}_{run_date.strftime('%Y%m%d')}.xlsx"


def _remote_size(ftp: ftplib.FTP, name: str) -> int | None:
    try:
        return ftp.size(name)
    except ftplib.all_errors:
        return None


def _list_remote_exports(ftp: ftplib.FTP, prefix: str) -> list[RemoteFile]:
    files: list[RemoteFile] = []
    for name in ftp.nlst():
        path_name = Path(name).name
        run_date = _parse_run_date(path_name, prefix)
        if not run_date:
            continue
        files.append(RemoteFile(name=path_name, run_date=run_date, size=_remote_size(ftp, path_name)))
    return sorted(files, key=lambda item: item.run_date, reverse=True)


def _download_once() -> int:
    host = _env("FTP_SOURCE_HOST") or _env("FTP_OZON_HOST")
    port = int(_env("FTP_PORT", "21"))
    user = _env("FTP_USER")
    password = _env("FTP_PASS")
    remote_dir = _env("FTP_SOURCE_PATH") or _env("FTP_OZON_PATH", DEFAULT_REMOTE_DIR)
    target_dir = Path(_env("FTP_TARGET_DIR", str(BASE_DIR / "brand_exports")))
    passive = _env("FTP_PASSIVE", "true").lower() not in {"0", "false", "no"}
    file_prefix = _env("FTP_FILE_PREFIX", DEFAULT_FILE_PREFIX)

    if not all([host, user, password]):
        print("FTP_SOURCE_HOST/FTP_OZON_HOST, FTP_USER and FTP_PASS must be set in .env")
        return 1

    target_dir.mkdir(parents=True, exist_ok=True)

    with ftplib.FTP() as ftp:
        print(f"Connecting to {host}:{port}, passive={passive}")
        ftp.connect(host, port, timeout=60)
        ftp.login(user, password)
        ftp.set_pasv(passive)
        ftp.cwd(remote_dir)
        ftp.voidcmd("TYPE I")

        exports = _list_remote_exports(ftp, file_prefix)
        if not exports:
            print(f"No {file_prefix}_*.xlsx files found in {remote_dir}")
            return 1

        latest = exports[0]
        final_name = _target_name(latest.name, file_prefix)
        final_path = target_dir / final_name
        temp_path = target_dir / f"{final_name}.download"

        if final_path.exists() and latest.size and final_path.stat().st_size == latest.size:
            print(f"Already downloaded: {final_path}")
            return 0

        print(f"Latest remote file: {latest.name}")
        print(f"Local target file: {final_path}")
        with temp_path.open("wb") as file:
            ftp.retrbinary(f"RETR {latest.name}", file.write, blocksize=1024 * 128)

        if latest.size and temp_path.stat().st_size != latest.size:
            print(f"Downloaded size mismatch: local={temp_path.stat().st_size}, remote={latest.size}")
            return 1
        if temp_path.stat().st_size == 0:
            print("Downloaded file is empty")
            return 1

        temp_path.replace(final_path)
        print(f"Downloaded {final_path.name} ({final_path.stat().st_size} bytes)")
        return 0


def main() -> int:
    parser = ArgumentParser(description="Download the latest parser XLSX from FTP.")
    parser.add_argument("--watch", action="store_true", help="Keep checking FTP in a loop.")
    parser.add_argument("--interval-minutes", type=float, default=60.0, help="Delay between checks in watch mode.")
    args = parser.parse_args()

    if not args.watch:
        return _download_once()

    while True:
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{started_at}] FTP check started")
        try:
            result = _download_once()
        except Exception as exc:  # noqa: BLE001 - scheduled watcher should keep working after transient FTP errors.
            result = 1
            print(f"FTP check failed: {type(exc).__name__}: {exc}")
        print(f"FTP check finished with exit code {result}")
        time.sleep(max(60.0, args.interval_minutes * 60.0))


if __name__ == "__main__":
    raise SystemExit(main())
