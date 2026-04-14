# Marketing Business Glossary

Standardised vocabulary for the Marketing Lakehouse data estate.
This glossary enables Dataplex Knowledge Graph semantic discovery and
cross-channel attribution by defining canonical terms and their synonym
relationships.

## Category: Identity

Terms related to user and device identity resolution.

- **cookie_id**
  - Synonyms: visitor_id, device_id
  - Description: Unique identifier for a browser or device session. The canonical key for cross-site tracking and identity resolution within the marketing identity graph.
  - Tables: cookie_registry, pixel_events
  - Business Context: Identity resolution

- **hashed_email**
  - Synonyms: hem
  - Description: SHA-256 hash of a normalised, lowercased email address. Privacy-preserving identifier that enables cross-channel attribution without exposing PII.
  - Tables: audience, cookie_registry, transactions
  - Business Context: Cross-channel attribution

## Category: Campaign

Terms related to advertising campaigns and brand management.

- **brand**
  - Synonyms: advertiser
  - Description: The advertiser brand name funding a campaign. Used as the primary commercial entity across campaign planning and reporting.
  - Tables: campaigns
  - Business Context: Campaign ownership

- **country_code**
  - Synonyms: market
  - Related: region
  - Description: ISO 3166-1 alpha-2 country code identifying the geographic market of a campaign, audience segment, or transaction.
  - Tables: campaigns, audience, transactions
  - Business Context: Market segmentation

## Category: Geography

Terms related to geospatial and location data.

- **lat**
  - Synonyms: location_lat
  - Description: WGS-84 latitude coordinate of an audience segment geographic centroid. Used for regional targeting and location-based insights.
  - Tables: audience
  - Business Context: Geographic targeting

- **lon**
  - Synonyms: location_lon
  - Description: WGS-84 longitude coordinate of an audience segment geographic centroid. Used for regional targeting and location-based insights.
  - Tables: audience
  - Business Context: Geographic targeting

## Category: Marketing Metrics

Terms related to marketing performance measurement and attribution.

- **audience_segment**
  - Description: A modelled audience cohort characterised by demographics, interests, and behavioural signals. Derived from panel survey data.
  - Tables: audience
  - Business Context: Audience discovery and campaign targeting

- **impression**
  - Related: reach, frequency, cpm
  - Description: A single instance of an ad being served to a user. Counted via pixel_events where event_type = 'impression'.
  - Tables: pixel_events
  - Business Context: Top-of-funnel awareness measurement

- **conversion**
  - Related: cvr, cpa, roas
  - Description: A purchase transaction attributed to an ad exposure via cookie_id or hem join within an attribution window.
  - Tables: transactions, pixel_events
  - Business Context: Bottom-of-funnel performance measurement

- **roas**
  - Related: conversion, mer
  - Description: Return On Ad Spend. Calculated as SUM(transaction amount_usd) / actual_spend_usd. The primary efficiency metric for campaign performance.
  - Tables: transactions, campaigns, pixel_events
  - Business Context: Campaign efficiency and budget optimisation

- **ltv**
  - Related: cac
  - Description: Lifetime Value. Calculated as SUM(amount_usd) per pan_token over the full transaction history. Used for long-term customer value assessment.
  - Tables: transactions
  - Business Context: Long-term customer value and acquisition strategy
