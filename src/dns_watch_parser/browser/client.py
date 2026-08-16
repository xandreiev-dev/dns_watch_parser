from __future__ import annotations

import logging
import random
import asyncio
import threading
import time
import json
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse
from urllib.parse import unquote

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
    cdp_url: str = "http://127.0.0.1:9223"
    storage_state_path: Path | None = None
    page_wait_until: str = "domcontentloaded"
    page_wait_selector: str = ""
    extra_wait_ms: int = 1500
    auto_scroll: bool = True
    scroll_steps: int = 4
    proxy_server: str = ""
    reuse_page: bool = False
    browser_retries: int = 2
    browser_connect_timeout: int = 10
    _client: httpx.Client = field(init=False, repr=False)
    _playwright: object | None = field(init=False, default=None, repr=False)
    _browser: object | None = field(init=False, default=None, repr=False)
    _context: object | None = field(init=False, default=None, repr=False)
    _page: object | None = field(init=False, default=None, repr=False)
    _owns_browser: bool = field(init=False, default=False, repr=False)

    def __post_init__(self) -> None:
        self.rate_limiter = self.rate_limiter or RateLimiter()
        self.retry_policy = self.retry_policy or RetryPolicy()
        self._client = httpx.Client(follow_redirects=True, timeout=self.timeout, trust_env=False)
        self.browser_mode = (self.browser_mode or "http").lower().strip()

    def close(self) -> None:
        self._client.close()
        self._save_storage_state()
        if self._page is not None and not self.reuse_page:
            try:
                self._page.close()
            except Exception:
                pass
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
            return self._get_text_with_browser_retry(url)

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

    def get_card_htmls(self, url: str, card_selector: str, link_selector: str) -> list[str]:
        if self.browser_mode not in {"playwright", "cdp"}:
            return []
        return self._run_browser_card_fetch(url, card_selector, link_selector)

    def check_health(self, expected_url: str = "") -> None:
        if self.browser_mode != "cdp":
            return
        base_url = self.cdp_url.rstrip("/")
        tabs: list[dict] = []
        last_exc: Exception | None = None
        for attempt in range(max(1, self.browser_retries + 1)):
            try:
                _get_cdp_json(base_url + "/json/version", self.browser_connect_timeout)
                if not expected_url:
                    return

                tabs = _get_cdp_json(base_url + "/json", self.browser_connect_timeout)
                break
            except Exception as exc:
                last_exc = exc
                if attempt >= self.browser_retries:
                    raise
                time.sleep(2)

        if last_exc is not None and not tabs:
            raise last_exc
        page_urls = [tab.get("url", "") for tab in tabs if tab.get("type") == "page"]
        healthy_urls = [url for url in page_urls if url and not url.startswith("chrome-error://")]
        if not any(_same_page_url(url, expected_url) for url in healthy_urls):
            raise RuntimeError(
                "CDP is alive, but the expected DNS catalog tab is not ready. "
                f"Expected: {expected_url}. Open tabs: {', '.join(page_urls) or 'none'}"
            )

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
            self._browser = chromium.connect_over_cdp(self.cdp_url, timeout=self.browser_connect_timeout * 1000)
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
        self._page = (pages[0] if pages else self._context.new_page()) if self.reuse_page else self._context.new_page()
        return self._page

    def _get_text_with_browser_retry(self, url: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(self.browser_retries + 1):
            try:
                return self._run_browser_fetch(url)
            except Exception as exc:
                last_exc = exc
                logger.warning("Browser request failed for %s: %s", url, exc)
                self._reset_browser_page()
                if attempt >= self.browser_retries:
                    break
        assert last_exc is not None
        raise last_exc

    def _run_browser_fetch(self, url: str) -> str:
        """Run Playwright through its async API, even when caller is sync.

        Some hosts run Python commands inside an already active asyncio loop.
        Playwright's sync API refuses to start in that situation, so browser
        fetching is isolated in an async coroutine and, when needed, a helper
        thread with its own event loop.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._get_text_with_browser_async(url))

        result: dict[str, str] = {}
        errors: list[BaseException] = []

        def runner() -> None:
            try:
                result["html"] = asyncio.run(self._get_text_with_browser_async(url))
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if errors:
            raise errors[0]
        return result["html"]

    def _run_browser_card_fetch(self, url: str, card_selector: str, link_selector: str) -> list[str]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._get_card_htmls_async(url, card_selector, link_selector))

        result: dict[str, list[str]] = {}
        errors: list[BaseException] = []

        def runner() -> None:
            try:
                result["cards"] = asyncio.run(self._get_card_htmls_async(url, card_selector, link_selector))
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if errors:
            raise errors[0]
        return result["cards"]

    async def _get_text_with_browser_async(self, url: str) -> str:
        assert self.rate_limiter is not None
        self.rate_limiter.wait()

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Browser mode is enabled but playwright is not installed") from exc

        async with async_playwright() as playwright:
            chromium = playwright.chromium
            browser = None
            context = None
            page = None
            try:
                if self.browser_mode == "cdp":
                    browser = await chromium.connect_over_cdp(
                        self.cdp_url,
                        timeout=self.browser_connect_timeout * 1000,
                    )
                    contexts = list(browser.contexts)
                    context = contexts[0] if contexts else await browser.new_context()
                else:
                    launch_kwargs = {"headless": self.headless}
                    if self.proxy_server:
                        launch_kwargs["proxy"] = {"server": self.proxy_server}
                    browser = await chromium.launch(**launch_kwargs)
                    context_kwargs = {"user_agent": (self.user_agents or ["Mozilla/5.0"])[0]}
                    if self.storage_state_path and self.storage_state_path.exists():
                        context_kwargs["storage_state"] = str(self.storage_state_path)
                    context = await browser.new_context(**context_kwargs)

                pages = list(context.pages)
                page = pages[0] if self.reuse_page and pages else await context.new_page()
                if _normalized_url(page.url) != _normalized_url(url):
                    try:
                        await page.goto(url, wait_until=self.page_wait_until, timeout=self.timeout * 1000)
                    except Exception:
                        if _normalized_url(page.url) != _normalized_url(url):
                            raise
                        logger.warning("Navigation failed, using already opened CDP page: %s", page.url)
                if self.page_wait_selector:
                    try:
                        await page.wait_for_selector(self.page_wait_selector, timeout=self.timeout * 1000)
                    except Exception as exc:
                        logger.debug("Selector wait failed for %s: %s", self.page_wait_selector, exc)
                if self.extra_wait_ms > 0:
                    await page.wait_for_timeout(self.extra_wait_ms)
                if self.auto_scroll:
                    await _auto_scroll_async(page, max(0, self.scroll_steps))
                html = await page.content()
                if self.storage_state_path is not None:
                    self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
                    await context.storage_state(path=str(self.storage_state_path))
                return html
            finally:
                if page is not None and not self.reuse_page:
                    try:
                        await page.close()
                    except Exception:
                        pass
                if browser is not None and self.browser_mode != "cdp":
                    await browser.close()

    async def _get_card_htmls_async(self, url: str, card_selector: str, link_selector: str) -> list[str]:
        assert self.rate_limiter is not None
        self.rate_limiter.wait()

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Browser mode is enabled but playwright is not installed") from exc

        async with async_playwright() as playwright:
            chromium = playwright.chromium
            browser = None
            page = None
            try:
                browser, context, page = await self._open_async_page(chromium, url)
                if self.reuse_page and _normalized_url(page.url) != _normalized_url(url):
                    await page.goto(url, wait_until=self.page_wait_until, timeout=self.timeout * 1000)
                try:
                    await page.wait_for_selector(card_selector, timeout=self.timeout * 1000)
                except Exception as exc:
                    logger.debug("Card selector wait failed for %s: %s", card_selector, exc)
                if self.extra_wait_ms > 0:
                    await page.wait_for_timeout(self.extra_wait_ms)
                await page.keyboard.press("Home")
                await page.wait_for_timeout(500)

                cards_by_url: dict[str, str] = {}
                stale_steps = 0
                for _ in range(max(1, self.scroll_steps) + 1):
                    batch = await page.locator(card_selector).evaluate_all(
                        """(cards, linkSelector) => cards.map((card) => {
                            const link = card.querySelector(linkSelector);
                            return {url: link ? link.href : "", html: card.outerHTML};
                        })""",
                        link_selector,
                    )
                    before = len(cards_by_url)
                    for item in batch:
                        item_url = item.get("url") if isinstance(item, dict) else ""
                        item_html = item.get("html") if isinstance(item, dict) else ""
                        if item_url and item_html:
                            normalized_url = item_url.split("?")[0]
                            previous_html = cards_by_url.get(normalized_url, "")
                            if _is_richer_card_html(item_html, previous_html):
                                cards_by_url[normalized_url] = item_html
                    stale_steps = stale_steps + 1 if len(cards_by_url) == before else 0
                    if stale_steps >= 10 and cards_by_url:
                        break
                    await page.mouse.wheel(0, 1800)
                    await page.wait_for_timeout(350)

                if self.storage_state_path is not None:
                    self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
                    await context.storage_state(path=str(self.storage_state_path))
                return list(cards_by_url.values())
            finally:
                if page is not None and not self.reuse_page:
                    try:
                        await page.close()
                    except Exception:
                        pass
                if browser is not None and self.browser_mode != "cdp":
                    await browser.close()

    async def _open_async_page(self, chromium, url: str):
        if self.browser_mode == "cdp":
            browser = await chromium.connect_over_cdp(
                self.cdp_url,
                timeout=self.browser_connect_timeout * 1000,
            )
            contexts = list(browser.contexts)
            matching_page = _find_matching_page(contexts, url)
            if self.reuse_page and matching_page is not None:
                return browser, matching_page.context, matching_page
            context = contexts[0] if contexts else await browser.new_context()
        else:
            launch_kwargs = {"headless": self.headless}
            if self.proxy_server:
                launch_kwargs["proxy"] = {"server": self.proxy_server}
            browser = await chromium.launch(**launch_kwargs)
            context_kwargs = {"user_agent": (self.user_agents or ["Mozilla/5.0"])[0]}
            if self.storage_state_path and self.storage_state_path.exists():
                context_kwargs["storage_state"] = str(self.storage_state_path)
            context = await browser.new_context(**context_kwargs)

        pages = list(context.pages)
        page = pages[0] if self.reuse_page and pages else await context.new_page()
        if _normalized_url(page.url) != _normalized_url(url):
            try:
                await page.goto(url, wait_until=self.page_wait_until, timeout=self.timeout * 1000)
            except Exception:
                matching_page = _find_matching_page(browser.contexts, url)
                if matching_page is None:
                    raise
                page = matching_page
                context = page.context
                logger.warning("Navigation failed, using already opened CDP page: %s", page.url)
        return browser, context, page

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
        if not self.reuse_page:
            page.close()
            self._page = None
        return html

    def _save_storage_state(self) -> None:
        if self._context is None or self.storage_state_path is None:
            return
        try:
            self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            self._context.storage_state(path=str(self.storage_state_path))
        except Exception as exc:
            logger.debug("Could not save browser storage state: %s", exc)

    def _reset_browser_page(self) -> None:
        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None


def _auto_scroll(page, steps: int) -> None:
    for _ in range(steps):
        page.mouse.wheel(0, 1800)
        page.wait_for_timeout(350)


async def _auto_scroll_async(page, steps: int) -> None:
    for _ in range(steps):
        await page.mouse.wheel(0, 1800)
        await page.wait_for_timeout(350)


def _looks_like_blocked_page(html: str) -> bool:
    lowered = html.lower()
    return "__qrator" in lowered or "qauth" in lowered or ("dns-shop" in lowered and "/product/" not in lowered)


def _is_richer_card_html(candidate: str, current: str) -> bool:
    if not current:
        return True
    candidate_score = _card_html_score(candidate)
    current_score = _card_html_score(current)
    return candidate_score > current_score or (candidate_score == current_score and len(candidate) > len(current))


def _card_html_score(html: str) -> int:
    lowered = html.lower()
    score = len(html)
    for token in ("product-buy__price", "₽", "в наличии", "доставим", "доставка", "рейтинг", "отзыв"):
        if token in lowered:
            score += 5000
    return score


def _normalized_url(url: str) -> str:
    return (url or "").split("#", 1)[0].rstrip("/")


def _get_cdp_json(url: str, timeout: int):
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"

    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Connection: close\r\n"
        "Accept: application/json\r\n"
        "\r\n"
    ).encode("ascii")
    with socket.create_connection((host, port), timeout=timeout) as connection:
        connection.settimeout(timeout)
        connection.sendall(request)
        chunks: list[bytes] = []
        while True:
            chunk = connection.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            raw = b"".join(chunks)
            headers, separator, body = raw.partition(b"\r\n\r\n")
            if separator and len(body) >= _content_length(headers):
                break

    raw = b"".join(chunks)
    _, _, body = raw.partition(b"\r\n\r\n")
    return json.loads(body.decode("utf-8"))


def _content_length(headers: bytes) -> int:
    for line in headers.splitlines():
        if line.lower().startswith(b"content-length:"):
            return int(line.split(b":", 1)[1].strip())
    return 0


def _same_page_url(left: str, right: str) -> bool:
    return unquote(_normalized_url(left)) == unquote(_normalized_url(right))


def _find_matching_page(contexts, url: str):
    for context in contexts:
        for page in context.pages:
            if _same_page_url(page.url, url):
                return page
    return None
