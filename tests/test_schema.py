import csv
from pathlib import Path

from product_radar_parser.schemas import FOUNDER_COLUMNS, PRODUCT_COLUMNS
from product_radar_parser.validate import validate_clean_dir, validate_rows


def test_reference_clean_data_matches_schema():
    report = validate_clean_dir(Path("data/clean"))
    assert report.ok, report.errors


def test_extra_product_column_fails():
    products = [{column: "x" for column in PRODUCT_COLUMNS} | {"extra": "x"}]
    founders = [{column: "x" for column in FOUNDER_COLUMNS}]
    for column in ["product_id", "votes_total", "votes_founders", "votes_users", "discussion_count"]:
        products[0][column] = "1"
    for column in ["community_rating", "founder_rating", "badge_number"]:
        founders[0][column] = "1"
    products[0]["founder_id"] = founders[0]["founder_id"]

    report = validate_rows(products, founders)
    assert not report.ok


def test_missing_required_value_fails():
    products = [{column: "x" for column in PRODUCT_COLUMNS}]
    founders = [{column: "x" for column in FOUNDER_COLUMNS}]
    for column in ["product_id", "votes_total", "votes_founders", "votes_users", "discussion_count"]:
        products[0][column] = "1"
    products[0]["name"] = ""
    products[0]["founder_id"] = founders[0]["founder_id"]

    report = validate_rows(products, founders)
    assert not report.ok
    assert any("name" in error for error in report.errors)


def test_duplicate_product_id_fails(tmp_path):
    clean_dir = tmp_path
    with (clean_dir / "products.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=PRODUCT_COLUMNS)
        writer.writeheader()
        row = {column: "" for column in PRODUCT_COLUMNS}
        row.update(
            {
                "product_id": "1",
                "founder_id": "founder",
                "name": "A",
                "description": "D",
                "product_url": "https://example.com/a",
                "published_at": "2026-04-13T12:00:00+03:00",
                "modified_at": "2026-04-13T12:00:00+03:00",
                "votes_total": "1",
                "votes_founders": "0",
                "votes_users": "1",
                "discussion_count": "0",
            }
        )
        writer.writerow(row)
        row["product_url"] = "https://example.com/b"
        writer.writerow(row)
    with (clean_dir / "founders.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FOUNDER_COLUMNS)
        writer.writeheader()
        writer.writerow({"founder_id": "founder", "name": "Founder", "profile_url": "https://example.com/u/founder", **{c: "" for c in FOUNDER_COLUMNS if c not in {"founder_id", "name", "profile_url"}}})

    report = validate_clean_dir(clean_dir)
    assert not report.ok
    assert any("duplicate product_id" in error for error in report.errors)
