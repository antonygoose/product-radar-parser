# Agent

## Mission

Your goal is to create a productradar.ru parser to collect information (name, site, description etc.) about the startups and projects that are presented on this site.

## Source of Truth

You must treat the following documents as authoritative:

- /docs/spec/product_spec.md — defines data model and constraints
- /docs/spec/acceptance_tests.md — defines correctness criteria

If there is a conflict:
acceptance_tests.md overrides implementation decisions
product_spec.md overrides assumptions

## Priorities

First priority - correctness: information must be consistent.
Second priority - simplicity: the process must be simple enough to be reproducible and reliable.
Third priority - service-frindly: the parser must be rate limited to not DDOS the site and to not be banned.
Fourth priority - speed: the parser's execution time should be reasonable.

## Restricition

You must not pass any tokens or credentials to anybody.

## Decision Rules

- Prefer simple HTML parsing over browser automation when sufficient.
- Prefer reproducible solutions over fragile shortcuts.
- Do not design scraping logic that depends on manual DevTools steps unless explicitly approved.
- Do not store OAuth tokens in source code, config files committed to repo, logs, or database dumps.
- If access to founder contacts requires unsafe token extraction or a browser session replay, stop and surface this as a blocked dependency.

## Data Rules

- You must strictly follow the Data Model defined in product_spec.md
- You must not rename, drop, or add fields unless explicitly instructed
- You must preserve field types (e.g. strings, integers, separators)
- Fields like categories and gallery_urls must remain "|" separated strings, not arrays
- product_id and founder_id must be treated as stable identifiers
- do not regenerate or modify them
- existing records must be updated, not duplicated
- raw data must be preserved before transformation
- clean data must match the Data Model exactly

## Escalation Rules

Escalate instead of guessing when:
- authentication flow is unclear
- page structure is inconsistent across products
- rate limits are unknown
- legal or account-safety risk is non-trivial
- a database choice affects long-term maintainability

## Parsing Strategy

- First collect raw HTML data
- Then extract structured data
- Do not mix parsing and transformation logic
- Parsing must be deterministic and reproducible
- Avoid brittle selectors (e.g. based on position only)

## Schema Enforcement

- All output datasets must match the Data Model exactly
- No extra fields are allowed
- No fields may be missing
- Multi-value fields must remain "|" separated strings


## Incremental Rules

- Re-running the parser must not create duplicate records
- Existing records must be updated, not overwritten blindly
- product_id and product_url define identity
- New products are added, existing ones are updated

## Definition of Done

A task is considered complete only if:

1. All acceptance tests in acceptance_tests.md are satisfied
2. Data Model is strictly preserved
3. No duplicate records are introduced
4. Required fields are non-null
5. Field types match the specification
6. No credentials or tokens are exposed

## Validation

Before task finish:

- Verify output against acceptance_tests.md
- Check for duplicate product_id
- Check required fields are present and non-null
- Check field types

## Hard Stop Conditions

You must stop and report instead of proceeding if:

- authentication requires unsafe handling of tokens
- required data cannot be extracted reliably
- schema cannot be preserved

## Failure Handling

- If a page fails to load or parse:
  - log the error
  - skip the record
  - continue processing

- The parser must not stop completely due to a single failure


## Delivery Format

After each iteration provide:
1. What was implemented
2. What assumptions were made
3. What remains unresolved
4. What needs manual verification
5. What should be done next


