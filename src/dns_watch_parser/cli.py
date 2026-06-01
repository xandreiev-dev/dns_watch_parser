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

    output_path = build_output_path(settings.output.dir, settings.output.filename_prefix, args.brand or None)
    state.output_file = str(output_path)
    state_store.save(state)

    telegram_settings = TelegramRuntimeSettings.from_env(enabled_default=settings.telegram.enabled)
    notifier = TelegramNotifier(telegram_settings)
    if not args.dry_run:
        notifier.send_message(f"DNS Watch Parser started. Output: {output_path}")

    user_agents = settings.parser.user_agents or [settings.parser.user_agent]
    client = BrowserClient(
        timeout=settings.parser.request_timeout,
        user_agents=[agent for agent in user_agents if agent],
        rate_limiter=RateLimiter(settings.parser.delay_min, settings.parser.delay_max),
        retry_policy=RetryPolicy(max_retries=settings.parser.max_retries),
        use_playwright_fallback=settings.parser.use_playwright_fallback,
        headless=settings.parser.headless,
    )
    writer = StreamingXlsxWriter(output_path)
    started_at = datetime.now(timezone.utc)
    total_urls = 0

    try:
        catalog = CatalogParser(client)
        product_parser = ProductParser(
            client,
            known_brands=settings.brands,
            source=settings.parser.source,
            shop_id=settings.parser.shop_id,
            city=os.getenv("DNS_CITY", ""),
            region=os.getenv("DNS_REGION", ""),
        )

        product_urls = catalog.collect_product_urls(
            settings.start_urls,
            max_pages=settings.parser.max_pages_per_brand,
            limit=limit,
        )
        total_urls = len(product_urls)
        processed = state.processed_set

        for url in product_urls:
            if url in processed:
                continue
            try:
                record = product_parser.parse_url(url, brand_hint=args.brand)
                if args.brand and record.brand.lower() != args.brand.lower():
                    state_store.mark_processed(state, url)
                    continue
                writer.append(record)
                state_store.mark_processed(state, url)
                processed = state.processed_set
                logger.info("Processed %s", url)
            except Exception as exc:
                logger.warning("Failed to parse %s: %s", url, exc)
                state_store.mark_failed(state, url)
                if not args.dry_run:
                    notifier.send_message(f"DNS parser error for URL: {url}\n{exc}")
    finally:
        writer.close()
        client.close()

    finished_at = datetime.now(timezone.utc)
    summary = format_summary(
        started_at=started_at,
        finished_at=finished_at,
        total_urls=total_urls,
        processed=len(state.processed_urls),
        failed=len(state.failed_urls),
        exported_rows=writer.rows_written,
        output_path=output_path,
    )
    logger.info("\n%s", summary)
    if not args.dry_run:
        notifier.send_message(summary)
        notifier.send_document(output_path, caption="DNS watch parser XLSX")
    return 0
