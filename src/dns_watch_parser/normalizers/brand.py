from __future__ import annotations

import re


ALIASES = {
    "хуавей": "Huawei",
    "самсунг": "Samsung",
    "сяоми": "Xiaomi",
    "эппл": "Apple",
}


def normalize_brand(title: str, known_brands: list[str], hint: str = "") -> str:
    if hint:
        return _display(hint, known_brands)
    source = title.lower()
    for brand in known_brands:
        if re.search(rf"\b{re.escape(brand.lower())}\b", source):
            return _display(brand, known_brands)
    for alias, brand in ALIASES.items():
        if alias in source:
            return brand
    return ""


def _display(value: str, known_brands: list[str]) -> str:
    for brand in known_brands:
        if brand.lower() == value.lower():
            return brand
    return value.strip()
