from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_BRANDS = [
    "Apple",
    "Samsung",
    "Garmin",
    "Huawei",
    "Honor",
    "Amazfit",
    "Xiaomi",
    "Redmi",
    "Google",
    "OnePlus",
    "Oppo",
    "Motorola",
]


@dataclass(slots=True)
class ParserSettings:
    source: str = "dns"
    shop_id: int | str = 0
    max_pages_per_brand: int = 0
    request_timeout: int = 30
    delay_min: float = 2
    delay_max: float = 6
    max_retries: int = 5
    resume_enabled: bool = True
    headless: bool = True
    use_playwright_fallback: bool = False
    user_agent: str = ""
    user_agents: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BrowserSettings:
    mode: str = "http"
    cdp_url: str = "http://127.0.0.1:9222"
    storage_state_path: Path = Path("tmp/state/dns_browser_state.json")
    page_wait_until: str = "domcontentloaded"
    page_wait_selector: str = ""
    extra_wait_ms: int = 1500
    auto_scroll: bool = True
    scroll_steps: int = 4
    proxy_server: str = ""
    reuse_page: bool = False
    browser_retries: int = 2
    browser_connect_timeout: int = 10


@dataclass(slots=True)
class OutputSettings:
    dir: Path = Path("brand_exports")
    filename_prefix: str = "dns_watch"
    include_timestamp: bool = True


@dataclass(slots=True)
class TmpSettings:
    dir: Path = Path("tmp")
    resume_state_path: Path = Path("tmp/state/dns_parser_state.json")


@dataclass(slots=True)
class TelegramSettings:
    enabled: bool = False


@dataclass(slots=True)
class Settings:
    parser: ParserSettings = field(default_factory=ParserSettings)
    browser: BrowserSettings = field(default_factory=BrowserSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    tmp: TmpSettings = field(default_factory=TmpSettings)
    telegram: TelegramSettings = field(default_factory=TelegramSettings)
    brands: list[str] = field(default_factory=lambda: DEFAULT_BRANDS.copy())
    start_urls: list[str] = field(default_factory=list)
    config_path: Path = Path("config.toml")
