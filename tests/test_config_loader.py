from dns_watch_parser.config.loader import load_settings


def test_load_browser_settings(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[parser]
source = "dns"

[browser]
mode = "cdp"
cdp_url = "http://127.0.0.1:9333"
storage_state_path = "tmp/state/browser.json"

[brands]
items = ["Garmin"]

[start_urls]
urls = ["https://www.dns-shop.ru/catalog/smart-casy/"]
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config)

    assert settings.browser.mode == "cdp"
    assert settings.browser.cdp_url == "http://127.0.0.1:9333"
    assert settings.browser.storage_state_path == tmp_path / "tmp/state/browser.json"
