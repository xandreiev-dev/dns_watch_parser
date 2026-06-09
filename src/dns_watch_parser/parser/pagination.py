from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def page_url(url: str, page: int) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if page <= 1:
        query.pop("p", None)
        query.pop("page", None)
    else:
        query["page"] = str(page)
    return urlunparse(parsed._replace(query=urlencode(query)))
