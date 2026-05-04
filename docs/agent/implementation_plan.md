# Product Radar Parser Implementation Plan

## Source Documents

Authoritative inputs:

- `AGENTS.md`
- `docs/spec/product_spec.md`
- `docs/spec/acceptance_tests.md`
- `docs/agent/architecture.md`

The implementation must satisfy the acceptance tests before it is considered
done. Where live Product Radar values differ from the frozen Smink fixture, use
stored fixture data for deterministic acceptance tests and live data for current
schema/invariant checks.

## Completion Criteria

The implementation is complete when:

- `python -m product_radar_parser.cli collect --group-by week --periods 1 --top-k 1`
  can collect the current top product for the latest week;
- `collect` can also discover public top products with `--group-by month` and
  `--group-by year`;
- fixture acceptance for `https://productradar.ru/product/smink-2/` passes with
  `product_id=11459`, `founder_id=nikatinstepan`, `votes_total=41`, and
  `discussion_count=9`;
- `data/clean/products.csv` and `data/clean/founders.csv` match the exact Data
  Model schemas;
- all required fields are non-null;
- integer fields are integers;
- `categories` and `gallery_urls` are strings using `|` separators;
- running the same configuration twice creates no duplicate products or founders;
- per-page failures are logged and do not stop the full run;
- no credentials or tokens are stored, printed, or committed.

## Phase 0.5: Public API and Contact Discovery

Status from live discovery on `2026-04-14`:

- `https://productradar.ru/wp-json/` is available and confirms WordPress.
- Custom namespaces exist: `productradar/v1` and `radar/v1`.
- `GET /wp-json/radar/v1/products/{cat_id}` exists but returned
  `401 rest_forbidden` anonymously, so it is not a safe public source.
- `wp/v2/posts?slug=smink-2` and `wp/v2/search?search=Smink` returned no
  product record, so products should not be discovered through standard posts.
- Public HTML leaderboards work with `/?groupby=week`, `/?groupby=month`, and
  `/?groupby=year`.
- Older grouped periods are available through the public AJAX action
  `POST /wp-admin/admin-ajax.php` with `action=more-handler`,
  `next_period`, `next_page`, and `group_by`.
- The Smink founder profile exposes public website/city/rating fields, but the
  message/contact button requires login. Contacts must be parsed from safely
  authenticated first-party responses.

Implementation decisions:

- Prefer public HTML plus `more-handler` over WordPress REST for leaderboard
  discovery.
- Treat custom REST endpoints that return `401` as unavailable unless Product
  Radar provides official API credentials or documentation.
- Implement authenticated contact parsing through Product Radar's normal login
  flow or an official Product Radar API/export. Do not use copied browser
  cookies, DevTools tokens, social OAuth replay, or browser session replay.

## Phase 0: Repository Baseline

Deliverables:

- Confirm the current reference data in:
  - `data/raw/smink-2.json`
  - `data/raw/founder-nikatinstepan.json`
  - `data/clean/products.csv`
  - `data/clean/founders.csv`
- Confirm whether a Python project scaffold exists. If not, create it.
- Add a minimal dependency file only after choosing concrete libraries.
- Confirm how runtime secrets will be injected for contact parsing. Do not add
  credentials to source files, config files, test fixtures, raw metadata, or
  logs.

Recommended dependencies:

- `httpx` for HTTP with timeouts.
- `beautifulsoup4` plus `lxml` for HTML parsing.
- Python standard `csv`, `json`, `datetime`, `logging`, and `pathlib`.
- `pytest` for tests.

Acceptance checks:

- Existing reference CSV columns are captured exactly in `schemas.py`.
- No existing data is renamed or reformatted during this phase.

## Phase 1: Schema Constants and Validation

Files to create:

- `product_radar_parser/schemas.py`
- `product_radar_parser/validate.py`
- `tests/test_schema.py`

Implementation:

- Define `PRODUCT_COLUMNS` in exact order:
  - `product_id`
  - `founder_id`
  - `name`
  - `description`
  - `product_url`
  - `website_url`
  - `published_at`
  - `modified_at`
  - `application_category`
  - `pricing`
  - `headquarters_city`
  - `categories`
  - `target_audience`
  - `problem`
  - `solution`
  - `advantages`
  - `additional`
  - `status_title`
  - `status_text`
  - `votes_total`
  - `votes_founders`
  - `votes_users`
  - `discussion_count`
  - `gallery_urls`
