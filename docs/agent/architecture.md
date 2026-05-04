# Product Radar Parser Architecture

## Source Documents

This architecture is constrained by:

- `docs/spec/product_spec.md`: data model, update rules, non-functional requirements.
- `docs/spec/acceptance_tests.md`: acceptance fixture and correctness criteria.
- `AGENTS.md`: operational rules, safety rules, and delivery format.

If these documents disagree, `acceptance_tests.md` wins over implementation details and
`product_spec.md` wins over assumptions in this document.

## Goals

Build a reproducible Product Radar parser that:

- collects top `k` products for `N` periods from `https://productradar.ru`,
  grouped by week, month, or year;
- stores raw fetched data before any transformation;
- extracts product and founder records into the exact Data Model schemas;
- supports incremental re-runs without duplicate products or founders;
- validates every output before a run is considered complete;
- rate-limits requests and continues after per-page failures;
- never stores OAuth tokens or other credentials in source, output files, or logs.

## Non-Goals

- No outreach sending.
- No UI or dashboard.
- No anti-bot bypass.
- No scraping outside `productradar.ru`.
- No browser-session replay or unsafe token extraction for founder contacts.
- No database service until the CSV pipeline is correct and stable.

## Data Flow

The pipeline has four deterministic stages:

1. Discovery
   - Input: `periods`, `top_k`, `group_by`, and the Product Radar base URL.
   - Output: ordered product URLs for the requested leaderboards.
   - The Smink acceptance run is `weeks=1`, `top_k=1`, expected URL
     `https://productradar.ru/product/smink-2/`.

2. Raw collection
   - Fetch product pages and founder profile pages with rate limiting.
   - Persist raw response content and fetch metadata before parsing.
   - Failed fetches are logged and skipped; the whole run continues.

3. Structured extraction
   - Parse raw HTML/JSON into normalized intermediate Python dicts.
   - Product extraction and founder extraction are separate modules.
   - Selectors must prefer stable semantic sources such as JSON-LD,
     canonical URLs, profile links, schema.org metadata, explicit labels, and
     durable element attributes over position-only selectors.

4. Clean transformation and upsert
   - Convert intermediate records to the exact clean schemas.
   - Preserve `product_id`, `product_url`, and `founder_id` as stable identity.
   - Join multi-value fields with `|`.
   - Merge into existing clean datasets by stable IDs, updating mutable fields
     without creating duplicates.
   - Run schema and acceptance validation before reporting success.

## Proposed Repository Layout

```text
product-radar-parser/
  data/
    raw/
      products/
        <product_id-or-slug>.html
        <product_id-or-slug>.json
      founders/
        <founder_id>.html
        <founder_id>.json
      runs/
        <run_id>.jsonl
    clean/
      products.csv
      founders.csv
    logs/
      parser.log
      validation.log
  docs/
    agent/
      architecture.md
      implementation_plan.md
    spec/
      product_spec.md
      acceptance_tests.md
  product_radar_parser/
    __init__.py
    cli.py
    config.py
    http_client.py
    discovery.py
    raw_store.py
    extractors/
      __init__.py
      product.py
      founder.py
    transform.py
    upsert.py
    schemas.py
    validate.py
    logging_config.py
  tests/
    fixtures/
      raw/
    test_acceptance_smink.py
    test_schema.py
    test_upsert.py
    test_failure_handling.py
```

The current repository already contains reference outputs:

- `data/raw/smink-2.json`
- `data/raw/founder-nikatinstepan.json`
- `data/clean/products.csv`
- `data/clean/founders.csv`

The first implementation should preserve these outputs as acceptance fixtures
while adding executable code around them.

## Runtime Interface

Primary CLI:

```bash
python -m product_radar_parser.cli collect --group-by week --periods 1 --top-k 1
python -m product_radar_parser.cli collect --group-by week --periods 1 --top-k 1 --session-cookie '<Cookie header value>'
python -m product_radar_parser.cli validate
```

Useful options:

