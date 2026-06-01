from dns_watch_parser.normalizers.article import extract_article


def test_article_from_text():
    assert extract_article(text="Код товара: 5498271") == "5498271"


def test_article_from_dns_product_url_hash():
    url = "https://www.dns-shop.ru/product/38a4d8668b77d21a/smart-casy-apple-watch-series-10-46-mm/"
    assert extract_article(url=url) == "38a4d8668b77d21a"