- Define `FOUNDER_COLUMNS` in exact order:
  - `founder_id`
  - `name`
  - `profile_url`
  - `bio`
  - `city`
  - `website`
  - `telegram_url`
  - `registered_at`
  - `community_rating`
  - `founder_rating`
  - `badge_name`
  - `badge_level`
  - `badge_number`
  - `statuses`
- Validate exact column equality, not just presence.
- Validate required fields:
  - product: `product_id`, `founder_id`, `name`, `description`,
    `product_url`, `published_at`, `modified_at`, `votes_total`,
    `votes_founders`, `votes_users`, `discussion_count`
  - founder: `founder_id`, `name`, `profile_url`
- Validate integer fields:
  - product: `product_id`, `votes_total`, `votes_founders`, `votes_users`,
    `discussion_count`
  - founder: `community_rating`, `founder_rating`, `badge_number` when non-empty
- Validate uniqueness:
  - product `product_id`
  - product `product_url`
  - founder `founder_id`
  - founder `profile_url`
- Validate founder linkage from products to founders.

Acceptance checks:

- `data/clean/products.csv` passes schema validation.
- `data/clean/founders.csv` passes schema validation.
- A test fixture with an extra column fails.
- A test fixture with a missing required value fails.
- A test fixture with duplicate `product_id` fails.

## Phase 2: Raw Store and Logging

Files to create:

- `product_radar_parser/raw_store.py`
- `product_radar_parser/logging_config.py`
- `tests/test_failure_handling.py`

Implementation:

- Create a `RunContext` with a stable `run_id`, timestamp, and configured
  directories.
- Save fetched product HTML under `data/raw/products/`.
- Save fetched founder HTML under `data/raw/founders/`.
- Save fetch metadata as JSON without credentials or request headers.
- Save run events as JSONL under `data/raw/runs/`.
- Configure logs under `data/logs/`.
- Add a redaction helper that removes or masks:
  - `Authorization`
  - `Cookie`
  - `Set-Cookie`
  - query parameters that look like `token`, `access_token`, `auth`, `code`, or
    `session`

Acceptance checks:

- Raw HTML is written before extraction.
- Logs include failures and skipped URLs.
- Logs do not include credential-like values in controlled tests.

## Phase 3: HTTP Client

Files to create:

- `product_radar_parser/http_client.py`
- `product_radar_parser/config.py`

Implementation:

- Implement a single shared client with:
  - timeout;
  - serial requests;
  - configurable min and max delay;
  - jitter between requests;
  - bounded retries for transient failures;
  - no retries for normal permanent `4xx` responses except `429`;
  - a clear user agent;
  - optional runtime session cookie support from `ParserConfig.session_cookie`.
- Add a dedicated CLI parameter for externally supplied Product Radar session
  cookies:
  - primary option: `--session-cookie`;
  - backwards-friendly alias: `--cookie-token`;
  - value semantics: exact `Cookie` header value sent to Product Radar requests;
  - storage rule: keep only in memory for the current process.
- When a session cookie is configured, attach it as a `Cookie` request header
  inside `http_client.py`. Do not parse it, normalize it, log it, include it in
  errors, or persist it in raw metadata.
- Return a typed result object containing:
  - final URL;
  - status code;
  - response text;
  - content hash;
  - fetched timestamp.
- Never expose cookies, auth headers, or tokens in result objects.
- Allow normal same-host cookie handling in memory for server-set operational
  cookies, but never persist or log cookies. If a request presents a captcha,
  interactive anti-bot challenge, or login wall, stop that path and report it.

Acceptance checks:

- Client waits between requests in tests with a fake sleeper.
- Transient errors retry within the configured bound.
- Non-retryable failures are returned/logged and do not crash the pipeline.
- A controlled response that sets cookies does not write cookie values to raw
  metadata or logs.
- A configured `--session-cookie` value is sent as a request `Cookie` header.
- The session cookie value is absent from `FetchResult`, raw metadata, logs,
  run events, and `ParserConfig.__repr__`.

## Phase 4: Product Extraction from Stored Raw Data

Files to create:

- `product_radar_parser/extractors/product.py`
- `product_radar_parser/transform.py`
- `tests/test_acceptance_smink.py`

Implementation:

