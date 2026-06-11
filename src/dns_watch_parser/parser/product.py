from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from dns_watch_parser.browser import BrowserClient
from dns_watch_parser.models import ProductRecord
from dns_watch_parser.models.product import json_dumps
from dns_watch_parser.normalizers import extract_article, extract_delivery_days, extract_warranty_days, normalize_brand, normalize_price
from dns_watch_parser.normalizers.text import clean_text

from .extractor import deep_find_values, embedded_json_objects, extract_breadcrumbs, extract_specs, find_json_ld_product, first_meta, regex_first


class ProductParser:
    def __init__(
        self,
        client: BrowserClient,
        *,
        known_brands: list[str],
        source: str = "dns",
        shop_id: int | str = 0,
        city: str = "",
        region: str = "",
    ):
        self.client = client
        self.known_brands = known_brands
        self.source = source
        self.shop_id = shop_id
        self.city = city
        self.region = region

    def parse_url(self, url: str, brand_hint: str = "") -> ProductRecord:
        html = self.client.get_text(url)
        return parse_product_html(
            html,
            url=url,
            known_brands=self.known_brands,
            brand_hint=brand_hint,
            source=self.source,
            shop_id=self.shop_id,
            city=self.city,
            region=self.region,
        )


def parse_product_html(
    html: str,
    *,
    url: str,
    known_brands: list[str],
    brand_hint: str = "",
    source: str = "dns",
    shop_id: int | str = 0,
    city: str = "",
    region: str = "",
) -> ProductRecord:
    soup = BeautifulSoup(html, "html.parser")
    product_json = find_json_ld_product(soup)
    embedded_json = embedded_json_objects(soup)
    text = clean_text(soup.get_text(" ", strip=True))

    title = clean_text(
        str(product_json.get("name") or "")
        or first_meta(soup, "og:title", "twitter:title")
        or _first_css_text(soup, ["h1", ".product-card-top__title", "[data-product-title]", "[itemprop=name]"])
        or _first_deep_value(embedded_json, {"name", "title"})
    )
    image_url = _extract_image(product_json, soup)
    offers = _as_dict(product_json.get("offers"))
    aggregate_rating = _as_dict(product_json.get("aggregateRating"))
    specs = extract_specs(soup)
    warranty = _first_spec(specs, ["гарантия", "срок гарантии"]) or regex_first([r"(гарантия[^.]{0,80})"], text)
    delivery_text = _extract_delivery_text(soup, text)
    availability = clean_text(str(offers.get("availability") or _first_css_text(soup, ["[class*=availability]", "[class*=stock]"])))
    price = normalize_price(
        offers.get("price")
        or first_meta(soup, "product:price:amount", "og:price:amount")
        or _first_attr(soup, ["[data-price]", "[itemprop=price]"], ["data-price", "content"])
        or _first_deep_value(embedded_json, {"price", "currentprice"})
        or regex_first([r"(\d[\d\s]{2,}\s*₽)"], text)
    )
    old_price = normalize_price(regex_first([r"(?:старая цена|до скидки)\D{0,20}(\d[\d\s]{2,}\s*₽)"], text))
    rating = _to_float(aggregate_rating.get("ratingValue") or regex_first([r"(\d[.,]\d{1,2})\s*\|\s*\d+\s*отзы"], text))
    reviews = _to_int(aggregate_rating.get("reviewCount") or regex_first([r"(\d+(?:[.,]\d+)?\s*[kк]?)\s*отзы"], text))
    article = extract_article(url, text)
    brand = normalize_brand(title, known_brands, brand_hint)

    return ProductRecord(
        source=source,
        shop_id=shop_id,
        brand=brand,
        title=title,
        product_name=title,
        model_raw=_model_raw(title, brand),
        article=article,
        product_id=article,
        product_url=url,
        image_url=image_url,
        price=price,
        old_price=old_price,
        rating=rating,
        reviews=reviews,
        availability=availability,
        stock_status=_stock_status(availability, text),
        city=city,
        region=region,
        delivery_text=delivery_text,
        delivery_days=extract_delivery_days(delivery_text),
        warranty=warranty,
        warranty_days=extract_warranty_days(warranty),
        specs_json=json_dumps(specs),
        raw_payload_json=json_dumps({"json_ld_product": product_json, "embedded_json_count": len(embedded_json)}),
        case_size=_extract_case_size(title, specs),
        color=_extract_color(title, specs),
        connectivity=_extract_connectivity(title, specs),
        seller="DNS",
        category=_category_from_breadcrumbs(extract_breadcrumbs(soup)),
        breadcrumbs=extract_breadcrumbs(soup),
    )


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return value[0] if value and isinstance(value[0], dict) else {}
    return value if isinstance(value, dict) else {}