- `--group-by`: leaderboard grouping, one of `week`, `month`, or `year`.
  Default: `week`.
- `--periods`: number of grouped leaderboards to collect. Default: `1`.
- `--weeks`: backwards-compatible alias for `--periods` when `--group-by=week`.
- `--top-k`: number of products per period. Default: `1`.
- `--base-url`: default `https://productradar.ru`.
- `--raw-dir`: default `data/raw`.
- `--clean-dir`: default `data/clean`.
- `--min-delay-seconds`: default `2.0`.
- `--max-delay-seconds`: default `5.0`.
- `--timeout-seconds`: default `30`.
- `--dry-run`: fetch and validate without writing clean outputs.
- `--session-cookie`: optional Product Radar session `Cookie` header value
  provided at runtime by the user. Alias: `--cookie-token`. This value is
  passed only to the in-memory HTTP client and must never be printed, logged,
  serialized into raw metadata, written to CSV, or stored in configuration.

Premium authentication is required for founder contacts and must be provided at
runtime only through the dedicated `--session-cookie` CLI parameter, environment
variables, prompt input, or an external secret provider. It must never be
committed, printed, logged, or serialized into `data/raw`. Authentication state
must live only in the HTTP client's in-memory cookie jar or in-memory request
headers for the duration of the run.

## Public API and Discovery Findings

Checked on `2026-04-14`:

- `https://productradar.ru/wp-json/` is enabled and exposes standard WordPress
  routes plus custom namespaces `productradar/v1` and `radar/v1`.
- The custom listing endpoint
  `https://productradar.ru/wp-json/radar/v1/products/{cat_id}` exists, but an
  anonymous request returned `401 rest_forbidden`; it must not be used unless
  Product Radar provides explicit authorized API access.
- Standard `wp/v2/posts` search does not expose Product Radar product pages;
  product pages appear to be served outside the public `wp/v2/posts` collection.
- Public leaderboard pages are available as HTML:
  - `https://productradar.ru/?groupby=week`
  - `https://productradar.ru/?groupby=month`
  - `https://productradar.ru/?groupby=year`
- Additional periods are loaded by the site's own public AJAX action:
  `POST https://productradar.ru/wp-admin/admin-ajax.php` with form fields
  `action=more-handler`, `next_period`, `next_page`, and `group_by`.
  The JSON response contains `html`, `next_period`, and `next_page`.
- Some requests may first return a Beget anti-bot cookie-setting page. The HTTP
  client may accept ordinary server-set cookies for the same host, but must not
  persist or log cookies. It must not bypass captchas, login walls, or other
  interactive anti-bot checks.

Discovery should therefore prefer public HTML and the `more-handler` AJAX flow
over WordPress REST routes. The REST index remains useful as an environment
check, not as the primary data source.

## Leaderboard Discovery Contract

For `group_by=week`, `month`, or `year`:

- fetch the initial page `/?groupby=<group_by>`;
- parse `.products__period` and following `.products__item.card` elements in
  document order;
- within each card, parse the product URL from `.product-bg-link`, product ID
  from `.upvote[data-id]`, current total votes from `.upvote[data-votes]`, and
  discussion count from `.card__comments`;
- take the first `top_k` cards for each period;
- for older periods, call the public `more-handler` AJAX endpoint serially using
  the returned `next_period` and `next_page` until `periods` periods are
  collected;
- persist every fetched HTML or AJAX response before parsing;
- deduplicate product URLs across periods before fetching product detail pages.

The Smink acceptance fixture is a frozen historical check. Live leaderboard
values can drift after `2026-04-14 13:15 Europe/Moscow`, so live discovery
validates schema and invariants while fixture tests validate exact Smink counts.

## Founder Contact Strategy

The public founder profile for the Smink fixture exposes the founder page,
public website, city, ratings, and registration date. The contact button is an
authenticated `Написать` action that links unauthenticated users to `/login`.

The safest simple way to parse required contacts is an explicit authenticated
collection mode:

- the user provides Product Radar premium-account authentication at runtime
  through the dedicated `--session-cookie` CLI parameter, a secret provider,
  environment variables, or an interactive prompt;
