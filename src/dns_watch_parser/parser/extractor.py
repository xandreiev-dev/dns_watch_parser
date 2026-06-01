from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from dns_watch_parser.normalizers.text import clean_text


def first_meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return ""


def json_ld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            objects.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                objects.extend(item for item in graph if isinstance(item, dict))
            objects.append(payload)
    return objects


def find_json_ld_product(soup: BeautifulSoup) -> dict[str, Any]:
    for obj in json_ld_objects(soup):
        raw_type = obj.get("@type")
        types = raw_type if isinstance(raw_type, list) else [raw_type]
        if "Product" in types:
            return obj
    return {}


def extract_breadcrumbs(soup: BeautifulSoup) -> str:
    items: list[str] = []
    for obj in json_ld_objects(soup):
        raw_type = obj.get("@type")
        if raw_type == "BreadcrumbList":
            for item in obj.get("itemListElement", []):
                name = item.get("name") if isinstance(item, dict) else ""
                if name:
                    items.append(clean_text(name))
    if items:
        return " > ".join(items)
    crumbs = [clean_text(node.get_text(" ", strip=True)) for node in soup.select("[class*=breadcrumb] a")]
    return " > ".join([crumb for crumb in crumbs if crumb])


def extract_specs(soup: BeautifulSoup) -> dict[str, str]:
    specs: dict[str, str] = {}
    selectors = [
        ".product-characteristics__spec",
        ".product-characteristics__group",
        "[class*=characteristics]",
    ]
    for selector in selectors:
        for block in soup.select(selector):
            text = clean_text(block.get_text(" ", strip=True))
            if not text:
                continue
            match = re.match(r"(.{2,80}?)[\s:]+(.{1,300})$", text)
            if match:
                key = clean_text(match.group(1))
                value = clean_text(match.group(2))
                if key and value and key not in specs:
                    specs[key] = value
    return specs


def regex_first(patterns: list[str], text: str, flags: int = re.IGNORECASE) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=flags)
        if match:
            return clean_text(match.group(1))
    return ""
