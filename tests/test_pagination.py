from dns_watch_parser.parser.pagination import page_url


def test_page_url_uses_dns_page_param():
    assert page_url("https://www.dns-shop.ru/catalog/smart-casy/", 2) == "https://www.dns-shop.ru/catalog/smart-casy/?page=2"


def test_page_url_cleans_page_params_for_first_page():
    assert page_url("https://www.dns-shop.ru/catalog/smart-casy/?page=4&p=4", 1) == "https://www.dns-shop.ru/catalog/smart-casy/"
