from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from .schemas import FOUNDER_COLUMNS, PRODUCT_COLUMNS
from .validate import ValidationError, read_csv, validate_rows


def upsert_clean(clean_dir: Path, products: list[dict[str, object]], founders: list[dict[str, object]]) -> None:
    clean_dir.mkdir(parents=True, exist_ok=True)
    product_path = clean_dir / "products.csv"
    founder_path = clean_dir / "founders.csv"

    existing_products = read_csv(product_path) if product_path.exists() else []
    existing_founders = read_csv(founder_path) if founder_path.exists() else []
    existing_report = validate_rows(_ordered(existing_products, PRODUCT_COLUMNS), _ordered(existing_founders, FOUNDER_COLUMNS))
    existing_report.raise_if_failed()

    merged_products = _merge_products(existing_products, products)
    merged_founders = _merge_by_id(existing_founders, founders, "founder_id", FOUNDER_COLUMNS, "founders")

    report = validate_rows(merged_products, merged_founders)
    report.raise_if_failed()
    _write_csv_atomic(product_path, PRODUCT_COLUMNS, merged_products)
    _write_csv_atomic(founder_path, FOUNDER_COLUMNS, merged_founders)


def _merge_products(existing: list[dict[str, object]], incoming: list[dict[str, object]]) -> list[dict[str, object]]:
    _reject_duplicate_batch(incoming, "product_id", "products")
    by_id = {str(row["product_id"]): dict(row) for row in existing}
    for row in incoming:
        product_id = str(row["product_id"])
        if product_id in by_id and str(by_id[product_id]["product_url"]) != str(row["product_url"]):
            raise ValidationError(f"products: product_url is immutable for product_id={product_id}")
        by_id[product_id] = {column: row.get(column, "") for column in PRODUCT_COLUMNS}
    return list(by_id.values())


def _merge_by_id(
    existing: list[dict[str, object]],
    incoming: list[dict[str, object]],
    id_column: str,
    columns: list[str],
    label: str,
) -> list[dict[str, object]]:
    _reject_duplicate_batch(incoming, id_column, label)
    by_id = {str(row[id_column]): dict(row) for row in existing}
    for row in incoming:
        by_id[str(row[id_column])] = {column: row.get(column, "") for column in columns}
    return list(by_id.values())


def _reject_duplicate_batch(rows: list[dict[str, object]], column: str, label: str) -> None:
    seen: set[str] = set()
    for row in rows:
        value = str(row.get(column, ""))
        if value in seen:
            raise ValidationError(f"{label}: duplicate incoming {column}: {value!r}")
        seen.add(value)


def _ordered(rows: list[dict[str, object]], columns: list[str]) -> list[dict[str, object]]:
    return [{column: row.get(column, "") for column in columns} for row in rows]


def _write_csv_atomic(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="raise")
            writer.writeheader()
            writer.writerows(_ordered(rows, columns))
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
