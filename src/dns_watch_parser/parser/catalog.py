from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from dns_watch_parser.browser import BrowserClient
from dns_watch_parser.models import ProductRecord
from dns_watch_parser.models.product import json_dumps
from dns_watch_parser.normalizers import extract_article, extract_delivery_days, normalize_brand, normalize_price
from dns_watch_parser.normalizers.text import clean_text

from .pagination import page_url


PRODUCT_PATH_RE = re.compile(r"/product/(?:[a-z0-9]{8,32}/)?[^\"'#?\s]+/?", re.IGNORECASE)
ABSOLUTE_PRODUCT_RE = re.compile(r"https://www\.dns-shop\.ru/product/[^\"'\\<>\s]+/?", re.IGNORECASE)
logger = logging.getLogger(__name__)


class CatalogParser:
    def __init__(self, client: BrowserClient, *, known_brands: list[str] | None = None, source: str = "dns", shop_id=0):
        self.client = client
        self.known_brands = known_brands or []
        self.source = source
        self.shop_id = shop_id

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

    def collect_catalog_records(self, start_urls: list[str], max_pages: int = 0, limit: int | None = None) -> list[ProductRecord]:
        records: dict[str, ProductRecord] = {}
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

                page_records = extract_catalog_records(
                    html,
                    current_url,
                    known_brands=self.known_brands,
                    source=self.source,
                    shop_id=self.shop_id,
                )
                if not page_records:
                    empty_pages += 1
                    if empty_pages >= 2 or page == 1:
                        break
                    continue
                empty_pages = 0
                for record in page_records:
                    records.setdefault(record.product_url, record)
                    if limit and len(records) >= limit:
                        return list(records.values())
        return list(records.values())


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


def extract_catalog_records(
    html: str,
    base_url: str = "https://www.dns-shop.ru",
    *,
    known_brands: list[str] | None = None,
    source: str = "dns",
    shop_id=0,
) -> list[ProductRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[ProductRecord] = []
    for card in soup.select(".catalog-product"):
        record = _record_from_card(card, base_url, known_brands or [], source, shop_id)
        if record and record.product_url:
            records.append(record)
    return records


def _record_from_card(card, base_url: str, known_brands: list[str], source: str, shop_id) -> ProductRecord | None:
    name_node = card.select_one(".catalog-product__name[href]")
    if not name_node:
        name_node = card.select_one("a[href*='/product/']")
    if not name_node:
        return None

    product_url = normalize_product_url(urljoin(base_url, name_node.get("href", "")))
    title = clean_text(name_node.get_text(" ", strip=True))
    if not title:
        title = clean_text((card.select_one("img") or {}).get("alt", ""))
    if not product_url or not title:
        return None

    price = normalize_price(_node_text(card, ".product-buy__price"))
    old_price = normalize_price(_node_text(card, ".product-buy__prev"))
    rating, reviews = _parse_rating(_node_text(card, ".catalog-product__rating"))
    image_url = _image_url(card, base_url)
    delivery_text = _catalog_delivery_text(card)
    article = extract_article(product_url)
    brand = normalize_brand(title, known_brands)

    return ProductRecord(
        source=source,
        shop_id=shop_id,
        brand=brand,
        title=_title_without_brackets(title),
        product_name=_title_without_brackets(title),
        model_raw=_model_raw(title, brand),
        article=article,
        product_id=article,
        product_url=product_url,
        image_url=image_url,
        price=price,
        old_price=old_price,
        rating=rating,
        reviews=reviews,
        availability=_catalog_availability(card),
        stock_status=_catalog_stock_status(card),
        delivery_text=delivery_text,
        delivery_days=extract_delivery_days(delivery_text),
        warranty="",
        specs_json=json_dumps({"catalog_title": title}),
        raw_payload_json=json_dumps({"source": "catalog_card"}),
        case_size=_first_match(title, [r"(\d{2}\s*mm)", r"(\d+(?:[.,]\d+)?\")"]),
        color=_catalog_color(title),
        connectivity=_catalog_connectivity(title),
        seller="DNS",
        category="Смарт-часы и браслеты",
        breadcrumbs="Каталог > Смартфоны и фототехника > Смартфоны и гаджеты > Смарт-часы и браслеты",
    )


def _node_text(card, selector: str) -> str:
    node = card.select_one(selector)
    return clean_text(node.get_text(" ", strip=True)) if node else ""


def _image_url(card, base_url: str) -> str:
    image = card.select_one("img")
    if not image:
        return ""
    for attr in ("data-src", "src"):
        value = image.get(attr)
        if value:
            return urljoin(base_url, value)
    return ""


def _parse_rating(value: str) -> tuple[float | None, int | None]:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*\|\s*([\d.,]+\s*[kк]?)", value, flags=re.IGNORECASE)
    if not match:
        return None, None
    rating = float(match.group(1).replace(",", "."))
    reviews_text = match.group(2).lower().replace(",", ".").replace(" ", "")
    multiplier = 1000 if reviews_text.endswith(("k", "к")) else 1
    reviews_text = re.sub(r"[^0-9.]", "", reviews_text)
    reviews = int(float(reviews_text) * multiplier) if reviews_text else None
    return rating, reviews


def _catalog_availability(card) -> str:
    text = clean_text(card.get_text(" ", strip=True)).lower()
    if "в наличии" in text:
        return "in_stock"
    return ""


def _catalog_stock_status(card) -> str:
    text = clean_text(card.get_text(" ", strip=True)).lower()
    if "нет в наличии" in text:
        return "out_of_stock"
    if "в наличии" in text:
        return "in_stock"
    return ""


def _catalog_delivery_text(card) -> str:
    text = clean_text(card.get_text(" ", strip=True))
    match = re.search(r"((?:доставим|доставка|самовывоз)[^.]{0,80})", text, flags=re.IGNORECASE)
    return clean_text(match.group(1)) if match else ""


def _title_without_brackets(title: str) -> str:
    return clean_text(title.split("[", 1)[0])


def _model_raw(title: str, brand: str) -> str:
    value = _title_without_brackets(title)
    value = re.sub(r"^(?:смарт-часы|умные часы|спортивные часы|детские часы)\s+", "", value, flags=re.IGNORECASE)
    if brand:
        value = re.sub(rf"^{re.escape(brand)}\s+", "", value, flags=re.IGNORECASE)
    return clean_text(value)


def _first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""


def _catalog_color(title: str) -> str:
    return _first_match(title, [r"корпус\s*-\s*([^,\]]+)", r"ремешок\s*-\s*([^,\]]+)"])


def _catalog_connectivity(title: str) -> str:
    found = []
    for token in ("Bluetooth", "Wi-Fi", "NFC", "LTE", "eSIM", "GPS", "4G"):
        if re.search(re.escape(token), title, flags=re.IGNORECASE):
            found.append(token)
    return ", ".join(found)