def _first_css_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            return clean_text(node.get_text(" ", strip=True))
    return ""


def _extract_delivery_text(soup: BeautifulSoup, page_text: str) -> str:
    selectors = [
        "[class*=delivery]",
        "[class*=pickup]",
        "[class*=order-avail]",
        "[data-commerce-target*=delivery]",
    ]
    for selector in selectors:
        value = _first_css_text(soup, [selector])
        if _looks_like_delivery(value):
            return value

    patterns = [
        r"((?:доставка|самовывоз)[^.;]{0,100}(?:сегодня|завтра|\d{1,2}\s*(?:дн|день|дня|дней|января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)))",
    ]
    value = regex_first(patterns, page_text)
    return value if _looks_like_delivery(value) else ""


def _looks_like_delivery(value: str) -> bool:
    if not value:
        return False
    lowered = value.lower()
    if len(value) > 220:
        return False
    navigation_markers = ("покупателям", "юрлицам", "клуб dns", "вакансии", "вернуться на главную")
    if any(marker in lowered for marker in navigation_markers):
        return False
    return "доставка" in lowered or "самовывоз" in lowered


def _first_attr(soup: BeautifulSoup, selectors: list[str], attrs: list[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        for attr in attrs:
            value = node.get(attr)
            if value:
                return clean_text(str(value))
    return ""


def _first_deep_value(objects: list[dict[str, Any]], keys: set[str]) -> str:
    normalized_keys = {key.lower() for key in keys}
    for obj in objects:
        for value in deep_find_values(obj, normalized_keys):
            if isinstance(value, (str, int, float)) and str(value).strip():
                return clean_text(str(value))
    return ""


def _extract_image(product_json: dict[str, Any], soup: BeautifulSoup) -> str:
    image = product_json.get("image")
    if isinstance(image, list):
        return str(image[0]) if image else ""
    if image:
        return str(image)
    return first_meta(soup, "og:image", "twitter:image")


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).lower().replace(",", ".").replace(" ", "")
    multiplier = 1000 if text.endswith(("k", "к")) else 1
    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None
    return int(float(text) * multiplier)


def _stock_status(availability: str, text: str) -> str:
    source = f"{availability} {text}".lower()
    if "outofstock" in source or "нет в наличии" in source:
        return "out_of_stock"
    if "instock" in source or "в наличии" in source:
        return "in_stock"
    return ""


def _model_raw(title: str, brand: str) -> str:
    value = title
    prefixes = ["смарт-часы", "умные часы", "спортивные часы", "детские часы"]
    for prefix in prefixes:
        value = re.sub(rf"^{prefix}\s+", "", value, flags=re.IGNORECASE)
    if brand:
        value = re.sub(rf"^{re.escape(brand)}\s+", "", value, flags=re.IGNORECASE)
    return clean_text(value.split("[", 1)[0])


def _first_spec(specs: dict[str, str], names: list[str]) -> str:
    for key, value in specs.items():
        key_lower = key.lower()
        if any(name in key_lower for name in names):
            return value
    return ""


def _extract_case_size(title: str, specs: dict[str, str]) -> str:
    value = _first_spec(specs, ["диагональ", "размер корпуса", "размер"])
    if value:
        return value
    return regex_first([r"(\d{2}\s*mm)", r"(\d+(?:[.,]\d+)?\")"], title)


def _extract_color(title: str, specs: dict[str, str]) -> str:
    value = _first_spec(specs, ["цвет корпуса", "цвет ремешка", "цвет"])
    if value:
        return value
    return regex_first([r"корпус\s*-\s*([^,\]]+)", r"ремешок\s*-\s*([^,\]]+)"], title)


def _extract_connectivity(title: str, specs: dict[str, str]) -> str:
    value = _first_spec(specs, ["беспроводные интерфейсы", "интерфейсы", "связь"])
    if value:
        return value
    found = []
    for token in ("Bluetooth", "Wi-Fi", "NFC", "LTE", "eSIM", "GPS", "ANT+"):
        if re.search(re.escape(token), title, flags=re.IGNORECASE):
            found.append(token)
    return ", ".join(found)


def _category_from_breadcrumbs(value: str) -> str:
    parts = [part.strip() for part in value.split(">") if part.strip()]
    return parts[-1] if parts else ""