- Start with fixture-driven extraction from `data/raw/smink-2.json`.
- Then add HTML extraction against saved HTML once collection is available.
- Extract intermediate product fields:
  - `product_id`
  - `founder_id`
  - `name`
  - `description`
  - `product_url`
  - `website_url`
  - `published_at`
  - `modified_at`
  - optional metadata fields
  - category list
  - gallery URL list
  - vote counts
  - discussion count
- Transform list fields to `|` separated strings.
- Transform missing optional fields to empty strings.
- Keep integer fields as integers until CSV serialization.

Acceptance checks:

- Smink fixture produces exactly one product row.
- Smink row has:
  - `product_id = 11459`
  - `founder_id = "nikatinstepan"`
  - `name = "Smink"`
  - `product_url = "https://productradar.ru/product/smink-2/"`
  - `votes_total = 41`
  - `discussion_count = 9`
- Product row has exactly the Data Model columns.

## Phase 5: Founder Extraction from Stored Raw Data

Files to create:

- `product_radar_parser/extractors/founder.py`
- founder tests in `tests/test_acceptance_smink.py`

Implementation:

- Start with fixture-driven extraction from `data/raw/founder-nikatinstepan.json`.
- Derive `founder_id` from profile username or URL slug.
- Extract:
  - `founder_id`
  - `name`
  - `profile_url`
  - `bio`
  - `city`
  - `website`
  - `telegram_url`, only if visible without unsafe auth
  - `registered_at`
  - ratings
  - badge fields
  - statuses
- Join multiple statuses with `|`.
- Add optional contact enrichment from an uncommitted private CSV, for example
  `data/private/founder_contacts.csv`, with exactly:
  - `founder_id`
  - `telegram_url`
- Merge private contacts by `founder_id` only after validating that every
  referenced founder exists. Do not add extra clean columns.
- Do not fetch premium contacts through OAuth automation, copied browser
  cookies, DevTools token extraction, or browser session replay.

Acceptance checks:

- Founder fixture produces one founder row with `founder_id=nikatinstepan`.
- Product `founder_id` links to a founder row.
- Founder row has exactly the Data Model columns.
- Private contact enrichment can populate `telegram_url` without changing the
  Founder schema.
- Missing or unknown `founder_id` in the private contact CSV fails validation.

## Phase 6: Incremental Upsert

Files to create:

- `product_radar_parser/upsert.py`
- `tests/test_upsert.py`

Implementation:

- Load existing CSVs when present.
- Validate existing CSVs before merging.
- Upsert product rows by `product_id`.
- Reject any attempt to change an existing product's `product_url`.
- Upsert founder rows by `founder_id`.
- Reject duplicate IDs inside an incoming batch.
- Write outputs atomically:
  - write to a temporary file in the same directory;
  - validate the temporary file;
  - replace the old file only after validation passes.

Acceptance checks:

- Running the same input twice keeps one `product_id=11459`.
- Mutable fields update in place.
- Duplicate incoming `product_id` fails validation.
- A required field becoming empty fails validation.

## Phase 7: Discovery of Top Products

Files to create:

- `product_radar_parser/discovery.py`
- discovery tests with saved HTML fixtures.

Implementation:

- Discover public Product Radar leaderboards from HTML.
- Support `group_by=week`, `group_by=month`, and `group_by=year`.
- Support `periods=N`; keep `weeks=N` only as a backwards-compatible alias for
  `group_by=week`.
- Fetch the initial leaderboard from `/?groupby=<group_by>`.
- Parse each `.products__period` and its following `.products__item.card`
  elements in document order.
- For each card, extract:
  - product URL from `.product-bg-link`;
  - product ID from `.upvote[data-id]`;
  - current total votes from `.upvote[data-votes]`;
  - discussion count from `.card__comments`.
- For older periods, call the public AJAX endpoint:

```text
POST /wp-admin/admin-ajax.php
action=more-handler
next_period=<next_period>
next_page=<next_page>
group_by=<week|month|year>
```

- Continue with the response `next_period` and `next_page` until enough periods
  are collected or the endpoint marks the last page.
- Persist the initial HTML and every AJAX JSON response as raw data before
  parsing.
- For each period, collect top `k` product URLs in stable leaderboard order.
- Deduplicate URLs across periods before fetching product pages.
- Do not rely on manual DevTools steps.
- If the leaderboard structure or AJAX response shape changes, stop and report the
  blocked dependency rather than guessing.

