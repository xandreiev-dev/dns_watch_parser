from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone

from dns_watch_parser.browser import BrowserClient, RateLimiter, RetryPolicy
from dns_watch_parser.config import load_settings
from dns_watch_parser.notifications import TelegramNotifier, TelegramRuntimeSettings, format_summary
from dns_watch_parser.parser import CatalogParser, ProductParser
from dns_watch_parser.storage import StateStore, StreamingXlsxWriter, build_output_path
from dns_watch_parser.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DNS smart watch parser")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--reset-state", action="store_true", help="Delete checkpoint before run")
    parser.add_argument("--limit", type=int, default=None, help="Limit product URLs")
    parser.add_argument("--brand", default="", help="Brand hint/filter")
    parser.add_argument("--dry-run", action="store_true", help="Small run without external integrations")
    parser.add_argument("--browser-mode", choices=["http", "playwright", "cdp"], default="", help="Override browser mode")
    parser.add_argument("--cdp-url", default="", help="Override Chrome CDP URL")
    parser.add_argument("--retry-failed", action="store_true", help="Process URLs from failed_urls checkpoint first")
    parser.add_argument("--no-telegram", action="store_true", help="Disable Telegram for this run")
    parser.add_argument("--catalog-only", action="store_true", help="Export data directly from catalog cards")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level)

    settings = load_settings(args.config)
    limit = args.limit
    if args.dry_run and limit is None:
        limit = 20

    state_store = StateStore(settings.tmp.resume_state_path)
    if args.reset_state:
        state_store.reset()
    state = state_store.load() if (args.resume or settings.parser.resume_enabled) else state_store.load().__class__()

    output_path = build_output_path(
        settings.output.dir,
        settings.output.filename_prefix,
        args.brand or None,
        include_timestamp=settings.output.include_timestamp,
    )
    state.output_file = str(output_path)
    state_store.save(state)

    user_agents = settings.parser.user_agents or [settings.parser.user_agent]
    browser_mode = args.browser_mode or settings.browser.mode
    cdp_url = args.cdp_url or settings.browser.cdp_url
    client = BrowserClient(
        timeout=settings.parser.request_timeout,
        user_agents=[agent for agent in user_agents if agent],
        rate_limiter=RateLimiter(settings.parser.delay_min, settings.parser.delay_max),
        retry_policy=RetryPolicy(max_retries=settings.parser.max_retries),
        use_playwright_fallback=settings.parser.use_playwright_fallback,
        headless=settings.parser.headless,
        browser_mode=browser_mode,
        cdp_url=cdp_url,
        storage_state_path=settings.browser.storage_state_path,
        page_wait_until=settings.browser.page_wait_until,
        page_wait_selector=settings.browser.page_wait_selector,
        extra_wait_ms=settings.browser.extra_wait_ms,
        auto_scroll=settings.browser.auto_scroll,
        scroll_steps=settings.browser.scroll_steps,
        proxy_server=settings.browser.proxy_server,
        reuse_page=settings.browser.reuse_page,
        browser_retries=settings.browser.browser_retries,
        browser_connect_timeout=settings.browser.browser_connect_timeout,
    )
    expected_cdp_url = ""
    if browser_mode == "cdp" and settings.start_urls:
        expected_cdp_url = settings.start_urls[0]
    try:
        client.check_health(expected_url=expected_cdp_url)
    except Exception as exc:
        client.close()
        logger.error("Browser preflight failed: %s", exc)
        return 2

    telegram_settings = TelegramRuntimeSettings.from_env(enabled_default=settings.telegram.enabled)
    if args.no_telegram:
        telegram_settings.enabled = False
    notifier = TelegramNotifier(telegram_settings)
    if not args.dry_run:
        notifier.send_message(f"DNS Watch Parser started. Output: {output_path}")

    writer: StreamingXlsxWriter | None = None
    started_at = datetime.now(timezone.utc)
    total_urls = 0
    error_samples: list[str] = []
    consecutive_error_key = ""
    consecutive_error_count = 0

    def ensure_writer() -> StreamingXlsxWriter:
        nonlocal writer
        if writer is None:
            writer = StreamingXlsxWriter(output_path)
        return writer

    def exported_rows() -> int:
        return writer.rows_written if writer is not None else 0

    try:
        catalog = CatalogParser(
            client,
            known_brands=settings.brands,
            source=settings.parser.source,
            shop_id=settings.parser.shop_id,
        )
        product_parser = ProductParser(
            client,
            known_brands=settings.brands,
            source=settings.parser.source,
            shop_id=settings.parser.shop_id,
            city=os.getenv("DNS_CITY", ""),
            region=os.getenv("DNS_REGION", ""),
        )

        if args.catalog_only and not args.retry_failed:
            records = catalog.collect_catalog_records(
                settings.start_urls,
                max_pages=settings.parser.max_pages_per_brand,
                limit=limit,
            )
            total_urls = len(records)
            processed = state.processed_set
            for record in records:
                if record.product_url in processed:
                    continue
                ensure_writer().append(record)
                state_store.mark_processed(state, record.product_url)
                state_store.clear_failed(state, record.product_url)
                processed = state.processed_set
                logger.info("Processed catalog card %s", record.product_url)
            product_urls = []
        elif args.retry_failed and state.failed_urls:
            product_urls = list(dict.fromkeys(state.failed_urls))
            if limit:
                product_urls = product_urls[:limit]
        else:
            product_urls = catalog.collect_product_urls(
                settings.start_urls,
                max_pages=settings.parser.max_pages_per_brand,
                limit=limit,
            )
        total_urls = total_urls or len(product_urls)
        processed = state.processed_set

        for url in product_urls:
            if url in processed:
                continue
            try:
                record = product_parser.parse_url(url, brand_hint=args.brand)
                if args.brand and record.brand.lower() != args.brand.lower():
                    state_store.mark_processed(state, url)
                    continue
                ensure_writer().append(record)
                state_store.mark_processed(state, url)
                state_store.clear_failed(state, url)
                processed = state.processed_set
                logger.info("Processed %s", url)
            except Exception as exc:
                logger.warning("Failed to parse %s: %s", url, exc)
                state_store.mark_failed(state, url, str(exc))
                if len(error_samples) < 5:
                    error_samples.append(f"{url} :: {exc}")
                error_key = _error_key(exc)
                if error_key == consecutive_error_key:
                    consecutive_error_count += 1
                else:
                    consecutive_error_key = error_key
                    consecutive_error_count = 1
                if exported_rows() == 0 and consecutive_error_count >= 3:
                    logger.error(
                        "Stopping early after %s identical startup failures: %s",
                        consecutive_error_count,
                        consecutive_error_key,
                    )
                    break
    finally:
        if writer is not None:
            writer.close()
        client.close()

    finished_at = datetime.now(timezone.utc)
    rows_written = exported_rows()
    summary = format_summary(
        started_at=started_at,
        finished_at=finished_at,
        total_urls=total_urls,
        processed=len(state.processed_urls),
        failed=len(state.failed_urls),
        exported_rows=rows_written,
        output_path=output_path,
    )
    logger.info("\n%s", summary)
    exit_code = 0
    if total_urls == 0 and rows_written == 0:
        logger.error("No records were exported. Check the CDP Chrome tab and DNS catalog loading before rerun.")
        exit_code = 3
    if not args.dry_run:
        if error_samples:
            logger.info("Error samples:\n%s", "\n".join(error_samples))
        notifier.send_message(summary)
        if rows_written > 0 and output_path.exists():
            notifier.send_document(output_path, caption="DNS watch parser XLSX")
    return exit_code


def _error_key(exc: Exception) -> str:
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    return text[:240]
