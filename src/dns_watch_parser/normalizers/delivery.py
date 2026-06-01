from __future__ import annotations

import re


def extract_delivery_days(value: str | None) -> int | None:
    if not value:
        return None
    text = value.lower()
    if "сегодня" in text:
        return 0
    if "завтра" in text:
        return 1
    match = re.search(r"(\d+)\s*(?:дн|день|дня|дней|сут)", text)
    if match:
        return int(match.group(1))
    return None