- when `--session-cookie` is used, the value must be treated as the exact
  `Cookie` header value for same-session Product Radar requests and must not be
  parsed, transformed, persisted, echoed, or included in run summaries;
- the parser performs the normal first-party login flow against
  `https://productradar.ru/wp-login.php` or a documented Product Radar contact
  API, if Product Radar provides one; if a session cookie is supplied directly,
  the parser skips login and sends that cookie only through the HTTP client;
- session cookies stay in an in-memory cookie jar or in-memory request header
  and are discarded after the run;
- authenticated founder pages are fetched with the same rate-limited HTTP
  client and persisted as raw HTML, but raw metadata must exclude cookies,
  authorization headers, request bodies, passwords, and login responses;
- the founder extractor parses `telegram_url` from the authenticated founder
  profile or authenticated contact response and writes it into the existing
  Founder schema;
- if the authenticated response still hides contacts, requires social OAuth,
  captcha, JavaScript-only browser state, copied browser cookies, DevTools token
  extraction, or browser session replay, stop and report the blocked dependency.

This is parsing, not manual enrichment: contacts are collected by the parser
from safely authenticated Product Radar responses. The only acceptable fallback
is an official Product Radar export or documented API for the same premium
account.

## Rate Limiting and HTTP Behavior

`http_client.py` owns all network access:

- one request at a time by default;
- random delay between `min_delay_seconds` and `max_delay_seconds`;
- explicit `User-Agent` identifying a non-aggressive research parser;
- optional runtime `Cookie` header from `--session-cookie`/`--cookie-token`,
  applied in memory to requests and excluded from all result objects, raw
  metadata, logs, and run events;
- timeout on every request;
- bounded retries for transient `429`, `500`, `502`, `503`, and `504`;
- no retry for permanent `4xx` except `429`;
- response status, URL, content hash, and timestamp logged without cookies or
  authorization headers.

If Product Radar rate limits are unknown, keep conservative defaults and
document the assumption in the run summary.

## Raw Storage Contract

Raw collection must preserve source data before transformation.

Each raw product artifact should include:

```json
{
  "source_url": "https://productradar.ru/product/smink-2/",
  "fetched_at": "2026-04-14T13:15:00+03:00",
  "status_code": 200,
  "content_sha256": "...",
  "html_path": "data/raw/products/smink-2.html"
}
```

The structured JSON extracted from that raw HTML may be stored beside it, but
it must not replace the raw HTML. Raw files should not contain credentials,
cookies, authorization headers, or full request headers.

## Clean Data Contract

Clean outputs are CSV files. They must contain exactly the fields below, in the
listed order, with no extra columns.

### `data/clean/products.csv`

```text
product_id
founder_id
name
description
product_url
website_url
published_at
modified_at
application_category
pricing
headquarters_city
categories
target_audience
problem
solution
advantages
additional
status_title
status_text
votes_total
votes_founders
votes_users
discussion_count
gallery_urls
```

Required non-null fields:

- `product_id` as integer
- `founder_id` as string
- `name` as string
- `description` as string
- `product_url` as unique string
- `published_at` as datetime string
- `modified_at` as datetime string
- `votes_total` as integer
- `votes_founders` as integer
- `votes_users` as integer
- `discussion_count` as integer

Optional fields must exist and may be empty strings.

### `data/clean/founders.csv`

```text
founder_id
name
profile_url
bio
city
website
telegram_url
registered_at
community_rating
founder_rating
badge_name
badge_level
badge_number
statuses
```

Required non-null fields:

- `founder_id` as unique stable string
- `name` as string
- `profile_url` as unique string

Optional fields must exist and may be empty strings.

## Identity and Upsert Rules

Products:

- primary identity: `product_id`;
- secondary uniqueness: `product_url`;
- immutable fields: `product_id`, `product_url`;
- mutable fields: all vote counts, discussion count, description, website URL,
  categories, status, gallery URLs, and other metadata.

