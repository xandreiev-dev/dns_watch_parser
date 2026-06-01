from dns_watch_parser.storage.state import StateStore


def test_state_persists_processed_urls(tmp_path):
    store = StateStore(tmp_path / "state.json")
    state = store.load()
    store.mark_processed(state, "https://example.test/product/1/")

    loaded = store.load()

    assert loaded.processed_urls == ["https://example.test/product/1/"]
    assert "https://example.test/product/1/" in loaded.processed_set
