from dns_watch_parser.parser.catalog import extract_catalog_records


def test_extract_catalog_records_from_dns_card():
    html = """
    <div class="catalog-product">
      <a class="catalog-product__image-link" href="/product/abc123456789abcd/smart-casy-test-watch/">
        <img alt="Смарт-часы Test Watch" data-src="https://img.test/watch.jpg">
      </a>
      <a class="catalog-product__name ui-link ui-link_black" href="/product/abc123456789abcd/smart-casy-test-watch/">
        Смарт-часы Garmin Test Watch [корпус - черный, 46 mm, Bluetooth, NFC]
      </a>
      <a class="catalog-product__rating" href="/product/abc123456789abcd/smart-casy-test-watch/?opinion">
        4.91 | 2.4k отзывов
      </a>
      <div class="product-buy__price">24 999 ₽</div>
      <span>В наличии в 221 магазине</span>
      <span>Доставим на дом за 2 часа</span>
    </div>
    """

    records = extract_catalog_records(html, known_brands=["Garmin"], source="dns", shop_id=0)

    assert len(records) == 1
    record = records[0]
    assert record.brand == "Garmin"
    assert record.price == 24999
    assert record.rating == 4.91
    assert record.reviews == 2400
    assert record.stock_status == "in_stock"
    assert record.color == "черный"
    assert record.connectivity == "Bluetooth, NFC"
