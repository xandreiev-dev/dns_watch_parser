from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar


T = TypeVar("T")


class RetryableHttpError(RuntimeError):
    def __init__(self, status_code: int, message: str = ""):
        super().__init__(message or f"Retryable HTTP status: {status_code}")
        self.status_code = status_code


@dataclass(slots=True)
class RetryPolicy:
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    retry_statuses: tuple[int, ...] = (401, 403, 408, 425, 429, 500, 502, 503, 504)

    def run(self, fn: Callable[[], T]) -> T:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return fn()
            except Exception as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                delay = min(self.max_delay, self.base_delay * (2**attempt))
                time.sleep(delay + random.uniform(0, 0.75))
        assert last_exc is not None
        raise last_exc
