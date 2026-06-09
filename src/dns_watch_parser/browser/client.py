from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import httpx

from .rate_limiter import RateLimiter
from .retry import RetryPolicy, RetryableHttpError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BrowserClient:
    timeout: int = 30
    user_agents: list[str] | None = None
    rate_limiter: RateLimiter | None = None
    retry_policy: RetryPolicy | None = None
    use_playwright_fallback: bool = False
    headless: bool = True
    browser_mode: str = "http"
    cdp_url: str = "http://127.0.0.1:9222"
    storage_state_path: Path | None = None
    page_wait_until: str = "domcontentloaded"
    page_wait_selector: str = ""
    extra_wait_ms: int = 1500
    auto_scroll: bool = True
    scroll_steps: int = 4
    proxy_server: str = ""
    _client: httpx.Client = field(init=False, repr=False)
    _playwright: object | None = field(init=False, default=None, repr=False)
    _browser: object | None = field(init=False, default=None, repr=False)
    _context: object | None = field(init=False, default=None, repr=False)
    _page: object | None = field(init=False, default=None, repr=False)
    _owns_browser: bool = field(init=False, default=False, repr=False)

    def __post_init__(self) -> None:
        self.rate_limiter = self.rate_limiter or RateLimiter()
        self.retry_policy = self.retry_policy or RetryPolicy()
        self._client = httpx.Client(follow_redirects=True, timeout=self.timeout)
        self.browser_mode = (self.browser_mode or "http").lower().strip()

    def close(self) -> None:
        self._client.close()
        self._save_storage_state()
        if self._browser is not None and self._owns_browser:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def _headers(self) -> Mapping[str, str]:
        agents = self.user_agents or []
        user_agent = random.choice(agents) if agents else "Mozilla/5.0"
        return {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.6,en;q=0.5",
            "Referer": "https://www.dns-shop.ru/",
        }

    def get_text(self, url: str) -> str:
        if self.browser_mode in {"playwright", "cdp"}:
            return self._get_text_with_browser(url)

        def request() -> str:
            assert self.rate_limiter is not None
            self.rate_limiter.wait()
            response = self._client.get(url, headers=self._headers())
            assert self.retry_policy is not None
            if response.status_code in self.retry_policy.retry_statuses:
                if self.use_playwright_fallback and response.status_code in (401, 403):
                    return self._get_text_with_browser(url)
                raise RetryableHttpError(response.status_code)
            response.raise_for_status()
            if self.use_playwright_fallback and _looks_like_blocked_page(response.text):
                return self._get_text_with_browser(url)
            return response.text

        assert self.retry_policy is not None
        return self.retry_policy.run(request)

    def _ensure_browser_page(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Browser mode is enabled but playwright is not installed") from exc

        self._playwright = sync_playwright().start()
        chromium = self._playwright.chromium
        if self.browser_mode == "cdp":
            self._browser = chromium.connect_over_cdp(self.cdp_url, timeout=self.timeout * 1000)
            contexts = list(self._browser.contexts)
            self._context = contexts[0] if contexts else self._browser.new_context()
            self._owns_browser = False
        else:
            launch_kwargs = {"headless": self.headless}
            if self.proxy_server:
                launch_kwargs["proxy"] = {"server": self.proxy_server}
            self._browser = chromium.launch(**launch_kwargs)
            self._owns_browser = True
            context_kwargs = {"user_agent": (self.user_agents or ["Mozilla/5.0"])[0]}
            if self.storage_state_path and self.storage_state_path.exists():
                context_kwargs["storage_state"] = str(self.storage_state_path)
            self._context = self._browser.new_context(**context_kwargs)

        pages = list(self._context.pages)
        self._page = pages[0] if pages else self._context.new_page()
        return self._page

    def _get_text_with_browser(self, url: str) -> str:
        assert self.rate_limiter is not None
        self.rate_limiter.wait()
        page = self._ensure_browser_page()
        page.goto(url, wait_until=self.page_wait_until, timeout=self.timeout * 1000)
        if self.page_wait_selector:
            try:
                page.wait_for_selector(self.page_wait_selector, timeout=self.timeout * 1000)
            except Exception as exc:
                logger.debug("Selector wait failed for %s: %s", self.page_wait_selector, exc)
        if self.extra_wait_ms > 0:
            page.wait_for_timeout(self.extra_wait_ms)
        if self.auto_scroll:
            _auto_scroll(page, max(0, self.scroll_steps))
        html = page.content()
        self._save_storage_state()
        return html

    def _save_storage_state(self) -> None:
        if self._context is None or self.storage_state_path is None:
            return
        try:
            self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            self._context.storage_state(path=str(self.storage_state_path))
        except Exception as exc:
            logger.debug("Could not save browser storage state: %s", exc)


def _auto_scroll(page, steps: int) -> None:
    for _ in range(steps):
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(350)


def _looks_like_blocked_page(html: str) -> bool:
    lowered = html.lower()
    return "__qrator" in lowered or "qauth" in lowered or ("dns-shop" in lowered and "/product/" not in lowered)
