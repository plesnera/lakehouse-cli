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
