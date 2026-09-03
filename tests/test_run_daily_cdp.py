from scripts.run_daily_cdp import _same_page_url


def test_same_page_url_matches_encoded_and_decoded_dns_query():
    encoded = "https://www.dns-shop.ru/search/?q=%D1%81%D0%BC%D0%B0%D1%80%D1%82-%D1%87%D0%B0%D1%81%D1%8B&category=251c82c88ed24e77"
    decoded = "https://www.dns-shop.ru/search/?q=смарт-часы&category=251c82c88ed24e77"

    assert _same_page_url(encoded, decoded)


def test_same_page_url_ignores_fragment_and_trailing_slash():
    assert _same_page_url("https://www.dns-shop.ru/search/#top", "https://www.dns-shop.ru/search/")
