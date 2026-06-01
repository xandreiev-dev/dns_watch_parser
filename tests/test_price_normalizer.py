from dns_watch_parser.normalizers.price import normalize_price


def test_normalize_price_removes_currency_and_spaces():
    assert normalize_price("29 990 ₽") == 29990
    assert normalize_price("1 234 567 руб.") == 1234567


def test_normalize_price_handles_empty_values():
    assert normalize_price("") is None
    assert normalize_price(None) is None
