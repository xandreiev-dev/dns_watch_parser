from dns_watch_parser.parser.product import parse_product_html


def test_parse_product_json_ld():
    html = """
    <html>
      <head>
        <meta property="og:image" content="https://img.test/watch.jpg">
        <script type="application/ld+json">
        {
          "@type": "Product",
          "name": "Смарт-часы Apple Watch SE 44 mm [корпус - черный, Bluetooth, NFC]",
          "image": "https://img.test/apple.jpg",
          "offers": {"price": "29990", "availability": "https://schema.org/InStock"},
          "aggregateRating": {"ratingValue": "4.8", "reviewCount": "120"}
        }
        </script>
      </head>
      <body>Код товара: 5439187 Гарантия 12 месяцев Доставка 2 дня</body>
    </html>
    """

    record = parse_product_html(
        html,
        url="https://www.dns-shop.ru/product/6705b978851ded20/smart-casy-apple-watch-se-2023-44-mm/",
        known_brands=["Apple"],
    )

    assert record.brand == "Apple"
    assert record.price == 29990
    assert record.article == "5439187"
    assert record.rating == 4.8
    assert record.reviews == 120
