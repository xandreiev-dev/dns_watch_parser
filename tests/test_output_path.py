from dns_watch_parser.storage.exports import build_output_path


def test_build_output_path_uses_timestamp_by_default(tmp_path):
    path = build_output_path(tmp_path, "dns_watch")

    assert path.name.startswith("dns_watch_")
    assert path.name.endswith(".xlsx")
    assert len(path.stem) > len("dns_watch_2026-06-12")


def test_build_output_path_can_use_date_only(tmp_path):
    path = build_output_path(tmp_path, "dns_watch", include_timestamp=False)

    assert path.name.startswith("dns_watch_")
    assert path.name.endswith(".xlsx")
    assert len(path.stem) == len("dns_watch_20260615")
