from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_START_URL = (
    "https://www.dns-shop.ru/search/"
    "?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82-%D1%87%D0%B0%D1%81%D1%8B"
    "&category=251c82c88ed24e77"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start Chrome or Edge for DNS parser CDP mode")
    parser.add_argument("--port", type=int, default=9223, help="Remote debugging port")
    parser.add_argument(
        "--profile-dir",
        default=str(Path(__file__).resolve().parents[1] / "tmp" / "chrome-profile"),
        help="Dedicated browser profile directory",
    )
    parser.add_argument("--start-url", default=DEFAULT_START_URL, help="URL to open")
    parser.add_argument("--browser", default="", help="Explicit path to chrome.exe/msedge.exe")
    parser.add_argument("--wait-timeout", type=int, default=30, help="Seconds to wait until CDP is ready")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if wait_for_cdp(args.port, 1):
        print(f"CDP is already ready on port {args.port}")
        print("Run parser:")
        print("python run_parser.py --browser-mode cdp --catalog-only --reset-state")
        return 0

    browser = Path(args.browser).expanduser() if args.browser else find_browser()
    if browser is None:
        print("Chrome or Edge executable was not found.", file=sys.stderr)
        return 1

    profile_dir = Path(args.profile_dir).expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(browser),
        f"--remote-debugging-port={args.port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        args.start_url,
    ]
    subprocess.Popen(cmd, close_fds=True)

    print(f"Browser started on CDP port {args.port}")
    print(f"Browser: {browser}")
    print(f"Profile: {profile_dir}")
    if wait_for_cdp(args.port, args.wait_timeout):
        print("CDP is ready")
    else:
        print("CDP did not answer yet; wait for Chrome to finish loading before running parser")
    print("Open DNS/login once if needed, make sure search results are visible, then run:")
    print("python run_parser.py --browser-mode cdp --catalog-only --reset-state")
    return 0


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


if __name__ == "__main__":
    raise SystemExit(main())
