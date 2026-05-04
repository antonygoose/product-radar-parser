# Acceptance Tests

## General

As acceptance test we take this product page: https://productradar.ru/product/smink-2/

It's mentioned as top-1 of the week "13 апреля - 19 апреля, 2026". This information is valid on the 14th of april 2026, 13:15 Moscow Time and can change.

In this case we take top-1 product (k=1) of the latest week (N=1).


## Product extraction

Given product page https://productradar.ru/product/smink-2/
When parsing is completed
Then the output contains exactly 1 product record

And:
- product_id = 11459
- founder_id = "nikatinstepan"
- name = "Smink"
- product_url matches source URL
- votes_total = 41
- discussion_count = 9

And all required fields are present and non-null
And all required fields from the Data Model are present
And required fields are non-null
And field types match the Data Model definition

## Schema validation

Then the product dataset contains all fields defined in Data Model
And no fields are missing or renamed
And no extra fields outside Data Model are present

## Field types

Then:
- votes_total is integer
- votes_founders is integer
- votes_users is integer
- discussion_count is integer
- product_id is integer
- founder_id is string

## Founder linkage

Given founder data is parsed
Then:
- founder_id exists in founders dataset
- each product has valid founder_id

And founder_id correctly links product to founder record

## Incremental consistency

Given parser runs twice with the same configuration
Then:
- no duplicate product_id exists
- number of unique product_id remains the same
- existing records are updated, not duplicated

## Multi-value fields

Then:
- categories is a "|" separated string or empty
- gallery_urls is a "|" separated string or empty
- separator "|" is preserved

## Failure handling

Given a page cannot be parsed
Then:
- the error is logged
- the process continues for other records

## Reference

You can find all the reference schemas and data in /data/clean folder.