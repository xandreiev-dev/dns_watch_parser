from __future__ import annotations

import re
from urllib.parse import urlparse


def extract_article(url: str = "", text: str = "") -> str:
    haystack = " ".join([url or "", text or ""])
    for pattern in (
        r"(?:код\s*товара|артикул)\D{0,10}(\d{5,12})",
        r"[?&](?:product|id|code)=(\d{5,12})",
        r"/product/[a-z0-9]+/[^/]+/.*?(\d{5,12})",
    ):
        match = re.search(pattern, haystack, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    path = urlparse(url).path
    match = re.search(r"/product/([a-f0-9]{12,32})/", path)
    return match.group(1) if match else ""
