from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook

from dns_watch_parser.models import OUTPUT_COLUMNS, ProductRecord
from dns_watch_parser.utils.paths import ensure_dir, safe_slug


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
    stamp = now.strftime("%Y-%m-%d_%H-%M-%S") if include_timestamp else now.date().isoformat()
    return Path(output_dir) / f"{prefix}{suffix}_{stamp}.xlsx"


class StreamingXlsxWriter:
    def __init__(self, path: str | Path, columns: list[str] | None = None):
        self.path = Path(path)
        self.columns = columns or OUTPUT_COLUMNS
        ensure_dir(self.path.parent)
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

    def append(self, record: ProductRecord | dict) -> None:
        row = record.to_row() if isinstance(record, ProductRecord) else record
        self.sheet.append([self.excel_safe(row.get(column, "")) for column in self.columns])
        self.rows_written += 1
        self._save()

    def append_many(self, records: Iterable[ProductRecord | dict]) -> None:
        for record in records:
            self.append(record)

    def _save(self) -> None:
        self.workbook.save(self.path)

    def close(self) -> None:
        self._save()
