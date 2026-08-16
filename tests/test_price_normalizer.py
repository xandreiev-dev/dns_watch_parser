from dns_watch_parser.normalizers.price import normalize_price, repair_concatenated_price


def test_normalize_price_removes_currency_and_spaces():
    assert normalize_price("29 990 ₽") == 29990
    assert normalize_price("1 234 567 руб.") == 1234567


def test_normalize_price_handles_empty_values():
    assert normalize_price("") is None
    assert normalize_price(None) is None


def test_repair_concatenated_price_with_old_price_suffix():
    assert repair_concatenated_price(1599919599, 19599) == 15999
    assert repair_concatenated_price(2899934499, 34499) == 28999


def test_repair_concatenated_price_rejects_unknown_huge_price():
    assert repair_concatenated_price(1599919599, None) is None
    assert repair_concatenated_price(1599919599, 34499) is None
