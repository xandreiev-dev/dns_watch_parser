from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook

from dns_watch_parser.models import OUTPUT_COLUMNS, ProductRecord
from dns_watch_parser.normalizers.price import MAX_PRICE_RUB, normalize_price, repair_concatenated_price
from dns_watch_parser.utils.paths import ensure_dir, safe_slug

logger = logging.getLogger(__name__)


def build_output_path(
    output_dir: str | Path,
    prefix: str,
    brand: str | None = None,
    *,
    include_timestamp: bool = True,
) -> Path:
    ensure_dir(output_dir)
    suffix = f"_{safe_slug(brand)}" if brand else ""
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d_%H-%M-%S") if include_timestamp else now.strftime("%Y%m%d")
    return Path(output_dir) / f"{prefix}{suffix}_{stamp}.xlsx"


@dataclass(slots=True)
class PriceQualityStats:
    rows_without_price: int = 0
    suspicious_price_rows: int = 0
    repaired_price_rows: int = 0
    skipped_price_rows: int = 0


class StreamingXlsxWriter:
    def __init__(self, path: str | Path, columns: list[str] | None = None):
        self.path = Path(path)
        self.temp_path = self._build_temp_path()
        self.columns = columns or OUTPUT_COLUMNS
        ensure_dir(self.path.parent)
        self.price_stats = PriceQualityStats()
        self.debug_path = self._build_debug_path()
        self._debug_initialized = False
        self.workbook = Workbook()
        self.sheet = self.workbook.active
        self.sheet.title = "Data"
        self.sheet.append(self.columns)
        self._save()
        self.rows_written = 0

    @staticmethod
    def excel_safe(value):
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    def append(self, record: ProductRecord | dict) -> bool:
        row = record.to_row() if isinstance(record, ProductRecord) else record
        row = dict(row)
        row = self._validate_price(row)
        if row is None:
            return False
        self.sheet.append([self.excel_safe(row.get(column, "")) for column in self.columns])
        self.rows_written += 1
        self._save()
        return True

    def append_many(self, records: Iterable[ProductRecord | dict]) -> None:
        for record in records:
            self.append(record)

    def _save(self) -> None:
        self.workbook.save(self.temp_path)

    def close(self, *, commit: bool = True) -> None:
        self._save()
        if commit:
            self.temp_path.replace(self.path)
            logger.info("XLSX export committed: %s", self.path)
        elif self.temp_path.exists():
            logger.warning("XLSX export was not committed; removing temporary file: %s", self.temp_path)
            self.temp_path.unlink()
        logger.info(
            "Price validation: rows_without_price=%s, suspicious_price_rows=%s, "
            "repaired_price_rows=%s, skipped_price_rows=%s%s",
            self.price_stats.rows_without_price,
            self.price_stats.suspicious_price_rows,
            self.price_stats.repaired_price_rows,
            self.price_stats.skipped_price_rows,
            f", debug_file={self.debug_path}" if self._debug_initialized else "",
        )

    def _validate_price(self, row: dict) -> dict | None:
        price = normalize_price(row.get("price"))
        old_price = normalize_price(row.get("old_price"))
        row["price"] = price
        row["old_price"] = old_price

        if price is None:
            self.price_stats.rows_without_price += 1
            return row
        if price <= MAX_PRICE_RUB:
            return row

        self.price_stats.suspicious_price_rows += 1
        repaired = repair_concatenated_price(price, old_price)
        if repaired is not None:
            row["price"] = repaired
            self.price_stats.repaired_price_rows += 1
            self._write_debug_row("repaired", row, original_price=price, repaired_price=repaired)
            return row

        self.price_stats.skipped_price_rows += 1
        self._write_debug_row("skipped", row, original_price=price, repaired_price=None)
        return None

    def _build_debug_path(self) -> Path:
        debug_root = self.path.parent.parent / "debug" if self.path.parent.name == "brand_exports" else self.path.parent / "debug"
        return debug_root / f"{self.path.stem}_price_debug.csv"

    def _build_temp_path(self) -> Path:
        return self.path.with_name(f".{self.path.stem}.{os.getpid()}.tmp.xlsx")

    def _write_debug_row(self, action: str, row: dict, *, original_price: int, repaired_price: int | None) -> None:
        if not self._debug_initialized:
            ensure_dir(self.debug_path.parent)
            with self.debug_path.open("w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["action", "title", "product_url", "original_price", "repaired_price", "old_price"])
            self._debug_initialized = True
        with self.debug_path.open("a", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    action,
                    row.get("title", ""),
                    row.get("product_url", ""),
                    original_price,
                    repaired_price or "",
                    row.get("old_price", ""),
                ]
            )
