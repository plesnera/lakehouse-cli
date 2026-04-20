# Creative / Content Asset Library

Catalogue of ad creative assets linked to campaigns. Supports content performance prediction by pairing asset metadata with pixel_events.creative_id. Each creative belongs to exactly one campaign.

## Tags
- business_owner: Marketing Data Products
- data_domain: creatives
- pii_class: none
- refresh_cadence: once
- row_count_approx: 1000
- marketing_usecases: content_performance_prediction

## Columns

- creative_id: Primary key (UUID v4). Referenced by pixel_events.creative_id.
- campaign_id: FK to campaigns.campaign_id. Each creative belongs to one campaign.
- creative_name: Asset label combining brand, format, and sequence identifiers.
- format: Controlled vocab: video_15s | video_30s | static_banner | carousel | stories.
- channel: Channel this asset is built for (meta, youtube, tiktok, display, ctv, search).
- duration_seconds: Populated for video formats only. Used to calculate VTR thresholds.
- width_px: Asset width in pixels.
- height_px: Asset height in pixels.
- brand: Advertiser brand (denormalised from campaigns for convenience).
- theme_tags: IAB-aligned creative theme labels. Supports content-based similarity queries.
- created_at: Upload timestamp for the creative asset.

## Data Quality Rules
- creative_id: non_null
- campaign_id: non_null
