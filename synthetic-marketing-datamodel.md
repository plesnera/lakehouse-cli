# Lakehouse Content — Final Deliverables & Implementation Plan

> Synthesised from `lakehouse-tasks-claude.md` and `lakehouse-tasks-vibe.md`
> Requirements source: `Agent.md`
> GCP Project: `wpp-dataproducts-lakehouse`
> Date: 2026-04-13

---

## Synthesis Notes

`lakehouse-tasks-claude.md` provided the implementation design. `lakehouse-tasks-vibe.md`
was a restatement of `Agent.md` without additional design content. This final document is
based on the claude proposal with the following corrections applied:

| Item | Was | Now |
|------|-----|-----|
| Dataplex Lake name in topology | `wpp-marketing-lake` | `demo-data` |
| `cookie → audience` fill rate | 55% | 40% |
| `cookie → hem` fill rate | 40% | 35% |
| `pixel → cookie` fill rate | 85% | 82% |
| `n_cookies` default | 1 000 000 | 80 000 |
| `n_pixel_events` default | 10 000 000 | 2 000 000 |
| `n_transactions` default | 2 000 000 | 500 000 |
| `target_markets` default | US/GB/DE/FR/AU | US/GB/JP |
| `audience` synonym columns | lat/lon only | added `location_lat`/`location_lon` physical columns |
| Per-market match-rate variation | not modelled | added per-market multiplier to generator design |

---

## Deliverable 1 — Data Model Design

### 1.1 Entity Relationship Overview

```
┌────────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│  audience      │──────│  cookie_registry  │──────│  pixel_events       │
│  (panel model) │ 0..* │  (device/id map)  │ 0..* │  (impression/click/ │
└────────────────┘      └──────────────────┘      │   video events)     │
        │                        │                 └──────────┬──────────┘
        │ hem (partial)          │ hem (partial)              │ campaign_id
        │                        │                            │
        ▼                        ▼                            ▼
┌────────────────┐      ┌──────────────────┐       ┌─────────────────────┐
│  transactions  │      │  campaigns       │◄──────│  (pixel_events ref) │
│  (card feed)   │      │  (metadata,      │       └─────────────────────┘
└────────────────┘      │   flights,spend) │
                        └──────────┬───────┘
                                   │ campaign_id (1..*)
                              ┌────▼──────┐
                              │ creatives  │
                              │ (content   │
                              │  assets)   │
                              └───────────┘
```

Join quality is intentionally imperfect — all FK columns carry realistic null rates
(see Section 1.4) to model real-world identity graph resolution limits.

---

### 1.2 Table Schemas

#### `audience` — Modelled audience segments

Dataplex Zone: **curated-data**

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| `audience_id` | STRING (UUID) | Primary key | No |
| `segment_name` | STRING | Named segment label e.g. "Eco-Conscious Millennials" | No |
| `country_code` | STRING(2) | ISO-3166-1 alpha-2 | No |
| `region` | STRING | Sub-national region / DMA | Yes |
| `age_band` | STRING | e.g. "25-34" | No |
| `gender` | STRING | M / F / NB / Unknown | No |
| `income_band` | STRING | Low / Mid / High | Yes |
| `interests` | ARRAY\<STRING\> | IAB interest taxonomy labels | Yes |
| `brand_affinity_scores` | MAP\<STRING,FLOAT\> | Brand → affinity score 0–1 | Yes |
| `channel_index` | MAP\<STRING,FLOAT\> | Channel → over-index ratio vs population | Yes |
| `hem` | STRING | SHA-256 of normalised email — ~60% populated | Yes |
| `lat` | DOUBLE | Centroid latitude of dominant location cluster | Yes |
| `lon` | DOUBLE | Centroid longitude | Yes |
| `location_lat` | DOUBLE | **Synonym for `lat`** — identical value, different name (semantic demo) | Yes |
| `location_lon` | DOUBLE | **Synonym for `lon`** — identical value, different name (semantic demo) | Yes |
| `panel_weight` | DOUBLE | Statistical weight for population projection | No |
| `created_at` | TIMESTAMP | Record creation timestamp | No |

*Semantic synonym pairs: `lat`/`lon` ↔ `location_lat`/`location_lon`; `hem` ↔ `hashed_email` (cookie_registry)*

---

#### `cookie_registry` — Device / identity mapping table

