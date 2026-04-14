# Audience Segmentation Data

This table contains detailed audience segmentation information for marketing analysis. It includes demographic data, interest scores, and geographic information for 8,000 panel participants. Used for audience discovery, lookalike modeling, and campaign targeting.

## Columns

- audience_id: Unique identifier for each audience segment participant
- segment_name: The name of the audience segment this participant belongs to
- country_code: ISO 3166-1 alpha-2 country code for the participant's location
- region: State, province, or administrative region within the country
- age_band: Age range category (e.g., 18-24, 25-34, etc.)
- gender: Participant's gender identity
- income_band: Household income range category
- interests: Comma-separated list of participant's interests and hobbies
- brand_affinity_scores: JSON object containing affinity scores for various brands
- channel_index: Index showing which marketing channels this audience responds best to
- hem: Hashed email identifier for privacy-preserving identity resolution
- lat: Latitude coordinate for geographic analysis and targeting
- lon: Longitude coordinate for geographic analysis and targeting