Acceptance checks:

- Fixture for week `13 апреля - 19 апреля, 2026` returns Smink as top 1.
- `group_by=week`, `periods=1`, `top_k=1` returns one URL.
- Month and year fixtures parse product URLs and vote counts from public HTML.
- Duplicate URLs across periods are removed.

## Phase 8: End-to-End CLI

Files to create:

- `product_radar_parser/cli.py`

Implementation:

- `collect` command:
  - discover product URLs;
  - fetch raw product pages;
  - extract product records;
  - discover founder profile URLs from product records;
  - fetch raw founder pages;
  - extract founder records;
  - upsert clean CSVs;
  - run validation;
  - print a concise run summary.
- `collect` command accepts `--session-cookie` with alias `--cookie-token`.
  The argument is runtime-only and is forwarded to `ParserConfig.session_cookie`;
  the CLI must not print the value in normal output or error messages.
- `validate` command:
  - validate existing clean CSVs and print result.
- `parse-fixture` or test helper:
  - parse stored Smink fixture without network access.

Acceptance checks:

- CLI exits non-zero on validation failure.
- CLI exits zero when fixture acceptance passes.
- Single page parse failure is logged and skipped.
- CLI can initialize a collection run with `--session-cookie` without changing
  clean schemas or raw metadata schemas.

## Phase 9: Live Verification and Service Friendliness

Implementation:

- Run a conservative live collection with:

```bash
python -m product_radar_parser.cli collect --group-by week --periods 1 --top-k 1 --min-delay-seconds 2 --max-delay-seconds 5
```

For an authenticated dry run with an externally supplied Product Radar session
cookie:

```bash
python -m product_radar_parser.cli collect --group-by week --periods 1 --top-k 1 --session-cookie '<Cookie header value>' --dry-run
```

- Compare the current live top product with the fixture expectations only when
  the live top product is still Smink. Otherwise, validate schema/invariants and
  keep the Smink assertion restricted to fixture tests.
- Record assumptions in the iteration summary:
  - rate-limit delay used;
  - whether discovery used initial HTML only or `more-handler`;
  - whether founder contacts were public;
  - whether authenticated mode was enabled without revealing the cookie value;
  - whether any pages were skipped.

Acceptance checks:

- Live run completes without duplicate rows.
- Logs show rate-limited requests.
- No tokens or cookies are written to logs or raw metadata.
- Authenticated live run, when used, does not expose the cookie in stdout,
  stderr, logs, raw metadata, or clean CSVs.

## Phase 10: Hardening Before Scaling

Implementation:

- Add fixtures for at least three more product pages with different categories,
  gallery counts, and founder profile shapes.
- Add tests for missing optional fields.
- Add tests for malformed pages.
- Add tests for multiple founders only if Product Radar exposes such pages and
  the Data Model is clarified; current Data Model has one `founder_id` per
  product.
- Add `README.md` usage instructions after CLI behavior stabilizes.

Acceptance checks:

- Parser skips malformed pages and continues.
- Required fields stay non-null across fixtures.
- Multi-value fields remain strings, not arrays.

## Manual Verification Required

These items require human confirmation before broad scraping:

- Whether Product Radar permits sustained use of the public `more-handler`
  endpoint for weekly/monthly/yearly leaderboard collection.
- Whether Product Radar can provide an official premium contact export or
  documented account API.
- Whether using a runtime-supplied Product Radar session cookie is acceptable
  for the account and complies with Product Radar terms for this use case.
- Whether manually maintained private contact input is acceptable when official
  contact API/export is unavailable.
- Whether weekly and monthly update cadence should be one command with modes or
  separate scheduled jobs.
- Whether CSV remains sufficient or a database migration is needed.

## Blockers and Stop Conditions

Stop and report instead of continuing if:

- founder contacts require unsafe token extraction;
- a required field cannot be parsed reliably from public or safely authorized
  data;
- Product Radar page structure differs enough that deterministic extraction is
  not possible;
- clean schema cannot be preserved exactly;
- database choice becomes necessary for correctness rather than convenience.

## Iteration Report Template

After each implementation iteration, report:

1. What was implemented.
2. What assumptions were made.
3. What remains unresolved.
4. What needs manual verification.
5. What should be done next.
