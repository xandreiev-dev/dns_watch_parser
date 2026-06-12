from dns_watch_parser.normalizers.delivery import extract_delivery_days


def test_delivery_days_relative_words():
    assert extract_delivery_days("Доставка сегодня") == 0
    assert extract_delivery_days("Самовывоз завтра") == 1
    assert extract_delivery_days("Доставим на дом за 2 часа") == 0


def test_delivery_days_numeric():
    assert extract_delivery_days("Доставка 3 дня") == 3
    assert extract_delivery_days("до 10 дней") == 10
