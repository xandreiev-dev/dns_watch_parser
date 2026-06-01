from __future__ import annotations

import random
import time
from dataclasses import dataclass


@dataclass(slots=True)
class RateLimiter:
    delay_min: float = 2
    delay_max: float = 6

    def wait(self) -> None:
        upper = max(self.delay_min, self.delay_max)
        time.sleep(random.uniform(self.delay_min, upper))
