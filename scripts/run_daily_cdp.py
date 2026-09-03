from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import unquote


DEFAULT_START_URL = (
    "https://www.dns-shop.ru/search/"
    "?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82-%D1%87%D0%B0%D1%81%D1%8B"
    "&category=251c82c88ed24e77"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run DNS parser with a short-lived CDP Chrome")
    parser.add_argument("--port", type=int, default=9223, help="Chrome remote debugging port")
    parser.add_argument(
        "--profile-dir",
        default=str(Path(__file__).resolve().parents[1] / "tmp" / "chrome-profile"),
        help="Dedicated Chrome profile directory",
    )
    parser.add_argument("--start-url", default=DEFAULT_START_URL, help="URL to open before parsing")
    parser.add_argument("--browser", default="", help="Explicit path to chrome.exe/msedge.exe")
    parser.add_argument("--wait-timeout", type=int, default=90, help="Seconds to wait for CDP")
    parser.add_argument("--settle-seconds", type=int, default=15, help="Seconds to let DNS page settle")
    parser.add_argument(
        "--parser-timeout-minutes",
        type=int,
        default=180,
        help="Maximum parser runtime before it is stopped and Chrome is closed",
    )
    parser.add_argument(
        "--min-exported-rows",
        type=int,
        default=1000,
        help="Minimum successful XLSX rows expected from the full DNS catalog",
    )
    parser.add_argument("--no-telegram", action="store_true", help="Disable Telegram for this parser run")
    parser.add_argument("--keep-browser-on-fail", action="store_true", help="Leave CDP Chrome open if parser fails")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_dir = Path(__file__).resolve().parents[1]
    profile_dir = Path(args.profile_dir).expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    browser = Path(args.browser).expanduser() if args.browser else find_browser()
    if browser is None:
        print("Chrome or Edge executable was not found.", file=sys.stderr)
        return 1

    print_runtime_fingerprint(project_dir)

    cdp_url = f"http://127.0.0.1:{args.port}"
    chrome_process: subprocess.Popen | None = None
    parser_code = 1

    try:
        clean_stale_temp_exports(project_dir)
        stop_cdp_chrome(args.port)
        time.sleep(3)

        chrome_cmd = [
            str(browser),
            f"--remote-debugging-port={args.port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            args.start_url,
        ]
        chrome_process = subprocess.Popen(chrome_cmd, close_fds=True)
        print(f"Chrome started on CDP port {args.port}")
        print(f"Browser: {browser}")
        print(f"Profile: {profile_dir}")

        if not wait_for_cdp(args.port, args.wait_timeout):
            print(f"CDP did not answer at {cdp_url}", file=sys.stderr)
            return 1

        print("CDP is ready")
        if args.settle_seconds > 0:
            print(f"Waiting {args.settle_seconds} sec for DNS page to settle")
            time.sleep(args.settle_seconds)
        if not wait_for_expected_page(args.port, args.start_url, 30):
            print(
                f"Expected DNS catalog tab is not ready after Chrome startup: {args.start_url}",
                file=sys.stderr,
            )
            return 1

        parser_cmd = [
            sys.executable,
            str(project_dir / "run_parser.py"),
            "--browser-mode",
            "cdp",
            "--cdp-url",
            cdp_url,
            "--catalog-only",
            "--reset-state",
            "--min-exported-rows",
            str(args.min_exported_rows),
        ]
        if args.no_telegram:
            parser_cmd.append("--no-telegram")

        print("Starting DNS parser")
        timeout_seconds = args.parser_timeout_minutes * 60 if args.parser_timeout_minutes > 0 else None
        try:
            parser_code = subprocess.run(parser_cmd, cwd=str(project_dir), timeout=timeout_seconds).returncode
        except subprocess.TimeoutExpired:
            parser_code = 124
            print(
                f"DNS parser exceeded {args.parser_timeout_minutes} minutes; "
                "stopping parser and closing CDP Chrome",
                file=sys.stderr,
            )
        print(f"DNS parser exited with code {parser_code}")
        return parser_code
    finally:
        if args.keep_browser_on_fail and parser_code != 0:
            print("Parser failed; keeping CDP Chrome open for inspection")
        else:
            print("Closing CDP Chrome")
            if chrome_process is not None:
                terminate_process_tree(chrome_process.pid)
            stop_cdp_chrome(args.port)
            if chrome_process is not None and chrome_process.poll() is None:
                try:
                    chrome_process.terminate()
                    chrome_process.wait(timeout=10)
                except Exception:
                    try:
                        chrome_process.kill()
                    except Exception:
                        pass


def find_browser() -> Path | None:
    candidates = [
        _env_path("PROGRAMFILES", "Google", "Chrome", "Application", "chrome.exe"),
        _env_path("PROGRAMFILES(X86)", "Google", "Chrome", "Application", "chrome.exe"),
        _env_path("LOCALAPPDATA", "Google", "Chrome", "Application", "chrome.exe"),
        _env_path("PROGRAMFILES", "Microsoft", "Edge", "Application", "msedge.exe"),
        _env_path("PROGRAMFILES(X86)", "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    return next((path for path in candidates if path and path.exists()), None)


def _env_path(env_name: str, *parts: str) -> Path | None:
    root = os.environ.get(env_name)
    return Path(root, *parts) if root else None


def wait_for_cdp(port: int, timeout: int) -> bool:
    deadline = time.monotonic() + max(0, timeout)
    url = f"http://127.0.0.1:{port}/json/version"
    while time.monotonic() <= deadline:
        try:
            with urlopen(url, timeout=2) as response:
                return response.status == 200
        except (OSError, URLError):
            time.sleep(1)
    return False


def wait_for_expected_page(port: int, expected_url: str, timeout: int) -> bool:
    deadline = time.monotonic() + max(0, timeout)
    url = f"http://127.0.0.1:{port}/json"
    while time.monotonic() <= deadline:
        try:
            tabs = _read_cdp_json(url)
            page_urls = [tab.get("url", "") for tab in tabs if tab.get("type") == "page"]
            if any(_same_page_url(page_url, expected_url) for page_url in page_urls):
                return True
        except (OSError, URLError, ValueError):
            pass
        time.sleep(1)
    return False


def _read_cdp_json(url: str):
    with urlopen(url, timeout=2) as response:
        import json

        return json.loads(response.read().decode("utf-8"))


def _same_page_url(left: str, right: str) -> bool:
    return unquote((left or "").split("#", 1)[0].rstrip("/")) == unquote(
        (right or "").split("#", 1)[0].rstrip("/")
    )


def print_runtime_fingerprint(project_dir: Path) -> None:
    print(f"Project: {project_dir}")
    print(f"Python: {sys.executable}")
    print(f"Python version: {sys.version.split()[0]}")
    revision = current_git_revision(project_dir)
    if revision:
        print(f"Git revision: {revision}")
    else:
        print("Git revision: unavailable")

    for relative_path in (
        "config.toml",
        "src/dns_watch_parser/browser/client.py",
        "src/dns_watch_parser/parser/catalog.py",
        "src/dns_watch_parser/storage/exports.py",
    ):
        path = project_dir / relative_path
        print(f"Fingerprint {relative_path}: {file_fingerprint(path)}")


def current_git_revision(project_dir: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(project_dir),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def file_fingerprint(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def stop_cdp_chrome(port: int) -> None:
    command = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.Name -eq 'chrome.exe' -and $_.CommandLine -like '*remote-debugging-port={port}*' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def terminate_process_tree(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def clean_stale_temp_exports(project_dir: Path) -> None:
    export_dir = project_dir / "brand_exports"
    if not export_dir.exists():
        return
    for path in export_dir.glob(".*.tmp.xlsx"):
        try:
            path.unlink()
            print(f"Removed stale temporary export: {path}")
        except OSError as exc:
            print(f"Could not remove stale temporary export {path}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
