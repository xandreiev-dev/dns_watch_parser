from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


OUTPUT_COLUMNS = [
    "source",
    "shop_id",
    "brand",
    "title",
    "product_name",
    "model_raw",
    "article",
    "product_id",
    "product_url",
    "image_url",
    "price",
    "old_price",
    "rating",
    "reviews",
    "availability",
    "stock_status",
    "city",
    "region",
    "delivery_text",
    "delivery_days",
    "warranty",
    "warranty_days",
    "specs_json",
    "raw_payload_json",
    "parsed_at",
    "case_size",
    "color",
    "connectivity",
    "seller",
    "category",
    "breadcrumbs",
]


@dataclass(slots=True)
class ProductRecord:
    source: str = "dns"
    shop_id: int | str = 0
    brand: str = ""
    title: str = ""
    product_name: str = ""
    model_raw: str = ""
    article: str = ""
    product_id: str = ""
    product_url: str = ""
    image_url: str = ""
    price: int | None = None
    old_price: int | None = None
    rating: float | None = None
    reviews: int | None = None
    availability: str = ""
    stock_status: str = ""
    city: str = ""
    region: str = ""
    delivery_text: str = ""
    delivery_days: int | None = None
    warranty: str = ""
    warranty_days: int | None = None
    specs_json: str = "{}"
    raw_payload_json: str = "{}"
    parsed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    case_size: str = ""
    color: str = ""
    connectivity: str = ""
    seller: str = ""
    category: str = ""
    breadcrumbs: str = ""

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        for column in OUTPUT_COLUMNS:
            row.setdefault(column, "")
        return {column: row.get(column, "") for column in OUTPUT_COLUMNS}


def json_dumps(value: Any) -> str:
    if value in (None, ""):
        return "{}"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