Dataplex Zone: **curated-data**

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| `cookie_id` | STRING (UUID) | Primary key — **synonym: `visitor_id`** | No |
| `visitor_id` | STRING | Synonym for `cookie_id` — identical value (semantic demo) | No |
| `device_id` | STRING | Platform device identifier — **synonym: `cookie_id`** | Yes |
| `audience_id` | STRING | FK → `audience.audience_id` — **~40% populated** | Yes |
| `hem` | STRING | SHA-256 hashed email — **~35% populated** | Yes |
| `hashed_email` | STRING | **Synonym for `hem`** — identical value, different name (semantic demo) | Yes |
| `country_code` | STRING(2) | Observed market | No |
| `city` | STRING | Resolved city | Yes |
| `lat` | DOUBLE | Last known latitude | Yes |
| `lon` | DOUBLE | Last known longitude | Yes |
| `device_type` | STRING | desktop / mobile / tablet / ctv | No |
| `browser` | STRING | Chrome / Safari / Firefox / App / Unknown | Yes |
| `first_seen_at` | TIMESTAMP | First observation | No |
| `last_seen_at` | TIMESTAMP | Most recent observation | No |

*Semantic synonym pairs: `cookie_id` ↔ `visitor_id` ↔ `device_id`; `hem` ↔ `hashed_email`*

---

#### `pixel_events` — Ad tracking pixel event stream

Dataplex Zone: **raw-data**

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| `event_id` | STRING (UUID) | Primary key | No |
| `event_type` | STRING | impression / click / video_start / video_q1 / video_q2 / video_q3 / video_complete / engagement | No |
| `cookie_id` | STRING | FK → `cookie_registry.cookie_id` — **~82% populated** | Yes |
| `campaign_id` | STRING | FK → `campaigns.campaign_id` | No |
| `creative_id` | STRING | FK → `creatives.creative_id` | No |
| `channel` | STRING | meta / youtube / tiktok / display / ctv / search | No |
| `placement` | STRING | Ad placement / format hint | Yes |
| `country_code` | STRING(2) | Geo of event | No |
| `region` | STRING | Sub-national | Yes |
| `lat` | DOUBLE | Event latitude — ~50% populated | Yes |
| `lon` | DOUBLE | Event longitude | Yes |
| `device_type` | STRING | desktop / mobile / tablet / ctv | Yes |
| `spend_usd` | DOUBLE | Media cost for this event (CPM pro-rated for impressions; 0 otherwise) | Yes |
| `event_ts` | TIMESTAMP | Event timestamp | No |
| `_partition_date` | DATE | Iceberg partition column (day) | No |

---

#### `campaigns` — Campaign / flight metadata

Dataplex Zone: **curated-data**

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| `campaign_id` | STRING (UUID) | Primary key | No |
| `campaign_name` | STRING | Human-readable name | No |
| `brand` | STRING | Advertiser brand — **synonym: `advertiser`** | No |
| `advertiser` | STRING | **Synonym for `brand`** — identical value (semantic demo) | No |
| `product_category` | STRING | IAB product category | No |
| `country_code` | STRING(2) | Primary market | No |
| `regions` | ARRAY\<STRING\> | Target regions | Yes |
| `channels` | ARRAY\<STRING\> | Activated channels | No |
| `objective` | STRING | awareness / consideration / conversion / retention | No |
| `budget_usd` | DOUBLE | Total approved budget | No |
| `actual_spend_usd` | DOUBLE | Realised spend | Yes |
| `start_date` | DATE | Flight start | No |
| `end_date` | DATE | Flight end | No |
| `status` | STRING | planned / active / completed / paused | No |
| `created_at` | TIMESTAMP | Record creation | No |

*Semantic synonym pairs: `brand` ↔ `advertiser`*

---

#### `creatives` — Content asset library

Dataplex Zone: **curated-data**

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| `creative_id` | STRING (UUID) | Primary key | No |
| `campaign_id` | STRING | FK → `campaigns.campaign_id` | No |
| `creative_name` | STRING | Asset label | No |
| `format` | STRING | video_15s / video_30s / static_banner / carousel / stories | No |
| `channel` | STRING | Channel this asset is built for | No |
| `duration_seconds` | INT | For video assets only | Yes |
| `width_px` | INT | Asset width in pixels | Yes |
| `height_px` | INT | Asset height in pixels | Yes |
| `brand` | STRING | Advertiser brand (denormalised) | No |
| `theme_tags` | ARRAY\<STRING\> | Creative theme labels (IAB-aligned) | Yes |
| `created_at` | TIMESTAMP | Upload timestamp | No |

---

#### `transactions` — Mastercard-style purchase feed

Dataplex Zone: **curated-data**

