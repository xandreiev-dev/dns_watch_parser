from __future__ import annotations

import re


MAX_PRICE_RUB = 1_000_000


def normalize_price(value: str | int | float | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    compact = re.sub(r"[^\d]", "", value)
    return int(compact) if compact else None


def repair_concatenated_price(price: int | str | None, old_price: int | str | None, *, max_price: int = MAX_PRICE_RUB) -> int | None:
    """Fix DNS card prices accidentally read as current+old price.

    DNS sometimes renders the old price inside the current price container. If
    text extraction reads both descendants, `15 999` + `19 599` becomes
    `1599919599`. When the huge value ends with the separately parsed old
    price, the prefix is the real current price.
    """
    current = normalize_price(price)
    old = normalize_price(old_price)
    if current is None or current <= max_price:
        return current
    if old is None:
        return None

    current_digits = str(current)
    old_digits = str(old)
    if not current_digits.endswith(old_digits):
        return None

    repaired_digits = current_digits[: -len(old_digits)]
    if not repaired_digits:
        return None
    repaired = int(repaired_digits)
    if 0 < repaired <= max_price:
        return repaired
    return None
