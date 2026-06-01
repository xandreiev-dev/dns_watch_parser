from __future__ import annotations

import re


def normalize_price(value: str | int | float | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    compact = re.sub(r"[^\d]", "", value)
    return int(compact) if compact else None
