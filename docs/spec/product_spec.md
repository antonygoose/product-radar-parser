# Product Specification

## Overview

Our main goal is to create a database of products based on the productradar.ru site. The database should consist of the products and all their metadata like name, description, founder, site etc.

It's crucial to consistently parse all the information needed and incrementally update it to keep fresh.

This info will be used by me to outreach the founders of products that I can search by filters. 

## Problem 

The main problem is that the current filters are too wide and you need to find screen the products manually that takes significant time.

## Use-cases

User: me as product manager
Goal: to find suitable companies and outreach the founders
Use-case: 
1. Open the database 
2. Filter the results (e.g. only b2b companies, 200+ likes, 15+ comments etc.)
3. Get contact of the founder

## Scope

We should create a data pipeline consisting of these steps: 
1. Data collection
- Collect the product pages as raw data
- Extract and store the information from them
2. Transformation
- To compute the additional metrics based on llm analysis and to add them to the data mart
3. Incremental upload and update
- To add new information once a week
- Update the old information once a month

## Functional Requirements

FR-1: the parser should collect top-k startups of the week where k is configurable parameter
FR-2: the parser should collect N weeks where N is configurable parameter
FR-3: the data mart should consist of the product's description, founder information and social activity (likes, comments)  
FR-4: the system must preserve schema exactly as defined in Data Model
FR-5: the system must not drop or rename fields

##  Non-Functional Requirements

NFR-1: you should rate-limit your parsing requests to not DDOS or be banned
NFR-2: the data is eventually consistent

## Data Model (source of truth)

### Product

Required fields:
- product_id (int, unique, stable)
- founder_id (string, foreign key)
- name (string)
- description (string)
- product_url (string, unique)
- website_url (string, optional)
- published_at (datetime)
- modified_at (datetime)
- votes_total (int)
- votes_founders (int)
- votes_users (int)
- discussion_count (int)

Optional fields:
- application_category
- pricing
- headquarters_city
- categories (string, "|" separated)
- target_audience
- problem
- solution
- advantages
- additional
- status_title
- status_text
- gallery_urls (string, "|" separated)

### Founder

Required fields:
- founder_id (string, unique, stable)
- name (string)
- profile_url (string, unique)

Optional fields:
- bio
- city
- website
- telegram_url
- registered_at
- community_rating
- founder_rating
- badge_name
- badge_level
- badge_number
- statuses

## Data Invariants

- product_id is unique and stable across runs
- product_url is unique
- founder_id links Product to Founder
- no duplicate products should exist across runs
- required fields must not be null
- optional fields may be empty but must exist in schema

## Update Rules

- new products are added on each weekly run
- existing products are updated, not duplicated
- immutable fields: product_id, product_url
- mutable fields: votes, discussion_count, description, etc.
- founder data is updated separately

## Acceptance Criteria

Given: the site https://productradar.ru
When parsing starts: 
1) we find top startups of the week, e.g. https://productradar.ru/product/smink-2/
2) parse its raw page
3) extract the info, e.g. name - "Smink", title - "Smink — платформа для создания сайтов, интернет-магазинов и управления бизнесом в одной системе", num_comments - "9", etc.


## Constraints

You need to be authorized and have premium account to get founders' contacts.

Authentication for founder contacts is provided externally.

The system must not extract, store in code, or log OAuth tokens.
If authentication is required, it must be injected securely at runtime.

## Open Questions

1) How to effectively update the database?
2) How to securily work with Oauth token?
3) How to easily create new attributes in the data mart?
4) How to create LLM-based attributes?
5) WHat database type should we use? 
6) How to prevent high disk usage?

## Success Criteria

1) We can parse the products information and the founders' contacts in reasonable (under 1 hour) time.
2) We can easily navigate through projects to find relevant ones.
3) At least 95% of required fields are correctly parsed.
4) The account is not banned by the website.
5) No duplicate products are created during updates.

### Out of Scope
- sending outreach messages
- building UI or dashboards
- bypassing anti-bot protection
- scraping data outside productradar.ru

