from pathlib import Path

from product_radar_parser.cli import parse_fixture
from product_radar_parser.extractors.founder import extract_founder_from_json
from product_radar_parser.extractors.founder import extract_founder_from_html
from product_radar_parser.extractors.product import extract_product_from_json
from product_radar_parser.extractors.product import extract_product_from_html
from product_radar_parser.transform import founder_to_row, product_to_row
from product_radar_parser.validate import validate_acceptance_smink, validate_rows


def test_smink_fixture_product_acceptance():
    product, founder_url = extract_product_from_json(Path("data/raw/smink-2.json"))
    row = product_to_row(product)

    assert founder_url == "https://productradar.ru/user/nikatinstepan/"
    assert validate_acceptance_smink([row]).ok
    assert row["product_id"] == 11459
    assert row["founder_id"] == "nikatinstepan"
    assert row["name"] == "Smink"
    assert row["votes_total"] == 41
    assert row["discussion_count"] == 9


def test_smink_fixture_founder_links():
    founder = extract_founder_from_json(Path("data/raw/founder-nikatinstepan.json"))
    founder_row = founder_to_row(founder)
    products, founders = parse_fixture()
    report = validate_rows(products, founders)

    assert report.ok
    assert founder_row["founder_id"] == "nikatinstepan"
    assert founder_row["profile_url"] == "https://productradar.ru/user/nikatinstepan/"


def test_live_smink_html_prefers_author_over_voters_when_available():
    html_path = Path("data/raw/products/smink-2.html")
    if not html_path.exists():
        return

    product, founder_url = extract_product_from_html(html_path.read_text(encoding="utf-8"), "https://productradar.ru/product/smink-2/")

    assert founder_url == "https://productradar.ru/user/nikatinstepan/"
    assert product["founder_id"] == "nikatinstepan"


def test_live_smink_html_extracts_product_detail_fields_when_available():
    html_path = Path("data/raw/products/smink-2.html")
    if not html_path.exists():
        return

    product, _founder_url = extract_product_from_html(html_path.read_text(encoding="utf-8"), "https://productradar.ru/product/smink-2/")
    row = product_to_row(product)

    assert row["application_category"] == "CRM"
    assert row["pricing"] == "Платно (триал)"
    assert row["headquarters_city"] == "Москва"
    assert "CRM" in row["categories"]
    assert row["target_audience"]
    assert row["problem"]
    assert row["solution"]
    assert row["advantages"]
    assert row["additional"]
    assert row["status_title"]
    assert row["status_text"]
    assert row["gallery_urls"]


def test_live_founder_html_extracts_profile_fields_when_available():
    html_path = Path("data/raw/founders/nikatinstepan.html")
    if not html_path.exists():
        return

    founder = extract_founder_from_html(html_path.read_text(encoding="utf-8"), "https://productradar.ru/user/nikatinstepan/")
    row = founder_to_row(founder)

    assert row["city"] == "Москва"
    assert row["website"] == "https://smink.ru"
    assert row["registered_at"] == "2026-03-23"
    assert row["community_rating"]
    assert row["founder_rating"]
    assert row["badge_name"] == "Друг Радара"
    assert row["badge_level"] == "Ангел"
    assert row["badge_number"] == 411
    assert row["statuses"] == "🙌 Поддерживаю проекты"


def test_founder_city_dict_without_name_serializes_empty_string():
    row = founder_to_row(
        {
            "username": "founder",
            "name": "Founder",
            "profile_url": "https://productradar.ru/user/founder/",
            "city": {"name": ""},
            "website": "https://t.me/example",
            "ratings": {},
            "badges": [],
            "statuses": [],
            "contacts": [],
        }
    )

    assert row["city"] == ""
    assert row["telegram_url"] == "https://t.me/example"
