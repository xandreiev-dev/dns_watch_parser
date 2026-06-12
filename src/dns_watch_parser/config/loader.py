from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from .settings import BrowserSettings, OutputSettings, ParserSettings, Settings, TelegramSettings, TmpSettings


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _path(base: Path, raw: str | Path) -> Path:
    value = Path(raw)
    if value.is_absolute():
        return value
    return (base / value).resolve()


def load_settings(path: str | Path = "config.toml") -> Settings:
    config_path = Path(path).resolve()
    project_root = config_path.parent
    load_dotenv(project_root / ".env")

    data = _read_toml(config_path)
    parser_raw = data.get("parser", {})
    browser_raw = data.get("browser", {})
    output_raw = data.get("output", {})
    tmp_raw = data.get("tmp", {})
    telegram_raw = data.get("telegram", {})

    parser = ParserSettings(**parser_raw)
    env_shop_id = os.getenv("DNS_SHOP_ID")
    if env_shop_id:
        parser.shop_id = env_shop_id
    env_mode = os.getenv("DNS_BROWSER_MODE")
    env_cdp_url = os.getenv("DNS_CDP_URL")
    env_proxy = os.getenv("DNS_PROXY_SERVER")

    browser = BrowserSettings(
        mode=env_mode or browser_raw.get("mode", "http"),
        cdp_url=env_cdp_url or browser_raw.get("cdp_url", "http://127.0.0.1:9222"),
        storage_state_path=_path(project_root, browser_raw.get("storage_state_path", "tmp/state/dns_browser_state.json")),
        page_wait_until=browser_raw.get("page_wait_until", "domcontentloaded"),
        page_wait_selector=browser_raw.get("page_wait_selector", ""),
        extra_wait_ms=int(browser_raw.get("extra_wait_ms", 1500)),
        auto_scroll=bool(browser_raw.get("auto_scroll", True)),
        scroll_steps=int(browser_raw.get("scroll_steps", 4)),
        proxy_server=env_proxy or browser_raw.get("proxy_server", ""),
        reuse_page=bool(browser_raw.get("reuse_page", False)),
        browser_retries=int(browser_raw.get("browser_retries", 2)),
        browser_connect_timeout=int(browser_raw.get("browser_connect_timeout", 10)),
    )

    output = OutputSettings(
        dir=_path(project_root, output_raw.get("dir", "brand_exports")),
        filename_prefix=output_raw.get("filename_prefix", "dns_watch"),
        include_timestamp=bool(output_raw.get("include_timestamp", True)),
    )
    tmp = TmpSettings(
        dir=_path(project_root, tmp_raw.get("dir", "tmp")),
        resume_state_path=_path(project_root, tmp_raw.get("resume_state_path", "tmp/state/dns_parser_state.json")),
    )
    telegram = TelegramSettings(enabled=bool(telegram_raw.get("enabled", False)))
    brands = list(data.get("brands", {}).get("items", []))
    start_urls = list(data.get("start_urls", {}).get("urls", []))

    return Settings(
        parser=parser,
        browser=browser,
        output=output,
        tmp=tmp,
        telegram=telegram,
        brands=brands,
        start_urls=start_urls,
        config_path=config_path,
    )
