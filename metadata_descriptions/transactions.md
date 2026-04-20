# Transactional Purchase Feed (Mastercard-style)

Synthetic purchase transaction feed modelled on Mastercard merchant data. Represents purchase events that may or may not link to an ad exposure via cookie_id or hem. cookie_id is populated at market-specific rates (US: 30%, UK: 20%, JP: 15%); hem at (US: 25%, UK: 15%, JP: 10%). The pan_token is a tokenised non-reversible payment card reference used for LTV and CAC calculations. Partitioned by date.

## Tags
- business_owner: Marketing Data Products
- data_domain: transactions
- pii_class: pseudonymous
- refresh_cadence: daily
- row_count_approx: 500000
- marketing_usecases: post_campaign_analysis,audience_discovery

## Columns

- txn_id: Primary key (UUID v4) for each transaction.
- pan_token: Non-reversible tokenised PAN. Always populated. Used for LTV aggregation. Does NOT link to real card data.
- cookie_id: FK to cookie_registry. Market-specific fill rates (US 30%, UK 20%, JP 15%). Join via hem as fallback.
- hem: SHA-256 hashed email. Market-specific fill rates (US 25%, UK 15%, JP 10%). Glossary term: Hashed Email / HEM.
- merchant_name: Name of the merchant where the transaction occurred.
- merchant_category_code: ISO-18245 MCC. 4-digit string. Use for product-category conversion analysis.
- brand: Resolved brand from merchant (may be null).
- amount_usd: Transaction value in USD. Use SUM for revenue in ROAS and MER calculations.
- currency_code: ISO-4217 currency code.
- country_code: ISO 3166-1 alpha-2 country where the transaction occurred.
- city: City where the transaction occurred.
- lat: Merchant latitude.
- lon: Merchant longitude.
- channel: Transaction channel: in_store | online | contactless.
- txn_ts: Timestamp when the transaction occurred.
- event_date: Date of the transaction (derived from txn_ts).
- partition_date: Iceberg partition key (day). Always filter on this column for time-range queries.

## Data Quality Rules
- txn_id: non_null
- pan_token: non_null
- amount_usd: non_null
