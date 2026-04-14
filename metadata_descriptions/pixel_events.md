# Ad Tracking Pixel Events

Event-level stream of ad tracking signals (impressions, clicks, video engagement milestones) captured via tracking pixels across digital channels. Partitioned by event date. Supports all awareness, engagement, and conversion funnel metrics. cookie_id is absent for ~18% of events to model ITP / cookieless environments. spend_usd is the pro-rated CPM cost for impression events; zero for other event types.

## Tags
- business_owner: Marketing Data Products
- data_domain: activation
- pii_class: pseudonymous
- refresh_cadence: daily
- row_count_approx: 2000000
- marketing_usecases: post_campaign_analysis,content_performance_prediction,audience_performance_prediction

## Columns

- event_id: Primary key (UUID v4) for each individual tracking event.
- event_type: Controlled vocab: impression | click | video_start | video_q1 | video_q2 | video_q3 | video_complete | engagement.
- cookie_id: FK to cookie_registry. ~82% populated. Join to cookie_registry for audience enrichment.
- campaign_id: FK to campaigns.campaign_id. Always populated.
- creative_id: FK to creatives.creative_id. Always populated.
- channel: Channel where the event occurred (meta, youtube, tiktok, display, ctv, search).
- placement: Ad placement / format hint (feed, sidebar, pre-roll, mid-roll, search_results).
- country_code: ISO 3166-1 alpha-2 geo of the event.
- region: Sub-national administrative region.
- lat: Event latitude. ~50% populated.
- lon: Event longitude. ~50% populated.
- device_type: Device category: desktop | mobile | tablet | ctv.
- spend_usd: Media cost attributed to this event. SUM / impressions * 1000 = CPM.
- event_ts: Timestamp when the event occurred.
- event_date: Date of the event (derived from event_ts).
- partition_date: Iceberg partition key (day). Always filter on this column for time-range queries.
