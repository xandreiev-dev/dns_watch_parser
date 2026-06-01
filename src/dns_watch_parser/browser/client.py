from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Mapping

import httpx

from .rate_limiter import RateLimiter
from .retry import RetryPolicy, RetryableHttpError


@dataclass(slots=True)
class BrowserClient:
    timeout: int = 30
    user_agents: list[str] | None = None
    rate_limiter: RateLimiter | None = None
    retry_policy: RetryPolicy | None = None
    use_playwright_fallback: bool = False
    headless: bool = True
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.rate_limiter = self.rate_limiter or RateLimiter()
        self.retry_policy = self.retry_policy or RetryPolicy()
        self._client = httpx.Client(follow_redirects=True, timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

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
        def request() -> str:
            assert self.rate_limiter is not None
            self.rate_limiter.wait()
            response = self._client.get(url, headers=self._headers())
            assert self.retry_policy is not None
            if response.status_code in self.retry_policy.retry_statuses:
                if self.use_playwright_fallback and response.status_code in (401, 403):
                    return self._get_text_with_playwright(url)
                raise RetryableHttpError(response.status_code)
            response.raise_for_status()
            if self.use_playwright_fallback and _looks_like_blocked_page(response.text):
                return self._get_text_with_playwright(url)
            return response.text

        assert self.retry_policy is not None
        return self.retry_policy.run(request)

    def _get_text_with_playwright(self, url: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Playwright fallback is enabled but playwright is not installed") from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            page = browser.new_page(user_agent=(self.user_agents or ["Mozilla/5.0"])[0])
            page.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)
            html = page.content()
            browser.close()
            return html


def _looks_like_blocked_page(html: str) -> bool:
    lowered = html.lower()
    return "__qrator" in lowered or "qauth" in lowered or ("dns-shop" in lowered and "/product/" not in lowered)
