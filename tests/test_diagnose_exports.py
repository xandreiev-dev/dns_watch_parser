from scripts.diagnose_exports import parse_recent_log_runs


def test_parse_recent_log_runs_reads_parser_exit_code(tmp_path):
    log = tmp_path / "scheduled_run.log"
    log.write_text(
        "\n".join(
            [
                "[03.09.2026 14:53:44,28] DNS parser scheduled run started",
                "Total URLs: 1508",
                "Exported rows: 1508",
                "DNS parser exited with code 0",
            ]
        ),
        encoding="utf-8",
    )

    runs = parse_recent_log_runs(log, 5)

    assert len(runs) == 1
    assert runs[0].finished_code == "0"
    assert runs[0].total_urls == "1508"
    assert runs[0].exported_rows == "1508"


def test_parse_recent_log_runs_marks_low_rows(tmp_path):
    log = tmp_path / "scheduled_run.log"
    log.write_text(
        "\n".join(
            [
                "[22.08.2026 16:09:57,30] DNS parser scheduled run started",
                "2026-08-22 16:09:57,307 ERROR dns_watch_parser.cli: Exported rows below minimum: rows=779, minimum=1000. Keeping previous XLSX untouched.",
                "Total URLs: 779",
                "Exported rows: 779",
                "DNS parser exited with code 4",
            ]
        ),
        encoding="utf-8",
    )

    runs = parse_recent_log_runs(log, 5)

    assert runs[0].finished_code == "4"
    assert runs[0].low_rows