| Column | Type | Description | Nullable |
|--------|------|-------------|----------|
| `txn_id` | STRING (UUID) | Primary key | No |
| `pan_token` | STRING | Tokenised PAN — always populated; primary stable join key | No |
| `cookie_id` | STRING | FK → `cookie_registry.cookie_id` — **~25% populated (see per-market rates)** | Yes |
| `hem` | STRING | Hashed email — **~20% populated (see per-market rates)** | Yes |
| `merchant_name` | STRING | Merchant name | No |
| `merchant_category_code` | STRING(4) | ISO-18245 MCC code | No |
| `brand` | STRING | Resolved brand from merchant | Yes |
| `amount_usd` | DOUBLE | Transaction amount | No |
| `currency_code` | STRING(3) | ISO-4217 | No |
| `country_code` | STRING(2) | Transaction country | No |
| `city` | STRING | Transaction city | Yes |
| `lat` | DOUBLE | Merchant latitude | Yes |
| `lon` | DOUBLE | Merchant longitude | Yes |
| `channel` | STRING | in_store / online / contactless | No |
| `txn_ts` | TIMESTAMP | Transaction timestamp | No |
| `_partition_date` | DATE | Iceberg partition column (day) | No |

---

### 1.3 Scale Parameters

| Table | Row count | Partitioned |
|-------|-----------|-------------|
| `audience` | 8 000 panel participants / ~500 modelled segments | No |
| `cookie_registry` | 80 000 cookies | No |
| `pixel_events` | 2 000 000 events | Yes (day) |
| `campaigns` | ~200 campaigns | No |
| `creatives` | ~1 000 creative assets | No |
| `transactions` | ~500 000 transactions | Yes (day) |

---

### 1.4 Identity Join Keys and Match Rates

```
IDENTITY RESOLUTION GRAPH
==========================
audience (8K panel)
  │
  ├──[hem, 60%]──────────────────────────────────┐
  │                                               │
cookie_registry (80K cookies)                     │
  ├──[audience_id, 40%]──► audience               │
  ├──[hem, 35%]────────────────────────────────── ┤ (same hem pool)
  │                                               │
pixel_events (2M events)                          │
  ├──[cookie_id, 82%]──► cookie_registry          │
  │   (18% cookieless: ITP, iOS, CTV)             │
  │                                               │
transactions (500K)                               │
  ├──[cookie_id, 25%]──► cookie_registry          │
  └──[hem, 20%]────────────────────────────────── ┘

per-market adjustments (applied to txn rates only):
  US: cookie +5pp → 30%, hem +5pp → 25%
  UK: cookie  −5pp → 20%, hem −5pp → 15%
  JP: cookie −10pp → 15%, hem −10pp → 10%
```

| Join key | Tables | Baseline fill rate | Notes |
|----------|--------|--------------------|-------|
| `audience_hem` | audience.hem | 60% | Panel participants with consented email |
| `cookie → audience` | cookie_registry.audience_id | 40% | Cookies resolvable to a modelled segment |
| `cookie → hem` | cookie_registry.hem | 35% | Logged-in / authenticated rate |
| `pixel → cookie` | pixel_events.cookie_id | 82% | ~18% cookieless (ITP, iOS, CTV) |
| `transaction → cookie` | transactions.cookie_id | 25% | US: 30%, UK: 20%, JP: 15% |
| `transaction → hem` | transactions.hem | 20% | US: 25%, UK: 15%, JP: 10% |

`pan_token` is always populated — it is the stable join key within the transactions table.

---

### 1.5 Semantic Synonym Pairs (Dataplex Knowledge Graph)

| Canonical Term | Synonym(s) and location | Physical column? |
|----------------|------------------------|------------------|
| `cookie_id` | `visitor_id` (cookie_registry), `device_id` (cookie_registry) | Yes — both present in table |
| `hashed_email` / `hem` | `hem` (audience, transactions), `hashed_email` (cookie_registry) | Yes — both present in table |
| `brand` | `advertiser` (campaigns) | Yes — both present in table |
| `lat` / `lon` | `location_lat` / `location_lon` (audience) | Yes — both present in table |
| `country_code` | `market` (used in some audience segment label fields) | Partial — `market` in label strings only |

All pairs marked "Yes" have both columns physically present with identical values. This
is intentional — the synonym detection demo requires real data in both columns, not just
a column alias or view.

---

### 1.6 Derived / Calculable Metrics Mapping

| Metric | Funnel stage | Source tables | Derivation |
|--------|-------------|--------------|------------|
| Impressions | Awareness | `pixel_events` | `COUNT(*) WHERE event_type = 'impression'` |
| Reach | Awareness | `pixel_events` | `COUNT(DISTINCT cookie_id) WHERE event_type = 'impression'` |
| Frequency | Awareness | `pixel_events` | `Impressions / Reach` |
| CPM | Awareness | `pixel_events` | `(SUM(spend_usd) / impressions) * 1000` |
| Clicks | Engagement | `pixel_events` | `COUNT(*) WHERE event_type = 'click'` |
| CTR | Engagement | `pixel_events` | `Clicks / Impressions * 100` |
| CPC | Engagement | `pixel_events` | `SUM(spend_usd) / Clicks` |
| VTR | Engagement | `pixel_events` | `COUNT(video_complete) / COUNT(video_start)` |
| Engagement Rate | Engagement | `pixel_events` | `COUNT(engagement) / impressions` |
| Conversions | Conversion | `transactions` JOIN `pixel_events` | Cookie or hem join within attribution window |
| CVR | Conversion | derived | `Conversions / Clicks * 100` |
| CPA | Conversion | derived | `actual_spend_usd / Conversions` |
| ROAS | Conversion | derived | `SUM(amount_usd) / actual_spend_usd` |
| MER | Conversion | derived | `Total Revenue / Total Ad Spend` |
| LTV | Long-term | `transactions` | `SUM(amount_usd) GROUP BY pan_token` |
| CAC | Long-term | `campaigns`, `transactions` | `actual_spend_usd / COUNT(first transactions)` |

