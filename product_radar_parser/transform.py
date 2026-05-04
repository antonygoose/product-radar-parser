from __future__ import annotations

from .schemas import FOUNDER_COLUMNS, PRODUCT_COLUMNS


def join_pipe(values: object) -> str:
    if values is None:
        return ""
    if isinstance(values, str):
        return values
    return "|".join(str(value) for value in values if value not in (None, ""))


def product_to_row(product: dict[str, object]) -> dict[str, object]:
    about = product.get("about") if isinstance(product.get("about"), dict) else {}
    status = product.get("status") if isinstance(product.get("status"), dict) else {}
    votes = product.get("votes") if isinstance(product.get("votes"), dict) else {}
    headquarters = product.get("headquarters") if isinstance(product.get("headquarters"), dict) else {}
    categories = product.get("categories") or []
    if categories and isinstance(categories, list) and isinstance(categories[0], dict):
        category_values = [str(item.get("name", "")) for item in categories]
    else:
        category_values = categories

    row: dict[str, object] = {
        "product_id": int(product["id"]),
        "founder_id": str(product["founder_id"]),
        "name": str(product["name"]),
        "description": str(product["description"]),
        "product_url": str(product.get("canonical_url") or product.get("product_url")),
        "website_url": str(product.get("website_url") or ""),
        "published_at": str(product["published_at"]),
        "modified_at": str(product["modified_at"]),
        "application_category": str(product.get("application_category") or ""),
        "pricing": str(product.get("pricing") or ""),
        "headquarters_city": str(headquarters.get("city") or product.get("headquarters_city") or ""),
        "categories": join_pipe(category_values),
        "target_audience": str(about.get("target_audience") or product.get("target_audience") or ""),
        "problem": str(about.get("problem") or product.get("problem") or ""),
        "solution": str(about.get("solution") or product.get("solution") or ""),
        "advantages": str(about.get("advantages") or product.get("advantages") or ""),
        "additional": str(about.get("additional") or product.get("additional") or ""),
        "status_title": str(status.get("title") or product.get("status_title") or ""),
        "status_text": str(status.get("text") or product.get("status_text") or ""),
        "votes_total": int(votes.get("total", product.get("votes_total", 0))),
        "votes_founders": int(votes.get("founders", product.get("votes_founders", 0))),
        "votes_users": int(votes.get("users", product.get("votes_users", 0))),
        "discussion_count": int(product["discussion_count"]),
        "gallery_urls": join_pipe(product.get("gallery") or product.get("gallery_urls") or []),
    }
    return {column: row.get(column, "") for column in PRODUCT_COLUMNS}


def founder_to_row(profile: dict[str, object]) -> dict[str, object]:
    city = profile.get("city") if isinstance(profile.get("city"), dict) else {}
    ratings = profile.get("ratings") if isinstance(profile.get("ratings"), dict) else {}
    community = ratings.get("community") if isinstance(ratings.get("community"), dict) else {}
    founder = ratings.get("founder") if isinstance(ratings.get("founder"), dict) else {}
    badges = profile.get("badges") or []
    badge = badges[0] if badges and isinstance(badges[0], dict) else {}
    statuses = profile.get("statuses") or []
    if statuses and isinstance(statuses, list) and isinstance(statuses[0], dict):
        status_values = [str(item.get("label", "")) for item in statuses]
    else:
        status_values = statuses
    contacts = profile.get("contacts") or []
    telegram_url = ""
    if isinstance(contacts, list):
        for contact in contacts:
            if isinstance(contact, dict) and contact.get("type") == "telegram":
                telegram_url = str(contact.get("url") or "")
                break
    website = str(profile.get("website") or "")
    if not telegram_url and website.startswith("https://t.me/"):
        telegram_url = website

    row: dict[str, object] = {
        "founder_id": str(profile["username"]),
        "name": str(profile["name"]),
        "profile_url": str(profile.get("profile_url") or profile.get("canonical_url")),
        "bio": str(profile.get("bio") or profile.get("description") or ""),
        "city": str(city.get("name") or (profile.get("city") if not isinstance(profile.get("city"), dict) else "") or ""),
        "website": website,
        "telegram_url": telegram_url,
        "registered_at": str(profile.get("registered_at") or ""),
        "community_rating": "" if community.get("value") is None else int(community.get("value")),
        "founder_rating": "" if founder.get("value") is None else int(founder.get("value")),
        "badge_name": str(badge.get("name") or ""),
        "badge_level": str(badge.get("level") or ""),
        "badge_number": "" if badge.get("number") is None else int(badge.get("number")),
        "statuses": join_pipe(status_values),
    }
    return {column: row.get(column, "") for column in FOUNDER_COLUMNS}
