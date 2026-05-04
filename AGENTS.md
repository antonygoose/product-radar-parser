# Agent

## Mission

Your goal is to create a productradar.ru parser to collect information (name, site, description etc.) about the startups and projects that are presented on this site.

## Inputs

### Requirements

- `/docs/spec/product_spec.md` defines expected system behavior, data model, and constraints.
- `/docs/spec/acceptance_tests.md` defines how correctness is verified.

### Design and Planning

- `/docs/agent/architecture.md` defines expected system design based on the product_spec.md.
- `/docs/agent/implementation_plan.md` defines implementation plan based on the product_spec.md, acceptance_tests.md and architecture.md.

If they conflict, stop and report the conflict instead of guessing.

## Spec Update Workflow

Use `/docs/spec/product_spec.md` as the single source of truth.

Active change requests are located in `/docs/spec/change_requests/` (excluding `/archive/`). Change requests must not conflict. If they do, stop and report.

### Applying Changes

- Read `product_spec.md` and all active change request files
- Integrate changes by rewriting relevant sections in `product_spec.md`
- Do not append changes as separate sections
- Do not duplicate or preserve outdated logic
- Keep the spec internally consistent
- Do not resolve conflicting change requests
- If conflicts exist, stop and report

### Tests

- If changes affect behavior, update `/docs/spec/acceptance_tests.md`
- Use `tests_change.md` as input for required test updates
- Ensure spec and tests stay aligned

### Changelog

- Add a concise entry to `/docs/spec/changelog.md` summarizing applied changes

### Archiving

After processing:
- Move all applied change request files to `/docs/spec/change_requests/archive/`
- Do not process archived files again

### Archive Naming Rules

All archived files must follow this format:

`YYYY-MM-DD_<short_description>.md`

Examples:
- `2026-05-04_csv_to_supabase.md`
- `2026-05-06_add_outreach_agent.md`

Rules:
- Use ISO date format (YYYY-MM-DD)
- Description must be short, lowercase, and use underscores
- No spaces or special characters
- Names must be unique and reflect the intent of the change

### Constraints

- Never maintain multiple conflicting versions of the spec
- Never treat archived files as active inputs
- Always keep `product_spec.md` as the only source of truth

## Priorities

First priority - correctness: information must be consistent.
Second priority - simplicity: the process must be simple enough to be reproducible and reliable.
Third priority - service-friendly: the parser must be rate limited to not DDOS the site and to not be banned.
Fourth priority - speed: the parser's execution time should be reasonable.

## Data Contract

The parser output must follow the Data Model defined in `/docs/spec/product_spec.md`.
Do not change the data model unless explicitly requested through an active change request.


## Definition of Done

A task is considered complete only if all acceptance tests in acceptance_tests.md are satisfied.

## Delivery Format

After each iteration provide:
1. What was implemented
2. What assumptions were made
3. What remains unresolved
4. What needs manual verification
5. What should be done next