---

## Deliverable 2 — Dataplex Knowledge Catalog Metadata

### 2.1 Catalog Topology

```
Dataplex Lake: demo-data  (us-east1)
  ├── Zone: raw-data          (type: RAW,      GCS-backed)
  │     └── Asset: pixel_events Iceberg table
  └── Zone: curated-data      (type: CURATED,  BigLake / Iceberg)
        ├── Asset: audience
        ├── Asset: cookie_registry
        ├── Asset: campaigns
        ├── Asset: creatives
        └── Asset: transactions

Entry Group:
  /projects/wpp-dataproducts-lakehouse/locations/us-east1/entryGroups/marketing-lakehouse

Business Glossary: marketing-glossary
  ├── Term: Audience Segment
  ├── Term: Cookie / Visitor ID     (synonyms: visitor_id, device_id)
  ├── Term: Hashed Email / HEM      (synonyms: hem, hashed_email, email_hash)
  ├── Term: Brand / Advertiser      (synonyms: advertiser)
  ├── Term: Geographic Centroid     (synonyms: lat/lon, location_lat/location_lon)
  ├── Term: Impression
  ├── Term: Conversion
  ├── Term: ROAS
  └── Term: LTV
```

---

### 2.2 Tag Template: `marketing_table_metadata`

```yaml
tag_template_id: marketing_table_metadata
display_name: "Marketing Lakehouse Table Metadata"
fields:
  - id: business_owner
    display_name: "Business Owner"
    type: STRING
    required: true
  - id: data_domain
    display_name: "Data Domain"
    type: ENUM
    enum_values: [audience, identity, activation, transactions, campaigns, creatives]
    required: true
  - id: pii_class
    display_name: "PII Classification"
    type: ENUM
    enum_values: [none, pseudonymous, identified]
    required: true
  - id: refresh_cadence
    display_name: "Refresh Cadence"
    type: ENUM
    enum_values: [once, daily, hourly, streaming]
  - id: row_count_approx
    display_name: "Approximate Row Count"
    type: DOUBLE
  - id: marketing_usecases
    display_name: "Supported Use Cases"
    type: STRING   # comma-separated
```

---

### 2.3 Per-Table Catalog Entries

#### `audience`

```yaml
entry_id: audience
display_name: "Audience Profiles (Panel Model)"
description: >
  Modelled audience segments derived from panel survey data and behavioural signals.
  Each row represents a distinct addressable audience cohort characterised by
  demographics, interests, brand affinity scores, and channel over-index scores.
  The 'hem' column is a SHA-256 hashed email populated for ~60% of records to reflect
  realistic consent rates. The lat/lon and location_lat/location_lon columns carry
  identical centroid values — the duplication is intentional to demonstrate Dataplex
  semantic graph synonym resolution.
tags:
  marketing_table_metadata:
    business_owner: "Marketing Data Products"
    data_domain: audience
    pii_class: pseudonymous
    refresh_cadence: daily
    row_count_approx: 8000
    marketing_usecases: "audience_discovery,audience_performance_prediction"
column_descriptions:
  audience_id: "Surrogate primary key (UUID v4). Stable across refreshes."
  segment_name: "Human-readable cohort label used in campaign planning tools."
  hem: "SHA-256 of normalised email. ~60% populated. Canonical glossary term: Hashed Email / HEM."
  brand_affinity_scores: "MAP of brand → affinity score [0,1]. Higher = stronger affinity."
  channel_index: "MAP of channel → over-index ratio vs population. >1 = over-indexes."
  lat: "Centroid latitude of dominant geo cluster. Synonym: location_lat (same table)."
  lon: "Centroid longitude. Synonym: location_lon (same table)."
  location_lat: "Synonym for lat. Duplicate column to demonstrate semantic synonym resolution."
  location_lon: "Synonym for lon. Duplicate column to demonstrate semantic synonym resolution."
  panel_weight: "Statistical projection weight. Use when scaling segment counts to population estimates."
```

