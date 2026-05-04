from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .http_client import FetchResult


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    slug = path.split("/")[-1] if path else "index"
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in slug)


class RawStore:
    def __init__(self, raw_dir: Path):
        self.raw_dir = raw_dir
        self.products_dir = raw_dir / "products"
        self.founders_dir = raw_dir / "founders"
        self.runs_dir = raw_dir / "runs"
        for directory in [self.products_dir, self.founders_dir, self.runs_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.events_path = self.runs_dir / f"{self.run_id}.jsonl"

    def save_product_html(self, result: FetchResult) -> Path:
        return self._save_html(self.products_dir, result)

    def save_founder_html(self, result: FetchResult) -> Path:
        return self._save_html(self.founders_dir, result)

    def save_leaderboard(self, name: str, result: FetchResult) -> Path:
        return self._save_html(self.raw_dir / "leaderboards", result, stem=name)

    def log_event(self, event: dict[str, object]) -> None:
        safe_event = dict(event)
        safe_event.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(safe_event, ensure_ascii=False, sort_keys=True) + "\n")

    def _save_html(self, directory: Path, result: FetchResult, stem: str | None = None) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        html_path = directory / f"{stem or slug_from_url(result.url)}.html"
        html_path.write_text(result.text, encoding="utf-8")
        metadata = {
            "source_url": result.url,
            "fetched_at": result.fetched_at,
            "status_code": result.status_code,
            "content_sha256": result.content_sha256,
            "html_path": str(html_path),
        }
        html_path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return html_path
