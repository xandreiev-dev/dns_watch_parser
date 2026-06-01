from openpyxl import load_workbook

from dns_watch_parser.models import OUTPUT_COLUMNS, ProductRecord
from dns_watch_parser.storage.exports import StreamingXlsxWriter


def test_export_schema_columns(tmp_path):
    path = tmp_path / "out.xlsx"
    writer = StreamingXlsxWriter(path)
    writer.append(ProductRecord(title="Смарт-часы Apple Watch", product_url="https://example.test"))
    writer.close()

    workbook = load_workbook(path)
    sheet = workbook.active
    columns = [cell.value for cell in sheet[1]]

    assert columns == OUTPUT_COLUMNS
    assert sheet.max_row == 2