#### `cookie_registry`

```yaml
entry_id: cookie_registry
display_name: "Cookie / Device Identity Registry"
description: >
  Maps cookie identifiers to device metadata, partial hashed email matches, and
  audience segment assignments. Intentionally contains synonym column pairs:
  cookie_id/visitor_id and hem/hashed_email, both with identical values, to
  demonstrate Dataplex semantic graph resolution. ~40% of rows carry an audience_id;
  ~35% carry a hashed email.
tags:
  marketing_table_metadata:
    business_owner: "Marketing Data Products"
    data_domain: identity
    pii_class: pseudonymous
    refresh_cadence: daily
    row_count_approx: 80000
    marketing_usecases: "audience_discovery,post_campaign_analysis"
column_descriptions:
  cookie_id: "Primary identity key. Synonyms: visitor_id (same table), device_id (same table). Glossary term: Cookie / Visitor ID."
  visitor_id: "Synonym for cookie_id. Identical value. Present for semantic graph demo."
  device_id: "Platform-native device identifier. Synonymous with cookie_id for resolution purposes."
  hem: "SHA-256 hashed email. ~35% populated. Synonym: hashed_email (same table). Glossary term: Hashed Email / HEM."
  hashed_email: "Semantic duplicate of hem. Different column name to demonstrate cross-table synonym resolution."
  audience_id: "FK to audience.audience_id. ~40% populated — not all cookies resolve to a modelled segment."
```

#### `pixel_events`

```yaml
entry_id: pixel_events
display_name: "Ad Tracking Pixel Events"
description: >
  Event-level stream of ad tracking signals (impressions, clicks, video engagement
  milestones) captured via tracking pixels across digital channels. Partitioned by
  event date. Supports all awareness, engagement, and conversion funnel metrics.
  cookie_id is absent for ~18% of events to model ITP / cookieless environments.
  spend_usd is the pro-rated CPM cost for impression events; zero for other event types.
tags:
  marketing_table_metadata:
    business_owner: "Marketing Data Products"
    data_domain: activation
    pii_class: pseudonymous
    refresh_cadence: daily
    row_count_approx: 2000000
    marketing_usecases: "post_campaign_analysis,content_performance_prediction,audience_performance_prediction"
column_descriptions:
  event_type: "Controlled vocab: impression | click | video_start | video_q1 | video_q2 | video_q3 | video_complete | engagement."
  cookie_id: "FK to cookie_registry. ~82% populated. Join to cookie_registry for audience enrichment."
  spend_usd: "Media cost attributed to this event. SUM / impressions * 1000 = CPM."
  _partition_date: "Iceberg partition key (day). Always filter on this column for time-range queries."
```

#### `campaigns`

```yaml
entry_id: campaigns
display_name: "Campaign / Flight Metadata"
description: >
  Master record for advertising campaigns. Contains two semantically equivalent
  columns — brand and advertiser — with identical values, intentionally to showcase
  Dataplex synonym detection. Channels and regions are arrays to support multi-market,
  multi-channel flights.
tags:
  marketing_table_metadata:
    business_owner: "Marketing Data Products"
    data_domain: campaigns
    pii_class: none
    refresh_cadence: daily
    row_count_approx: 200
    marketing_usecases: "post_campaign_analysis,audience_discovery"
column_descriptions:
  brand: "Advertiser brand name. Synonym: advertiser (same table). Glossary term: Brand / Advertiser."
  advertiser: "Semantic duplicate of brand. Identical value. Present for synonym resolution demo."
  objective: "Campaign goal: awareness | consideration | conversion | retention."
  actual_spend_usd: "Realised spend. May differ from budget_usd. Use for ROAS and CPA calculations."
```

#### `creatives`

```yaml
entry_id: creatives
display_name: "Creative / Content Asset Library"
description: >
  Catalogue of ad creative assets linked to campaigns. Supports content performance
  prediction by pairing asset metadata with pixel_events.creative_id. Each creative
  belongs to exactly one campaign.
tags:
  marketing_table_metadata:
    business_owner: "Marketing Data Products"
    data_domain: creatives
    pii_class: none
    refresh_cadence: once
    row_count_approx: 1000
    marketing_usecases: "content_performance_prediction"
column_descriptions:
  format: "Controlled vocab: video_15s | video_30s | static_banner | carousel | stories."
  duration_seconds: "Populated for video formats only. Used to calculate VTR thresholds."
  theme_tags: "IAB-aligned creative theme labels. Supports content-based similarity queries."
```

#### `transactions`

