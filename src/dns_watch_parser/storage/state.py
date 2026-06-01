from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dns_watch_parser.utils.dates import utc_now_iso


@dataclass(slots=True)
class ParserState:
    processed_urls: list[str] = field(default_factory=list)
    failed_urls: list[str] = field(default_factory=list)
    current_brand: str = ""
    current_page: int = 0
    started_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    output_file: str = ""

    @property
    def processed_set(self) -> set[str]:
        return set(self.processed_urls)


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> ParserState:
        if not self.path.exists():
            return ParserState()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return ParserState(**data)

    def save(self, state: ParserState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state.updated_at = utc_now_iso()
        self.path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    def reset(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def mark_processed(self, state: ParserState, url: str) -> None:
        if url not in state.processed_set:
            state.processed_urls.append(url)
        self.save(state)

    def mark_failed(self, state: ParserState, url: str) -> None:
        if url not in set(state.failed_urls):
            state.failed_urls.append(url)
        self.save(state)