Founders:

- primary identity: `founder_id`;
- secondary uniqueness: `profile_url`;
- `founder_id` is derived from the Product Radar profile URL slug, for example
  `https://productradar.ru/user/nikatinstepan/` maps to `nikatinstepan`;
- existing founder rows are updated by `founder_id`, not appended.

The upsert layer must reject a batch if:

- two rows in the same batch have the same `product_id`;
- the existing clean dataset contains duplicate `product_id`;
- two different `product_id` values map to the same `product_url`;
- a required field is missing or null.

## Extraction Strategy

Product extractor responsibilities:

- product ID from stable embedded data or page metadata;
- canonical `product_url`;
- `name` and `description`;
- `website_url`;
- publication and modification timestamps;
- categories and gallery URLs as lists in intermediate data;
- founder profile URL and derived `founder_id`;
- vote counts split into total, founders, users;
- discussion count;
- optional Product Radar product questionnaire fields.

Founder extractor responsibilities:

- `founder_id` from profile URL slug;
- name and canonical profile URL;
- bio, city, website, telegram URL when available without unsafe auth;
- registration date;
- community and founder ratings;
- badge fields;
- statuses as a list in intermediate data.

Transformation responsibilities:

- convert optional missing values to empty strings;
- convert list fields to `|` separated strings;
- convert integer fields to integers;
- preserve datetime strings with timezone offsets when available;
- output exactly the clean schemas.

## Validation

`validate.py` must run after every collection and before completion:

- product schema equals the expected product column list exactly;
- founder schema equals the expected founder column list exactly;
- no extra columns;
- no missing columns;
- required fields are present and non-empty;
- integer fields parse as integers;
- `product_id` is unique;
- `product_url` is unique;
- `founder_id` in every product exists in founders;
- `categories` and `gallery_urls` are strings, either empty or `|` separated;
- the Smink acceptance fixture passes:
  - exactly one product for `group_by=week`, `periods=1`, `top_k=1`;
  - `product_id = 11459`;
  - `founder_id = "nikatinstepan"`;
  - `name = "Smink"`;
  - `votes_total = 41`;
  - `discussion_count = 9`.

Because the Product Radar leaderboard and counts can change after
`2026-04-14 13:15 Europe/Moscow`, live validation should be separated from the
frozen fixture test. The fixture test uses stored raw data; the live run verifies
schema and invariants against current data.

## Error Handling

Per-page failures are non-fatal:

- log the failing URL, stage, error type, and timestamp;
- do not log credentials, cookies, tokens, or raw request headers;
- skip that record;
- continue processing remaining URLs;
- include skipped URLs in the run summary.

Fatal failures:

- schema cannot be preserved;
- authentication requires unsafe token handling;
- product IDs or founder IDs cannot be extracted reliably;
- page structure is inconsistent enough that required fields cannot be parsed
  deterministically.

## Storage Choice

Use CSV files in `data/clean` for the first implementation because:

- the source Data Model is tabular;
- the acceptance reference data already uses CSV;
- CSV keeps incremental behavior easy to inspect;
- a database choice is listed as an open question in the product spec.

A database migration can be introduced later after correctness is proven. The
database schema must mirror the same fields exactly and keep CSV export tests.

## Assumptions

- Public product pages contain enough data to satisfy required product fields.
- Public founder profile pages contain enough data to satisfy required founder
  fields, except premium-only contacts.
- Telegram URLs require safe runtime authentication for premium contact parsing.
- Conservative serial fetching is acceptable because the success criteria allow
  runs under one hour.

## Open Risks

- Founder contacts require premium authentication. If the account can only be
  accessed through unsafe token extraction, browser session replay, copied
  cookies, captcha, or JavaScript-only OAuth state, contact parsing is blocked
  until Product Radar provides a safe login method, export, or documented API.
- Leaderboard URLs and week filters must be confirmed during implementation
  from public site HTML.
- Vote split selectors may change. Extraction should be backed by fixtures for
  the acceptance product and at least a few additional products before scaling.