```yaml
entry_id: transactions
display_name: "Transactional Purchase Feed (Mastercard-style)"
description: >
  Synthetic purchase transaction feed modelled on Mastercard merchant data. Represents
  purchase events that may or may not link to an ad exposure via cookie_id or hem.
  cookie_id is populated at market-specific rates (US: 30%, UK: 20%, JP: 15%);
  hem at (US: 25%, UK: 15%, JP: 10%). The pan_token is a tokenised non-reversible
  payment card reference used for LTV and CAC calculations. Partitioned by date.
tags:
  marketing_table_metadata:
    business_owner: "Marketing Data Products"
    data_domain: transactions
    pii_class: pseudonymous
    refresh_cadence: daily
    row_count_approx: 500000
    marketing_usecases: "post_campaign_analysis,audience_discovery"
column_descriptions:
  pan_token: "Non-reversible tokenised PAN. Always populated. Used for LTV aggregation. Does NOT link to real card data."
  cookie_id: "FK to cookie_registry. Market-specific fill rates (US 30%, UK 20%, JP 15%). Join via hem as fallback."
  hem: "SHA-256 hashed email. Market-specific fill rates (US 25%, UK 15%, JP 10%). Glossary term: Hashed Email / HEM."
  merchant_category_code: "ISO-18245 MCC. 4-digit string. Use for product-category conversion analysis."
  amount_usd: "Transaction value in USD. Use SUM for revenue in ROAS and MER calculations."
  _partition_date: "Iceberg partition key (day). Always filter on this column."
```

---

## Deliverable 3 — Synthetic Data Generator Design

### 3.1 Technology Stack

```
Python 3.11+
├── faker           — realistic names, emails, cities, coordinates
├── pyiceberg       — Iceberg table creation and appending
├── pyarrow         — in-memory columnar data, schema enforcement
├── numpy           — controlled stochastic match rates, distributions
├── pydantic v2     — generator config validation
└── google-cloud-storage — GCS writes for Iceberg warehouse
```

### 3.2 Generator Architecture

```
generators/
├── config.py           # GeneratorConfig pydantic model
├── base.py             # BaseGenerator: schema, faker setup, seed control
├── audience.py         # AudienceGenerator
├── cookie_registry.py  # CookieRegistryGenerator     (depends on: audience IDs)
├── campaigns.py        # CampaignGenerator            (independent)
├── creatives.py        # CreativeGenerator            (depends on: campaign IDs)
├── pixel_events.py     # PixelEventGenerator          (depends on: cookie + campaign + creative IDs)
├── transactions.py     # TransactionGenerator         (depends on: cookie IDs, hems)
└── orchestrator.py     # Runs all generators in dependency order
```

### 3.3 GeneratorConfig

```python
from pydantic import BaseModel, Field
from typing import dict as Dict

class MarketMatchRates(BaseModel):
    txn_cookie_fill_rate: float
    txn_hem_fill_rate: float

class GeneratorConfig(BaseModel):
    seed: int = 42
    target_markets: list[str] = ["US", "GB", "JP"]

    # Scale (matches Agent.md spec)
    n_audience_participants: int = 8_000
    n_audience_segments: int = 500
    n_cookies: int = 80_000
    n_campaigns: int = 200
    n_creatives_per_campaign: int = 5      # ~1 000 total
    n_pixel_events: int = 2_000_000
    n_transactions: int = 500_000
    date_range_days: int = 365

    # Match-rate controls — baseline rates
    audience_hem_fill_rate: float = 0.60
    cookie_audience_fill_rate: float = 0.40
    cookie_hem_fill_rate: float = 0.35
    pixel_cookie_fill_rate: float = 0.82
    txn_cookie_fill_rate: float = 0.25     # baseline; overridden per market
    txn_hem_fill_rate: float = 0.20        # baseline; overridden per market

    # Per-market overrides for transaction join rates
    # US: baseline +5pp, UK: baseline −5pp, JP: baseline −10pp
    market_txn_rates: Dict[str, MarketMatchRates] = {
        "US": MarketMatchRates(txn_cookie_fill_rate=0.30, txn_hem_fill_rate=0.25),
        "GB": MarketMatchRates(txn_cookie_fill_rate=0.20, txn_hem_fill_rate=0.15),
        "JP": MarketMatchRates(txn_cookie_fill_rate=0.15, txn_hem_fill_rate=0.10),
    }

    # Iceberg / GCS output
    iceberg_warehouse: str = "gs://wpp-dataproducts-lakehouse-warehouse/iceberg"
    iceberg_namespace: str = "marketing"
    biglake_connection: str = "projects/wpp-dataproducts-lakehouse/locations/us-east1/connections/biglake-conn"
```

### 3.4 Generation Order (dependency DAG)

