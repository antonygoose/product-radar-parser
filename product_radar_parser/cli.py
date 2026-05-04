from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

from .config import ParserConfig
from .discovery import discover_top_products
from .extractors.founder import extract_founder_from_html, extract_founder_from_json, is_login_required_for_contact
from .extractors.product import extract_product_from_html, extract_product_from_json
from .http_client import RateLimitedHttpClient
from .logging_config import configure_logging
from .raw_store import RawStore, slug_from_url
from .transform import founder_to_row, product_to_row
from .upsert import upsert_clean
from .validate import validate_acceptance_smink, validate_clean_dir, validate_rows


class RawDefaultsHelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Show defaults while preserving example formatting."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="product-radar-parser",
        description="Collect Product Radar products into data/clean CSV files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser(
        "collect",
        formatter_class=RawDefaultsHelpFormatter,
        description="Fetch leaderboards, product pages, and founder pages, then upsert clean CSV outputs.",
        epilog=textwrap.dedent(
            """\
            Examples:
              python3 -m product_radar_parser.cli collect --group-by week --periods 1 --top-k 1
              python3 -m product_radar_parser.cli collect --group-by week --periods 1 --top-k 1 --dry-run
              python3 -m product_radar_parser.cli collect --group-by week --periods 1 --top-k 1 --session-cookie 'wordpress_logged_in_xxx=abc; other_cookie=def'

            --session-cookie expects the exact Cookie header value from an active Product Radar session.
            Do not pass a full "Cookie:" header line; pass only the value after "Cookie:".
            """
        ),
    )
    collect.add_argument("--group-by", choices=["week", "month", "year"], default="week", help="Leaderboard period type to collect.")
    collect.add_argument("--periods", type=int, default=1, help="Number of leaderboard periods to collect.")
    collect.add_argument("--weeks", type=int, help="Alias for --periods when --group-by week.")
    collect.add_argument("--top-k", type=int, default=1, help="Number of top products to collect from each period.")
    collect.add_argument("--base-url", default="https://productradar.ru", help="Product Radar base URL.")
    collect.add_argument("--raw-dir", type=Path, default=Path("data/raw"), help="Directory for fetched raw HTML and metadata.")
    collect.add_argument("--clean-dir", type=Path, default=Path("data/clean"), help="Directory for products.csv and founders.csv.")
    collect.add_argument("--min-delay-seconds", type=float, default=2.0, help="Minimum delay between HTTP requests.")
    collect.add_argument("--max-delay-seconds", type=float, default=5.0, help="Maximum delay between HTTP requests.")
    collect.add_argument("--timeout-seconds", type=float, default=30.0, help="HTTP request timeout.")
    collect.add_argument("--dry-run", action="store_true", help="Fetch, parse, and validate without writing clean CSV files.")
    collect.add_argument("--fixture", action="store_true", help="Parse stored Smink fixture without network requests.")
    collect.add_argument(
        "--session-cookie",
        "--cookie-token",
        dest="session_cookie",
        metavar="COOKIE_VALUE",
        help="Exact Cookie header value for an active Product Radar session, e.g. 'wordpress_logged_in_xxx=abc; other_cookie=def'.",
    )

    validate = subparsers.add_parser(
        "validate",
        formatter_class=RawDefaultsHelpFormatter,
        description="Validate existing clean CSV files.",
    )
    validate.add_argument("--clean-dir", type=Path, default=Path("data/clean"), help="Directory containing products.csv and founders.csv.")
    parse_fixture = subparsers.add_parser(
        "parse-fixture",
        formatter_class=RawDefaultsHelpFormatter,
        description="Parse the stored Smink fixture and run fixture acceptance checks.",
    )
    parse_fixture.add_argument("--clean-dir", type=Path, default=Path("data/clean"), help="Unused compatibility option.")

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return _validate_command(args.clean_dir)
        if args.command == "parse-fixture":
            products, founders = parse_fixture()
            report = validate_rows(products, founders)
            report.errors.extend(validate_acceptance_smink(products).errors)
            report.raise_if_failed()
            print("fixture acceptance passed: 1 product, 1 founder")
            return 0
        return _collect_command(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _collect_command(args: argparse.Namespace) -> int:
    periods = args.weeks if args.weeks is not None else args.periods
    config = ParserConfig(
        group_by=args.group_by,
        periods=periods,
        top_k=args.top_k,
        base_url=args.base_url,
        raw_dir=args.raw_dir,
        clean_dir=args.clean_dir,
        min_delay_seconds=args.min_delay_seconds,
        max_delay_seconds=args.max_delay_seconds,
        timeout_seconds=args.timeout_seconds,
        dry_run=args.dry_run,
        session_cookie=args.session_cookie,
    )
    config.validate()
    logger = configure_logging(Path("data/logs"))

    auth_contact_summary: dict[str, int] | None = None
    if args.fixture:
        products, founders = parse_fixture()
    else:
        products, founders, auth_contact_summary = collect_live(config, logger)

    report = validate_rows(products, founders)
    if args.fixture:
        report.errors.extend(validate_acceptance_smink(products).errors)
    report.raise_if_failed()
    if not config.dry_run:
        upsert_clean(config.clean_dir, products, founders)
        validate_clean_dir(config.clean_dir).raise_if_failed()
    summary = f"collected products={len(products)} founders={len(founders)} dry_run={config.dry_run}"
    if auth_contact_summary is not None and config.session_cookie:
        summary += (
            f" auth_telegram_visible={auth_contact_summary['telegram_visible']}"
            f" auth_contact_login_required={auth_contact_summary['login_required']}"
        )
    print(summary)
    return 0


def _validate_command(clean_dir: Path) -> int:
    report = validate_clean_dir(clean_dir)
    report.raise_if_failed()
    print("validation passed")
    return 0


def parse_fixture() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    product, _profile_url = extract_product_from_json(Path("data/raw/smink-2.json"))
    founder = extract_founder_from_json(Path("data/raw/founder-nikatinstepan.json"))
    return [product_to_row(product)], [founder_to_row(founder)]


def collect_live(config: ParserConfig, logger) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    client = RateLimitedHttpClient(config)
    raw_store = RawStore(config.raw_dir)
    candidates = discover_top_products(config, client, raw_store)
    products: list[dict[str, object]] = []
    founder_urls: dict[str, str] = {}

    for candidate in candidates:
        try:
            result = client.get(candidate.product_url)
            html_path = raw_store.save_product_html(result)
            if result.status_code >= 400:
                raw_store.log_event({"stage": "product_fetch", "url": candidate.product_url, "status": result.status_code, "skipped": True})
                continue
            product, founder_url = extract_product_from_html(html_path.read_text(encoding="utf-8"), candidate.product_url)
            if candidate.product_id is not None:
                product["id"] = candidate.product_id
            if candidate.votes_total is not None:
                product["votes"] = {"total": candidate.votes_total, "founders": 0, "users": candidate.votes_total}
            if candidate.discussion_count is not None:
                product["discussion_count"] = candidate.discussion_count
            row = product_to_row(product)
            products.append(row)
            if founder_url:
                founder_urls[str(row["founder_id"])] = founder_url
        except Exception as exc:
            logger.exception("skipping product %s: %s", candidate.product_url, type(exc).__name__)
            raw_store.log_event({"stage": "product_parse", "url": candidate.product_url, "error": type(exc).__name__, "skipped": True})

    founders: list[dict[str, object]] = []
    auth_contact_summary = {"telegram_visible": 0, "login_required": 0}
    for founder_id, founder_url in founder_urls.items():
        try:
            result = client.get(founder_url)
            html_path = raw_store.save_founder_html(result)
            if result.status_code >= 400:
                raw_store.log_event({"stage": "founder_fetch", "url": founder_url, "status": result.status_code, "skipped": True})
                continue
            html = html_path.read_text(encoding="utf-8")
            if is_login_required_for_contact(html):
                auth_contact_summary["login_required"] += 1
            profile = extract_founder_from_html(html, founder_url)
            profile["username"] = founder_id
            row = founder_to_row(profile)
            if row["telegram_url"]:
                auth_contact_summary["telegram_visible"] += 1
            founders.append(row)
        except Exception as exc:
            logger.exception("skipping founder %s: %s", founder_url, type(exc).__name__)
            raw_store.log_event({"stage": "founder_parse", "url": founder_url, "error": type(exc).__name__, "skipped": True})

    return products, founders, auth_contact_summary


if __name__ == "__main__":
    raise SystemExit(main())
