from dns_watch_parser.normalizers.warranty import extract_warranty_days


def test_warranty_months_and_years():
    assert extract_warranty_days("12 месяцев") == 360
    assert extract_warranty_days("2 года") == 730


def test_warranty_days():
    assert extract_warranty_days("90 дней") == 90
