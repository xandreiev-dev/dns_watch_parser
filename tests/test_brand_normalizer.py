from dns_watch_parser.normalizers.brand import normalize_brand


def test_brand_from_title():
    brands = ["Apple", "Samsung", "Garmin"]
    assert normalize_brand("Смарт-часы Apple Watch SE", brands) == "Apple"


def test_brand_hint_wins():
    assert normalize_brand("Смарт-часы Watch", ["Garmin"], hint="Garmin") == "Garmin"
