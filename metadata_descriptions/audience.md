# Audience Profiles (Panel Model)

Modelled audience segments derived from panel survey data and behavioural signals. Each row represents a distinct addressable audience cohort characterised by demographics, interests, brand affinity scores, and channel over-index scores. The hem column is a SHA-256 hashed email populated for ~60% of records to reflect realistic consent rates. The lat/lon and location_lat/location_lon columns carry identical centroid values — the duplication is intentional to demonstrate Dataplex semantic graph synonym resolution.

## Tags
- business_owner: Marketing Data Products
- data_domain: audience
- pii_class: pseudonymous
- refresh_cadence: daily
- row_count_approx: 8000
- marketing_usecases: audience_discovery,audience_performance_prediction

## Columns

- audience_id: Surrogate primary key (UUID v4). Stable across refreshes.
- segment_name: Human-readable cohort label used in campaign planning tools.
- country_code: ISO 3166-1 alpha-2 country code for the participant's location.
- region: State, province, or administrative region within the country.
- age_band: Age range category (e.g., 18-24, 25-34, 35-44, 45-54, 55+).
- gender: Participant's gender identity (M / F / NB / Unknown).
- income_band: Household income range category (Low / Mid / High).
- interests: IAB interest taxonomy labels for this audience cohort.
- brand_affinity_scores: MAP of brand → affinity score [0,1]. Higher = stronger affinity.
- channel_index: MAP of channel → over-index ratio vs population. >1 = over-indexes.
- hem: SHA-256 of normalised email. ~60% populated. Canonical glossary term: Hashed Email / HEM.
- lat: Centroid latitude of dominant geo cluster. Synonym: location_lat (same table).
- lon: Centroid longitude. Synonym: location_lon (same table).
- location_lat: Synonym for lat. Duplicate column to demonstrate semantic synonym resolution.
  - Synonym Of: lat
- location_lon: Synonym for lon. Duplicate column to demonstrate semantic synonym resolution.
  - Synonym Of: lon
- panel_weight: Statistical projection weight. Use when scaling segment counts to population estimates.
- created_at: Record creation timestamp.