```
1. audience          → produces: audience_ids[], hems_pool[]
2. campaigns         → produces: campaign_ids[]
3. creatives         → depends on: campaign_ids[]
                     → produces: creative_ids[]
4. cookie_registry   → depends on: audience_ids[], hems_pool[]
                     → produces: cookie_ids[], cookie_hems[]
5. pixel_events      → depends on: cookie_ids[], campaign_ids[], creative_ids[]
6. transactions      → depends on: cookie_ids[], cookie_hems[], per-market rates
```

Steps 2 and 3 (campaigns → creatives) can run in parallel with step 1 (audience).
Steps 4–6 are sequential.

### 3.5 Key Generator Behaviours

**Match rates**: Each FK column is filled using `numpy.random.choice` with the configured
fill rate, then remaining rows receive `None`. Join success rates are verifiable after
generation via the `--validate` command.

**Per-market transaction rates**: `TransactionGenerator` receives the market for each
row and looks up the appropriate `MarketMatchRates` override from `GeneratorConfig`.
This produces realistic variation without post-hoc patching.

**Semantic synonym columns**: Written at generation time, not derived at query time.
`cookie_registry` writes `cookie_id` and `visitor_id` with identical values; `hem` and
`hashed_email` with identical values. `campaigns` writes `brand` and `advertiser`.
`audience` writes `lat`/`location_lat` and `lon`/`location_lon` with identical values.

**Time distribution**: Events follow a weekday-weighted distribution. Pixel events are
only generated within the `start_date`..`end_date` window of the referenced campaign.
Transactions are distributed across the full date range.

**Geographic realism**: `faker.local_latlng(country_code=market)` provides realistic
lat/lon per market. Audience segment centroids are offset by a small Gaussian noise
(σ ≈ 0.5°) to represent a geographic cluster rather than a single point.

**Batched writes**: `pixel_events` and `transactions` are written in batches of 200 000
rows to bound peak memory usage. Target: full generation in under 5 minutes on a 4-core
machine with 16 GB RAM.

**Iceberg output**: Each table is written via `pyiceberg`. `pixel_events` and
`transactions` are partitioned by `_partition_date` (day). All other tables are
unpartitioned.

---

## Deliverable 4 — Ingestion and Catalog Registration Utilities

### 4.1 Module Layout

```
ingestion/
├── iceberg_writer.py    # Write + register BigLake Iceberg tables via pyiceberg
├── bq_external.py       # Register Iceberg tables as BigLake external tables in BQ
├── dataplex_lake.py     # Create/update Dataplex Lake, Zones, Asset registrations
├── catalog.py           # Register catalog entries in the Entry Group
├── tag_writer.py        # Apply marketing_table_metadata tag template to entries
├── glossary_writer.py   # Create Business Glossary terms and synonym graph links
└── cli.py               # Typer-based CLI (see 4.4)
```

### 4.2 Ingestion Pipeline

```
Step 1  Ensure GCS warehouse bucket exists                (iceberg_writer.py)
Step 2  Write Iceberg tables from generator output        (iceberg_writer.py)
Step 3  Register BigLake external tables in BigQuery      (bq_external.py)
Step 4  Create Dataplex Lake + Zones (demo-data)          (dataplex_lake.py)
Step 5  Register GCS/BQ assets in Dataplex Zones          (dataplex_lake.py)
Step 6  Create catalog Entry Group (if absent)            (catalog.py)
Step 7  Register per-table catalog entries                (catalog.py)
Step 8  Apply marketing_table_metadata tags               (tag_writer.py)
Step 9  Create Business Glossary terms                    (glossary_writer.py)
Step 10 Link synonym terms in the knowledge graph         (glossary_writer.py)
Step 11 Run validation checks                             (cli.py --validate)
```

### 4.3 Validation Checks

| Check | Query / assertion |
|-------|-------------------|
| Row counts match config | `SELECT COUNT(*) FROM {table}` vs config values |
| Pixel events within campaign dates | `JOIN pixel_events + campaigns ON campaign_id; assert event_ts BETWEEN start_date AND end_date` |
| pixel→cookie fill rate within ±3pp | `SELECT COUNT(cookie_id)/COUNT(*) FROM pixel_events` |
| cookie→audience fill rate within ±3pp | `SELECT COUNT(audience_id)/COUNT(*) FROM cookie_registry` |
| No orphan creative_ids in pixel_events | `LEFT JOIN creatives; assert no unmatched creative_id` |
| txn→cookie fill rates within ±3pp per market | `SELECT market, COUNT(cookie_id)/COUNT(*) FROM transactions GROUP BY market` |
| txn→hem fill rates within ±3pp per market | same, for hem |
| Synonym columns have identical values | `SELECT COUNT(*) FROM cookie_registry WHERE cookie_id != visitor_id` → 0 |
| Iceberg snapshot valid | `pyiceberg table.scan().to_arrow()` on each table |
| All catalog entries registered | Dataplex entries API list vs expected entry_ids |
| All tag templates applied | Dataplex tags API list vs table list |
| Business Glossary terms visible | Dataplex Catalog API — assert synonym links present |

