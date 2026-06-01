from __future__ import annotations

import re


def extract_warranty_days(value: str | None) -> int | None:
    if not value:
        return None
    text = value.lower()
    match = re.search(r"(\d+)\s*(?:мес|месяц|месяца|месяцев)", text)
    if match:
        return int(match.group(1)) * 30
    match = re.search(r"(\d+)\s*(?:год|года|лет)", text)
    if match:
        return int(match.group(1)) * 365
    match = re.search(r"(\d+)\s*(?:дн|день|дня|дней)", text)
    if match:
        return int(match.group(1))
    return None
