from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(slots=True)
class TelegramRuntimeSettings:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    timeout: int = 10

    @classmethod
    def from_env(cls, enabled_default: bool = False) -> "TelegramRuntimeSettings":
        return cls(
            enabled=_env_bool("TELEGRAM_NOTIFICATIONS_ENABLED", enabled_default),
            bot_token=(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip(),
            chat_id=(os.getenv("TELEGRAM_CHAT_ID") or "").strip(),
            timeout=int(os.getenv("TELEGRAM_TIMEOUT", "10") or 10),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.bot_token and self.chat_id)


class TelegramNotifier:
    def __init__(self, settings: TelegramRuntimeSettings):
        self.settings = settings

    def send_message(self, text: str) -> bool:
        if not self.settings.enabled:
            return False
        if not self.settings.bot_token or not self.settings.chat_id:
            logger.warning("Telegram enabled but token/chat_id are not configured")
            return False
        url = f"https://api.telegram.org/bot{self.settings.bot_token}/sendMessage"
        try:
            response = requests.post(
                url,
                data={"chat_id": self.settings.chat_id, "text": text, "disable_web_page_preview": "true"},
                timeout=self.settings.timeout,
            )
            response.raise_for_status()
            return bool(response.json().get("ok"))
        except Exception as exc:
            logger.warning("Telegram message failed: %s", exc)
            return False

    def send_document(self, path: str | Path, caption: str = "") -> bool:
        if not self.settings.enabled or not self.settings.bot_token or not self.settings.chat_id:
            return False
        path = Path(path)
        if not path.exists() or path.stat().st_size > 45 * 1024 * 1024:
            return False
        url = f"https://api.telegram.org/bot{self.settings.bot_token}/sendDocument"
        try:
            with path.open("rb") as fh:
                response = requests.post(
                    url,
                    data={"chat_id": self.settings.chat_id, "caption": caption},
                    files={"document": (path.name, fh)},
                    timeout=max(self.settings.timeout, 30),
                )
            response.raise_for_status()
            return bool(response.json().get("ok"))
        except Exception as exc:
            logger.warning("Telegram document failed: %s", exc)
            return False


def format_summary(
    *,
    started_at: datetime,
    finished_at: datetime,
    total_urls: int,
    processed: int,
    failed: int,
    exported_rows: int,
    output_path: Path,
) -> str:
    duration = finished_at - started_at
    seconds = max(0, int(duration.total_seconds()))
    minutes, tail = divmod(seconds, 60)
    return "\n".join(
        [
            "DNS Watch Parser",
            f"Status: finished",
            f"Duration: {minutes} min {tail} sec",
            f"Total URLs: {total_urls}",
            f"Processed: {processed}",
            f"Failed: {failed}",
            f"Exported rows: {exported_rows}",
            f"Output: {output_path}",
        ]
    )
