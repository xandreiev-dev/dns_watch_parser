from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from dns_watch_parser.browser import BrowserClient

from .pagination import page_url


PRODUCT_PATH_RE = re.compile(r"/product/(?:[a-z0-9]{8,32}/)?[^\"'#?\s]+/?", re.IGNORECASE)
ABSOLUTE_PRODUCT_RE = re.compile(r"https://www\.dns-shop\.ru/product/[^\"'\\<>\s]+/?", re.IGNORECASE)
logger = logging.getLogger(__name__)


class CatalogParser:
    def __init__(self, client: BrowserClient):
        self.client = client

    def collect_product_urls(self, start_urls: list[str], max_pages: int = 0, limit: int | None = None) -> list[str]:
        seen: dict[str, None] = {}
        pages = range(1, max_pages + 1) if max_pages and max_pages > 0 else range(1, 1000)
        for start_url in start_urls:
            empty_pages = 0
            for page in pages:
                current_url = page_url(start_url, page)
                try:
                    html = self.client.get_text(current_url)
                except Exception as exc:
                    logger.warning("Catalog page is not available: %s (%s)", current_url, exc)
                    break
                urls = extract_product_urls(html, start_url)
                if not urls:
                    empty_pages += 1
                    if empty_pages >= 2 or page == 1:
                        break
                    continue
                empty_pages = 0
                for url in urls:
                    seen.setdefault(url, None)
                    if limit and len(seen) >= limit:
                        return list(seen)
        return list(seen)


def extract_product_urls(html: str, base_url: str = "https://www.dns-shop.ru") -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: dict[str, None] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "/product/" not in href:
            continue
        normalized = normalize_product_url(urljoin(base_url, href))
        if normalized:
            urls.setdefault(normalized, None)

    for match in PRODUCT_PATH_RE.finditer(html):
        normalized = normalize_product_url(urljoin(base_url, match.group(0)))
        if normalized:
            urls.setdefault(normalized, None)
    for match in ABSOLUTE_PRODUCT_RE.finditer(html):
        normalized = normalize_product_url(match.group(0).replace("\\/", "/"))
        if normalized:
            urls.setdefault(normalized, None)
    return list(urls)


def normalize_product_url(url: str) -> str:
    if "/product/" not in url:
        return ""
    url = url.split("#", 1)[0].split("?", 1)[0]
    if not url.endswith("/"):
        url += "/"
    return url
