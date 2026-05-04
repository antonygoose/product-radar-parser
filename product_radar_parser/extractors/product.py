from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse


def founder_id_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) >= 2 and parts[-2] == "user":
        return parts[-1]
    return parts[-1] if parts else ""


def extract_product_from_json(path: Path) -> tuple[dict[str, object], str | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    product = dict(data["product"])
    founder = data.get("founder") or {}
    profile_url = founder.get("profile_url")
    if not product.get("founder_id") and profile_url:
        product["founder_id"] = founder_id_from_url(str(profile_url))
    return product, str(profile_url) if profile_url else None


def extract_product_from_html(html: str, source_url: str) -> tuple[dict[str, object], str | None]:
    """Extract required fields from a public product HTML page.

    This conservative fallback targets stable metadata and embedded attributes.
    If a required field is unavailable, the caller should log and skip the page.
    """
    json_ld = _product_json_ld(html)
    title = str(json_ld.get("name") or _tag_text(html, "h1") or _meta(html, "og:title") or _tag_text(html, "title") or "")
    description = _clean_text(str(json_ld.get("description") or _tag_text_by_class(html, "p", "product__description") or _meta(html, "description") or _meta(html, "og:description") or ""))
    canonical = str(json_ld.get("url") or _link(html, "canonical") or source_url)
    product_id = _first_int(_search(html, r'data-id=["\'](\d+)["\']'))
    votes_total = _first_int(_search(html, r'data-votes=["\'](\d+)["\']'), default=0)
    votes_founders, votes_users = _votes_split(html, votes_total)
    comments = _discussion_count(html)
    founder_url = (
        _meta(html, "article:author")
        or _search(html, r'class=["\'][^"\']*contributors__profile-link[^"\']*["\'][^>]*href=["\']([^"\']+)["\']')
        or _person_url(json_ld.get("author"))
        or _person_url(json_ld.get("creator"))
    )
    if founder_url and not founder_url.endswith("/"):
        founder_url = founder_url + "/"
    about = _about_fields(html)
    status_title, status_text = _status_fields(html)
    product = {
        "id": product_id,
        "founder_id": founder_id_from_url(founder_url or ""),
        "name": title.split("—", 1)[0].strip(),
        "description": description or title or "",
        "canonical_url": canonical,
        "website_url": _website_url(html),
        "published_at": str(json_ld.get("datePublished") or _meta(html, "article:published_time") or _datetime(html)),
        "modified_at": str(json_ld.get("dateModified") or _meta(html, "article:modified_time") or _datetime(html)),
        "application_category": str(json_ld.get("applicationCategory") or ""),
        "pricing": _tag_text_by_class(html, "span", "product__pricing"),
        "headquarters": {"city": _headquarters_city(html)},
        "about": about,
        "status": {"title": status_title, "text": status_text},
        "votes": {"total": votes_total, "founders": votes_founders, "users": votes_users},
        "discussion_count": comments,
        "categories": [{"name": name} for name in _category_names(html)],
        "gallery": _gallery_urls(html, json_ld),
    }
    return product, founder_url


def _search(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def _search_all(text: str, pattern: str) -> list[str]:
    return [match.strip() for match in re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL)]


def _first_int(value: str | None, default: int | None = None) -> int:
    if value is None:
        if default is None:
            raise ValueError("required integer was not found")
        return default
    return int(value)


def _meta(html: str, key: str) -> str | None:
    return _search(html, rf'<meta[^>]+(?:property|name)=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']*)["\']')


def _link(html: str, rel: str) -> str | None:
    return _search(html, rf'<link[^>]+rel=["\']{re.escape(rel)}["\'][^>]+href=["\']([^"\']*)["\']')


def _tag_text(html: str, tag: str) -> str | None:
    value = _search(html, rf"<{tag}[^>]*>(.*?)</{tag}>")
    return _clean_text(value) if value else None


def _datetime(html: str) -> str:
    return _search(html, r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+\-]\d{2}:\d{2})') or ""


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _product_json_ld(html: str) -> dict[str, object]:
    scripts = _search_all(html, r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>')
    for script in scripts:
        try:
            data = json.loads(unescape(script))
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") in {"WebApplication", "SoftwareApplication"}:
                return item
    return {}


def _person_url(value: object) -> str | None:
    if isinstance(value, dict) and value.get("url"):
        return str(value["url"])
    return None


def _tag_text_by_class(html: str, tag: str, class_name: str) -> str:
    value = _search(html, rf'<{tag}[^>]*class=["\'][^"\']*{re.escape(class_name)}[^"\']*["\'][^>]*>(.*?)</{tag}>')
    return _clean_text(value) if value else ""


def _website_url(html: str) -> str:
    return (
        _search(html, r'class=["\'][^"\']*product__website-button[^"\']*["\'][^>]*href=["\']([^"\']+)["\']')
        or _search(html, r'href=["\']([^"\']+)["\'][^>]*>\s*(?:Перейти|Сайт)')
        or ""
    )


def _about_fields(html: str) -> dict[str, str]:
    mapping = {
        "Для кого": "target_audience",
        "Проблема": "problem",
        "Решение": "solution",
        "Преимущества": "advantages",
        "Дополнительно": "additional",
    }
    fields: dict[str, str] = {}
    blocks = _search_all(html, r'(<div[^>]+class=["\'][^"\']*product__about-item(?![^"\']*product__about-item--status)[^"\']*["\'][^>]*>.*?</div>)')
    for block in blocks:
        label = _tag_text(block, "h3")
        text = _tag_text(block, "p")
        if not label or not text:
            continue
        normalized = label.rstrip(":")
        key = mapping.get(normalized)
        if key:
            fields[key] = text
    return fields


def _status_fields(html: str) -> tuple[str, str]:
    block = _search(html, r'(<div[^>]+class=["\'][^"\']*product__about-item--status[^"\']*["\'][^>]*>.*?</div>\s*</div>)')
    if not block:
        return "", ""
    return (
        _tag_text_by_class(block, "p", "product-status-item__title"),
        _tag_text_by_class(block, "p", "product-status-item__text"),
    )


def _headquarters_city(html: str) -> str:
    block = _search(html, r'(<div[^>]+class=["\'][^"\']*user-info__city[^"\']*["\'][^>]*>.*?</div>)')
    if not block or "Штаб-квартира" not in block:
        return ""
    return _tag_text(block, "a") or ""


def _category_names(html: str) -> list[str]:
    block = _search(html, r'(<ul[^>]+class=["\'][^"\']*product__categories[^"\']*["\'][^>]*>.*?</ul>)')
    if not block:
        return []
    return [_clean_text(value) for value in _search_all(block, r"<a[^>]*>(.*?)</a>") if _clean_text(value)]


def _gallery_urls(html: str, json_ld: dict[str, object]) -> list[str]:
    urls = _search_all(html, r'class=["\'][^"\']*product-gallery__item[^"\']*["\'][^>]*data-src=["\']([^"\']+)["\']')
    screenshot = json_ld.get("screenshot")
    if not urls and isinstance(screenshot, list):
        urls = [str(item) for item in screenshot if item]
    seen: set[str] = set()
    unique = []
    for url in urls:
        absolute = urljoin("https://productradar.ru", url)
        if absolute not in seen:
            unique.append(absolute)
            seen.add(absolute)
    return unique


def _votes_split(html: str, total: int) -> tuple[int, int]:
    details = _search(html, r'(<details[^>]+class=["\'][^"\']*voters__details[^"\']*["\'][^>]*>.*?</details>)')
    if not details:
        return 0, total
    founders = _first_int(_search(details, r"Основатели:\s*<b>(\d+)</b>"), default=0)
    users = _first_int(_search(details, r"Пользователи:\s*<b>(\d+)</b>"), default=max(total - founders, 0))
    return founders, users


def _discussion_count(html: str) -> int:
    comment_ids = set(re.findall(r"id=['\"]wpd-comm-(\d+)_", html))
    if comment_ids:
        return len(comment_ids)
    return _first_int(_search(html, r'class=["\'][^"\']*card__comments[^"\']*["\'][^>]*aria-label=["\'][^"\']*?(\d+)'), default=0)
