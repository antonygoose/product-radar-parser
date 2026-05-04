from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import urlparse


def extract_founder_from_json(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return dict(data["profile"])


def extract_founder_from_html(html: str, source_url: str) -> dict[str, object]:
    username = urlparse(source_url).path.strip("/").split("/")[-1]
    title = _meta(html, "og:title") or _tag_text(html, "title") or username
    name = title.replace(" - Профиль на Product Radar", "").strip()
    community_rating, founder_rating = _ratings(html)
    badge_name, badge_level, badge_number = _badge(html)
    telegram_url = _telegram_url(html)
    return {
        "username": username,
        "name": name,
        "profile_url": _meta(html, "og:url") or source_url,
        "bio": _meta(html, "og:description") or _meta(html, "description") or "",
        "city": {"name": _city(html)},
        "website": _website(html),
        "contacts": [{"type": "telegram", "url": telegram_url}] if telegram_url else [],
        "registered_at": _registered_at(html),
        "ratings": {
            "community": {"value": community_rating},
            "founder": {"value": founder_rating},
        },
        "badges": [{"name": badge_name, "level": badge_level, "number": badge_number}] if badge_name or badge_level or badge_number is not None else [],
        "statuses": [{"label": label} for label in _statuses(html)],
        "auth_contact_required": is_login_required_for_contact(html),
    }


def is_login_required_for_contact(html: str) -> bool:
    button = _search(html, r'(<a[^>]+class=["\'][^"\']*button--telegram[^"\']*["\'][^>]*>.*?</a>)') or ""
    return bool(button and ('href="/login"' in button or "auth-required" in button))


def _search(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def _search_all(text: str, pattern: str) -> list[str]:
    return [match.strip() for match in re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL)]


def _meta(html: str, key: str) -> str | None:
    return _search(html, rf'<meta[^>]+(?:property|name)=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']*)["\']')


def _tag_text(html: str, tag: str) -> str | None:
    value = _search(html, rf"<{tag}[^>]*>(.*?)</{tag}>")
    return _clean_text(value) if value else None


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _city(html: str) -> str:
    block = _search(html, r'(<div[^>]+class=["\'][^"\']*user-info__city[^"\']*["\'][^>]*>.*?</div>)')
    if not block or "Город" not in block:
        return ""
    return _tag_text(block, "a") or ""


def _website(html: str) -> str:
    return _search(html, r'class=["\'][^"\']*button--website[^"\']*["\'][^>]*href=["\']([^"\']+)["\']') or ""


def _telegram_url(html: str) -> str:
    href = _search(html, r'class=["\'][^"\']*button--telegram[^"\']*["\'][^>]*href=["\']([^"\']+)["\']') or ""
    return href if href.startswith("https://t.me/") else ""


def _registered_at(html: str) -> str:
    match = re.search(r"На Радаре с\s*(\d{2})\.(\d{2})\.(\d{4})", html)
    if not match:
        return ""
    day, month, year = match.groups()
    return f"{year}-{month}-{day}"


def _ratings(html: str) -> tuple[int | None, int | None]:
    values: dict[str, int] = {}
    blocks = _search_all(html, r'(<div[^>]+class=["\'][^"\']*user-raiting__item[^"\']*["\'][^>]*>.*?</div>)')
    for block in blocks:
        label = _tag_text_by_class(block, "span", "user-raiting__label")
        number = _tag_text_by_class(block, "span", "user-raiting__number")
        if not label or not number:
            continue
        if "сообщества" in label:
            values["community"] = int(number)
        elif "основателя" in label:
            values["founder"] = int(number)
    return values.get("community"), values.get("founder")


def _tag_text_by_class(html: str, tag: str, class_name: str) -> str:
    value = _search(html, rf'<{tag}[^>]*class=["\'][^"\']*{re.escape(class_name)}[^"\']*["\'][^>]*>(.*?)</{tag}>')
    return _clean_text(value) if value else ""


def _badge(html: str) -> tuple[str, str, int | None]:
    block = _search(html, r'(<div[^>]+class=["\'][^"\']*user-info__donator[^"\']*["\'][^>]*>.*?</div>)')
    if not block:
        return "", "", None
    title = _search(block, r'title=["\']([^"\']+)["\']') or ""
    name, level = "", ""
    if " - " in title:
        name, level = title.split(" - ", 1)
    elif title:
        name = title
    number_text = _tag_text_by_class(block, "span", "user-info__donator-number")
    number_match = re.search(r"\d+", number_text)
    return name, level, int(number_match.group(0)) if number_match else None


def _statuses(html: str) -> list[str]:
    block = _search(html, r'(<ul[^>]+class=["\'][^"\']*founder-statuses-list[^"\']*["\'][^>]*>.*?</ul>)')
    if not block:
        return []
    return [_clean_text(item) for item in _search_all(block, r"<li[^>]*>(.*?)</li>") if _clean_text(item)]
