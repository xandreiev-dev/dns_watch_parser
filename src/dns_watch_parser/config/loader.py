from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from .settings import OutputSettings, ParserSettings, Settings, TelegramSettings, TmpSettings


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
    output_raw = data.get("output", {})
    tmp_raw = data.get("tmp", {})
    telegram_raw = data.get("telegram", {})

    parser = ParserSettings(**parser_raw)
    env_shop_id = os.getenv("DNS_SHOP_ID")
    if env_shop_id:
        parser.shop_id = env_shop_id

    output = OutputSettings(
        dir=_path(project_root, output_raw.get("dir", "brand_exports")),
        filename_prefix=output_raw.get("filename_prefix", "dns_watch"),
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
        output=output,
        tmp=tmp,
        telegram=telegram,
        brands=brands,
        start_urls=start_urls,
        config_path=config_path,
    )