### 4.4 CLI Interface

```bash
# Generate + write Iceberg tables + register all catalog metadata
python -m ingestion.cli ingest --config config.yaml

# Generate only — write Parquet to ./local_output, skip Iceberg/GCS
python -m ingestion.cli generate --config config.yaml --local

# Register metadata only (tables already exist in GCS)
python -m ingestion.cli catalog --config config.yaml

# Validate after ingestion
python -m ingestion.cli validate --config config.yaml

# Tear down all resources and re-ingest (destructive, requires --confirm)
python -m ingestion.cli reset --config config.yaml --confirm
```

---

## Implementation Task List

| # | Task | Deliverable | Depends on | Notes |
|---|------|------------|------------|-------|
| T1 | Set up `pyproject.toml` + dev environment | project | — | faker, pyiceberg, pyarrow, pydantic, typer, google-cloud-{storage,bigquery,dataplex} |
| T2 | Implement `GeneratorConfig` + `BaseGenerator` | D3 | T1 | Pin seed; validate market_txn_rates keys match target_markets |
| T3 | Implement `AudienceGenerator` | D3 | T2 | Include location_lat/location_lon synonym columns |
| T4 | Implement `CampaignGenerator` + `CreativeGenerator` | D3 | T2 | Can run in parallel with T3 |
| T5 | Implement `CookieRegistryGenerator` | D3 | T3 | Depends on audience_ids pool |
| T6 | Implement `PixelEventGenerator` | D3 | T4, T5 | Batch writes; respect campaign date windows |
| T7 | Implement `TransactionGenerator` | D3 | T5 | Per-market cookie/hem rates from config |
| T8 | Implement `orchestrator.py` | D3 | T3–T7 | Runs full DAG; passes ID pools between generators |
| T9 | Implement `iceberg_writer.py` | D4 | T1 | BigLake Iceberg via pyiceberg; partitioned tables |
| T10 | Implement `bq_external.py` | D4 | T9 | Register BigLake external tables; uses biglake-conn |
| T11 | Implement `dataplex_lake.py` | D4 | T9 | Create demo-data lake, raw-data + curated-data zones, assets |
| T12 | Implement `catalog.py` + `tag_writer.py` | D4 | T11 | Entry Group marketing-lakehouse; per-table entries + tags |
| T13 | Implement `glossary_writer.py` | D4 | T12 | Terms + synonym graph links; key demo feature |
| T14 | Implement `cli.py` + `--validate` checks | D4 | T8–T13 | All five subcommands; ±3pp match-rate assertions |
| T15 | Local end-to-end test (`--local` mode) | testing | T14 | Validates schemas, row counts, synonym column equality |
| T16 | GCP end-to-end ingestion | deploy | T15 | Requires GCP access + pre-provisioned infra (see below) |

### Infrastructure Pre-requisites (must exist before T16)

1. **GCS bucket** — warehouse bucket in `us-east1` with uniform bucket-level IAM
2. **BigLake connection** — `projects/wpp-dataproducts-lakehouse/locations/us-east1/connections/biglake-conn`
3. **BigQuery dataset** — `wpp-dataproducts-lakehouse.marketing` in `us-east1`
4. **Dataplex Lake** — `demo-data` in `us-east1`
5. **Dataplex Zones** — `raw-data` (RAW) and `curated-data` (CURATED) under `demo-data`
6. **IAM roles** for the service account:
   - `roles/bigquery.dataEditor`
   - `roles/bigquery.connectionAdmin`
   - `roles/dataplex.editor`
   - `roles/storage.objectAdmin`

---

## NOT In Scope

| Item | Rationale |
|------|-----------|
| Terraform / IaC for infra provisioning | Infra is pre-provisioned; ingestion utilities assume resources exist |
| Real-time / streaming data generation | Demo is batch-only; streaming adds significant complexity for no demo value |
| BigQuery authorised views or row-level security | PII classification is pseudonymous; access control is out of scope for a demo |
| Multi-region deployment | `us-east1` only, per spec |
| Data refresh scheduling (Cloud Scheduler, Composer) | One-shot ingestion is sufficient for a demo |
| ML model training on the synthetic data | Metrics are derivable via SQL; no ML pipeline needed |

---

## What Already Exists

| Item | Status | Reuse |
|------|--------|-------|
| `pyproject.toml` | Already staged (git status shows AM) | Extend with new dependencies |
| GCP project `wpp-dataproducts-lakehouse` | Pre-provisioned | Target for all writes |
| `Agent.md` requirements | Complete | Source of truth for all schemas and rates |

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (PLAN) | 0 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**VERDICT:** ENG CLEARED — ready to implement.
