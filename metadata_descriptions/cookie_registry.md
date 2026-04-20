# Cookie / Device Identity Registry

Maps cookie identifiers to device metadata, partial hashed email matches, and audience segment assignments. Intentionally contains synonym column pairs: cookie_id/visitor_id and hem/hashed_email, both with identical values, to demonstrate Dataplex semantic graph resolution. ~40% of rows carry an audience_id; ~35% carry a hashed email.

## Tags
- business_owner: Marketing Data Products
- data_domain: identity
- pii_class: pseudonymous
- refresh_cadence: daily
- row_count_approx: 80000
- marketing_usecases: audience_discovery,post_campaign_analysis

## Columns

- cookie_id: Primary identity key. Synonyms: visitor_id (same table), device_id (same table). Glossary term: Cookie / Visitor ID.
- visitor_id: Synonym for cookie_id. Identical value. Present for semantic graph demo.
  - Synonym Of: cookie_id
- device_id: Platform-native device identifier. Synonymous with cookie_id for resolution purposes.
  - Synonym Of: cookie_id
- audience_id: FK to audience.audience_id. ~40% populated — not all cookies resolve to a modelled segment.
- hem: SHA-256 hashed email. ~35% populated. Synonym: hashed_email (same table). Glossary term: Hashed Email / HEM.
- hashed_email: Semantic duplicate of hem. Different column name to demonstrate cross-table synonym resolution.
  - Synonym Of: hem
- country_code: ISO 3166-1 alpha-2 observed market.
- city: Resolved city based on IP geolocation.
- lat: Last known latitude of the device.
- lon: Last known longitude of the device.
- device_type: Device category: desktop | mobile | tablet | ctv.
- browser: Browser or app identifier: Chrome | Safari | Firefox | App | Unknown.
- first_seen_at: Timestamp of first observation for this cookie.
- last_seen_at: Timestamp of most recent observation.

## Data Quality Rules
- cookie_id: non_null
- audience_id: non_null threshold=0.37
- hem: non_null threshold=0.32
