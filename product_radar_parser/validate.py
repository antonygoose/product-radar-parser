from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from .schemas import (
    FOUNDER_COLUMNS,
    FOUNDER_INTEGER_FIELDS,
    FOUNDER_REQUIRED,
    PRODUCT_COLUMNS,
    PRODUCT_INTEGER_FIELDS,
    PRODUCT_REQUIRED,
)


class ValidationError(Exception):
    """Raised when clean datasets violate the product specification."""


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_if_failed(self) -> None:
        if self.errors:
            raise ValidationError("\n".join(self.errors))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        return next(reader, [])


def _validate_columns(path: Path, expected: list[str], label: str, report: ValidationReport) -> None:
    if not path.exists():
        report.errors.append(f"{label}: missing file {path}")
        return
    actual = read_header(path)
    if actual != expected:
        report.errors.append(f"{label}: columns differ. expected={expected!r} actual={actual!r}")


def _is_empty(value: object) -> bool:
    return value is None or str(value).strip() == ""


def _validate_required(rows: list[dict[str, str]], required: list[str], label: str, report: ValidationReport) -> None:
    for i, row in enumerate(rows, start=2):
        for column in required:
            if _is_empty(row.get(column)):
                report.errors.append(f"{label}: row {i} has empty required field {column}")


def _validate_integer_fields(
    rows: list[dict[str, str]],
    integer_fields: list[str],
    label: str,
    report: ValidationReport,
    allow_empty: bool,
) -> None:
    for i, row in enumerate(rows, start=2):
        for column in integer_fields:
            value = row.get(column)
            if allow_empty and _is_empty(value):
                continue
            try:
                int(str(value))
            except (TypeError, ValueError):
                report.errors.append(f"{label}: row {i} field {column} is not an integer: {value!r}")


def _validate_unique(rows: list[dict[str, str]], column: str, label: str, report: ValidationReport) -> None:
    seen: set[str] = set()
    for i, row in enumerate(rows, start=2):
        value = row.get(column, "")
        if value in seen:
            report.errors.append(f"{label}: duplicate {column}: {value!r} at row {i}")
        seen.add(value)


def validate_rows(products: list[dict[str, object]], founders: list[dict[str, object]]) -> ValidationReport:
    product_rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in products]
    founder_rows = [{k: "" if v is None else str(v) for k, v in row.items()} for row in founders]
    report = ValidationReport()

    for i, row in enumerate(product_rows, start=1):
        if list(row.keys()) != PRODUCT_COLUMNS:
            report.errors.append(f"product row {i}: columns differ")
    for i, row in enumerate(founder_rows, start=1):
        if list(row.keys()) != FOUNDER_COLUMNS:
            report.errors.append(f"founder row {i}: columns differ")

    _validate_required(product_rows, PRODUCT_REQUIRED, "products", report)
    _validate_required(founder_rows, FOUNDER_REQUIRED, "founders", report)
    _validate_integer_fields(product_rows, PRODUCT_INTEGER_FIELDS, "products", report, allow_empty=False)
    _validate_integer_fields(founder_rows, FOUNDER_INTEGER_FIELDS, "founders", report, allow_empty=True)
    _validate_unique(product_rows, "product_id", "products", report)
    _validate_unique(product_rows, "product_url", "products", report)
    _validate_unique(founder_rows, "founder_id", "founders", report)
    _validate_unique(founder_rows, "profile_url", "founders", report)
    _validate_founder_links(product_rows, founder_rows, report)
    return report


def _validate_founder_links(
    product_rows: list[dict[str, str]],
    founder_rows: list[dict[str, str]],
    report: ValidationReport,
) -> None:
    founder_ids = {row.get("founder_id", "") for row in founder_rows}
    for i, row in enumerate(product_rows, start=2):
        founder_id = row.get("founder_id", "")
        if founder_id not in founder_ids:
            report.errors.append(f"products: row {i} founder_id does not exist in founders: {founder_id!r}")


def validate_clean_dir(clean_dir: Path) -> ValidationReport:
    product_path = clean_dir / "products.csv"
    founder_path = clean_dir / "founders.csv"
    report = ValidationReport()
    _validate_columns(product_path, PRODUCT_COLUMNS, "products", report)
    _validate_columns(founder_path, FOUNDER_COLUMNS, "founders", report)
    if report.errors:
        return report
    products = read_csv(product_path)
    founders = read_csv(founder_path)
    row_report = validate_rows(products, founders)
    report.errors.extend(row_report.errors)
    return report


def validate_acceptance_smink(products: list[dict[str, object]]) -> ValidationReport:
    report = ValidationReport()
    if len(products) != 1:
        report.errors.append(f"smink acceptance: expected exactly 1 product, got {len(products)}")
        return report
    row = products[0]
    expected = {
        "product_id": 11459,
        "founder_id": "nikatinstepan",
        "name": "Smink",
        "product_url": "https://productradar.ru/product/smink-2/",
        "votes_total": 41,
        "discussion_count": 9,
    }
    for key, expected_value in expected.items():
        if row.get(key) != expected_value:
            report.errors.append(f"smink acceptance: {key} expected {expected_value!r}, got {row.get(key)!r}")
    return report
