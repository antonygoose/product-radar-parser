PRODUCT_COLUMNS = [
    "product_id",
    "founder_id",
    "name",
    "description",
    "product_url",
    "website_url",
    "published_at",
    "modified_at",
    "application_category",
    "pricing",
    "headquarters_city",
    "categories",
    "target_audience",
    "problem",
    "solution",
    "advantages",
    "additional",
    "status_title",
    "status_text",
    "votes_total",
    "votes_founders",
    "votes_users",
    "discussion_count",
    "gallery_urls",
]

FOUNDER_COLUMNS = [
    "founder_id",
    "name",
    "profile_url",
    "bio",
    "city",
    "website",
    "telegram_url",
    "registered_at",
    "community_rating",
    "founder_rating",
    "badge_name",
    "badge_level",
    "badge_number",
    "statuses",
]

PRODUCT_REQUIRED = [
    "product_id",
    "founder_id",
    "name",
    "description",
    "product_url",
    "published_at",
    "modified_at",
    "votes_total",
    "votes_founders",
    "votes_users",
    "discussion_count",
]

FOUNDER_REQUIRED = ["founder_id", "name", "profile_url"]

PRODUCT_INTEGER_FIELDS = [
    "product_id",
    "votes_total",
    "votes_founders",
    "votes_users",
    "discussion_count",
]

FOUNDER_INTEGER_FIELDS = ["community_rating", "founder_rating", "badge_number"]
