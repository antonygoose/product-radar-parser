from pathlib import Path

import pytest

from product_radar_parser.cli import parse_fixture
from product_radar_parser.upsert import upsert_clean
from product_radar_parser.validate import ValidationError, read_csv, validate_clean_dir


def test_upsert_is_idempotent(tmp_path):
    products, founders = parse_fixture()
    upsert_clean(tmp_path, products, founders)
    upsert_clean(tmp_path, products, founders)

    rows = read_csv(tmp_path / "products.csv")
    assert len(rows) == 1
    assert rows[0]["product_id"] == "11459"
    assert validate_clean_dir(tmp_path).ok


def test_mutable_field_updates_in_place(tmp_path):
    products, founders = parse_fixture()
    upsert_clean(tmp_path, products, founders)
    products[0]["votes_total"] = 42
    upsert_clean(tmp_path, products, founders)

    rows = read_csv(tmp_path / "products.csv")
    assert len(rows) == 1
    assert rows[0]["votes_total"] == "42"


def test_duplicate_incoming_product_id_fails(tmp_path):
    products, founders = parse_fixture()
    with pytest.raises(ValidationError):
        upsert_clean(tmp_path, products + products, founders)


def test_product_url_is_immutable(tmp_path):
    products, founders = parse_fixture()
    upsert_clean(tmp_path, products, founders)
    changed = [dict(products[0])]
    changed[0]["product_url"] = "https://productradar.ru/product/other/"

    with pytest.raises(ValidationError):
        upsert_clean(tmp_path, changed, founders)
