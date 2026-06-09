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


def embedded_json_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for script in soup.find_all("script"):
        raw = script.string or script.get_text()
        if not raw or ("product" not in raw.lower() and "price" not in raw.lower()):
            continue
        for candidate in _json_object_candidates(raw):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                objects.append(payload)
    return objects


def deep_find_values(value: Any, keys: set[str]) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in keys:
                found.append(nested)
            found.extend(deep_find_values(nested, keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(deep_find_values(item, keys))
    return found


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


def _json_object_candidates(raw: str) -> list[str]:
    candidates: list[str] = []
    for marker in ("window.__INITIAL_STATE__", "window.__NUXT__", "__NEXT_DATA__"):
        pos = raw.find(marker)
        if pos < 0:
            continue
        brace = raw.find("{", pos)
        if brace >= 0:
            candidate = _balanced_json(raw, brace)
            if candidate:
                candidates.append(candidate)
    return candidates


def _balanced_json(raw: str, start: int) -> str:
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(raw)):
        char = raw[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw[start : index + 1]
    return ""
