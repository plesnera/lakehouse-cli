# Campaign / Flight Metadata

Master record for advertising campaigns. Contains two semantically equivalent columns — brand and advertiser — with identical values, intentionally to showcase Dataplex synonym detection. Channels and regions are arrays to support multi-market, multi-channel flights.

## Tags
- business_owner: Marketing Data Products
- data_domain: campaigns
- pii_class: none
- refresh_cadence: daily
- row_count_approx: 200
- marketing_usecases: post_campaign_analysis,audience_discovery

## Columns

- campaign_id: Primary key (UUID v4). Used as FK in pixel_events and creatives.
- campaign_name: Human-readable campaign name combining brand, product category and sequence.
- brand: Advertiser brand name. Synonym: advertiser (same table). Glossary term: Brand / Advertiser.
- advertiser: Semantic duplicate of brand. Identical value. Present for synonym resolution demo.
  - Synonym Of: brand
- product_category: IAB product category for the campaign (e.g. Apparel, Beauty, CPG, Tech).
- country_code: ISO 3166-1 alpha-2 code for the primary market.
- regions: Target regions within the market (array of administrative units).
- channels: Activated channels for this campaign (meta, youtube, tiktok, display, ctv, search).
- objective: Campaign goal: awareness | consideration | conversion | retention.
- budget_usd: Total approved budget in US dollars.
- actual_spend_usd: Realised spend. May differ from budget_usd. Use for ROAS and CPA calculations.
- start_date: Flight start date.
- end_date: Flight end date.
- status: Lifecycle state: planned | active | completed | paused.
- created_at: Record creation timestamp.
