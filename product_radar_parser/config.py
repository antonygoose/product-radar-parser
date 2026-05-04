from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ParserConfig:
    group_by: str = "week"
    periods: int = 1
    top_k: int = 1
    base_url: str = "https://productradar.ru"
    raw_dir: Path = Path("data/raw")
    clean_dir: Path = Path("data/clean")
    log_dir: Path = Path("data/logs")
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 5.0
    timeout_seconds: float = 30.0
    retries: int = 2
    dry_run: bool = False
    session_cookie: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.session_cookie is not None:
            object.__setattr__(self, "session_cookie", normalize_session_cookie(self.session_cookie))

    def validate(self) -> None:
        if self.group_by not in {"week", "month", "year"}:
            raise ValueError("--group-by must be one of week, month, year")
        if self.periods < 1:
            raise ValueError("--periods must be >= 1")
        if self.top_k < 1:
            raise ValueError("--top-k must be >= 1")
        if self.min_delay_seconds < 0 or self.max_delay_seconds < self.min_delay_seconds:
            raise ValueError("delay bounds are invalid")
        if self.session_cookie is not None and not self.session_cookie.strip():
            raise ValueError("--session-cookie must not be empty when provided")


def normalize_session_cookie(value: str) -> str:
    cookie = value.strip().strip("'\"")
    if cookie.lower().startswith("cookie:"):
        cookie = cookie.split(":", 1)[1].strip()
    return cookie
