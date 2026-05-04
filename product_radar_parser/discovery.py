from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin

from .config import ParserConfig
from .http_client import RateLimitedHttpClient
from .raw_store import RawStore


@dataclass(frozen=True)
class ProductCandidate:
    product_url: str
    product_id: int | None = None
    votes_total: int | None = None
    discussion_count: int | None = None
    period: str = ""


def discover_top_products(config: ParserConfig, client: RateLimitedHttpClient, raw_store: RawStore) -> list[ProductCandidate]:
    initial_url = f"{config.base_url.rstrip('/')}/?groupby={config.group_by}"
    result = client.get(initial_url)
    raw_store.save_leaderboard(f"{config.group_by}-initial", result)
    if result.status_code >= 400:
        raise RuntimeError(f"leaderboard fetch failed with status {result.status_code}: {initial_url}")

    candidates = parse_leaderboard_html(result.text, config.base_url, config.top_k)
    next_period, next_page = _next_markers(result.text)
    seen_markers: set[tuple[str, str]] = set()
    while _needs_more(candidates, config.periods, config.top_k) and next_period != "" and next_page != "":
        marker = (next_period, next_page)
        if marker in seen_markers:
            break
        seen_markers.add(marker)
        previous_periods = _ordered_periods(candidates)
        previous_last_period = previous_periods[-1] if previous_periods else ""
        ajax_url = f"{config.base_url.rstrip('/')}/wp-admin/admin-ajax.php"
        ajax = client.post_form(
            ajax_url,
            {
                "action": "more-handler",
                "next_period": next_period,
                "next_page": next_page,
                "group_by": config.group_by,
            },
        )
        raw_store.save_leaderboard(f"{config.group_by}-{next_period}-{next_page}", ajax)
        if ajax.status_code >= 400:
            raise RuntimeError(f"leaderboard ajax failed with status {ajax.status_code}: {ajax_url}")
        payload = json.loads(ajax.text)
        html = str(payload.get("html") or "")
        page_candidates = parse_leaderboard_html(html, config.base_url, config.top_k)
        if page_candidates and all(not candidate.period for candidate in page_candidates):
            page_candidates = [
                ProductCandidate(
                    candidate.product_url,
                    candidate.product_id,
                    candidate.votes_total,
                    candidate.discussion_count,
                    previous_last_period,
                )
                for candidate in page_candidates
            ]
        candidates.extend(page_candidates)
        next_period = _payload_marker(payload, "next_period")
        next_page = _payload_marker(payload, "next_page")

    return _dedupe(candidates, config.periods, config.top_k)


def parse_leaderboard_html(html: str, base_url: str, top_k: int) -> list[ProductCandidate]:
    chunks = re.split(r'(<[^>]*class=["\'][^"\']*products__period[^"\']*["\'][^>]*>.*?</[^>]+>)', html, flags=re.I | re.S)
    if len(chunks) == 1:
        return _parse_cards(html, base_url, top_k, "")

    candidates: list[ProductCandidate] = []
    current_period = ""
    for chunk in chunks:
        if "products__period" in chunk:
            current_period = _clean_text(chunk)
            continue
        if current_period:
            candidates.extend(_parse_cards(chunk, base_url, top_k, current_period))
    return candidates


def _parse_cards(html: str, base_url: str, top_k: int, period: str) -> list[ProductCandidate]:
    cards = re.findall(
        r'(<[^>]*class=["\'][^"\']*(?:products__item|card)[^"\']*(?:products__item|card)?[^"\']*["\'][^>]*>.*?)(?=<[^>]*class=["\'][^"\']*(?:products__item|products__period)[^"\']*["\']|$)',
        html,
        flags=re.I | re.S,
    )
    if not cards:
        cards = re.findall(r'(<article\b.*?</article>)', html, flags=re.I | re.S)
    found: list[ProductCandidate] = []
    for card in cards:
        href = _search(card, r'class=["\'][^"\']*product-bg-link[^"\']*["\'][^>]*href=["\']([^"\']+)["\']')
        href = href or _search(card, r'href=["\']([^"\']*/product/[^"\']+/)["\']')
        if not href:
            continue
        product_id = _optional_int(_search(card, r'class=["\'][^"\']*upvote[^"\']*["\'][^>]*data-id=["\'](\d+)["\']'))
        votes_total = _optional_int(_search(card, r'class=["\'][^"\']*upvote[^"\']*["\'][^>]*data-votes=["\'](\d+)["\']'))
        comments = _extract_comments_count(card)
        found.append(ProductCandidate(urljoin(base_url, href), product_id, votes_total, comments, period))
        if len(found) >= top_k:
            break
    return found


def _dedupe(candidates: list[ProductCandidate], periods: int, top_k: int) -> list[ProductCandidate]:
    seen: set[str] = set()
    selected: list[ProductCandidate] = []
    period_counts: dict[str, int] = {}
    for candidate in candidates:
        if len(period_counts) >= periods and candidate.period not in period_counts:
            continue
        count = period_counts.get(candidate.period, 0)
        if count >= top_k:
            continue
        if candidate.product_url in seen:
            continue
        selected.append(candidate)
        seen.add(candidate.product_url)
        period_counts[candidate.period] = count + 1
    return selected


def _periods(candidates: list[ProductCandidate]) -> set[str]:
    return {candidate.period for candidate in candidates if candidate.period}


def _ordered_periods(candidates: list[ProductCandidate]) -> list[str]:
    periods: list[str] = []
    for candidate in candidates:
        if candidate.period and candidate.period not in periods:
            periods.append(candidate.period)
    return periods


def _needs_more(candidates: list[ProductCandidate], periods: int, top_k: int) -> bool:
    selected = _dedupe(candidates, periods, top_k)
    return len(_ordered_periods(selected)) < periods


def _next_markers(html: str) -> tuple[str, str]:
    return (
        _search(html, r'data-next-period=["\']([^"\']+)["\']')
        or _search(html, r'"nextPeriod"\s*:\s*"?([^",}]+)"?')
        or "",
        _search(html, r'data-next-page=["\']([^"\']+)["\']')
        or _search(html, r'"nextPage"\s*:\s*"?([^",}]+)"?')
        or "",
    )


def _payload_marker(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    return "" if value is None else str(value)


def _search(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.I | re.S)
    return match.group(1).strip() if match else None


def _optional_int(value: str | None) -> int | None:
    return int(value) if value not in (None, "") else None


def _extract_comments_count(card: str) -> int | None:
    anchor = _search(card, r'(<a[^>]*class=["\'][^"\']*card__comments[^"\']*["\'][^>]*>.*?</a>)')
    if not anchor:
        return None
    aria = _search(anchor, r'aria-label=["\'][^"\']*?(\d+)[^"\']*["\']')
    if aria:
        return int(aria)
    text = _clean_text(anchor)
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def _clean_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()
