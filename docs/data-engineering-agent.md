# BigQuery Data Engineering Agent — Setup Guide

The BigQuery Data Engineering Agent is an AI-powered service that builds and
self-heals data pipelines via natural language prompts. This document describes
how to use it with the marketing lakehouse demo data.

Ref: https://cloud.google.com/bigquery/docs/data-engineering-agent-pipelines

## Prerequisites

1. The `marketing` dataset must exist in `wpp-dataproducts-lakehouse` with all
   six tables ingested and registered.
2. Catalog metadata (descriptions, tags, glossary) must be applied — the agent
   uses this metadata to understand the schema.
3. The BigQuery Data Engineering Agent must be enabled on your project (via
   the BigQuery console or API).

## Enabling the Agent

1. Navigate to **BigQuery Studio** in the Google Cloud Console.
2. Open the `marketing` dataset.
3. Click **Data Engineering Agent** in the left panel (or access via the
   BigQuery API if using the programmatic interface).
4. The agent will automatically discover tables registered in the dataset.

## Example Prompts

These prompts are designed to work with the synthetic marketing data and
demonstrate the agent's ability to discover schemas via the Knowledge Catalog:

### Audience Discovery
```
Find all audience segments in the US market that over-index on the
"meta" channel and have an income band of "High". Show their segment
names, age bands, and brand affinity scores.
```

### Campaign Performance
```
Build a pipeline that joins campaigns to pixel_events and calculates
CTR, CPC, and total spend for each campaign. Include only completed
campaigns. Materialise the results as a new table called
campaign_performance_summary.
```

### Cross-Channel Attribution
```
Create a pipeline that attributes transactions to ad exposures.
Join transactions to pixel_events using cookie_id (primary) and
hem/hashed_email (fallback) within a 30-day attribution window.
Calculate ROAS per campaign and market.
```

### Semantic Discovery
```
Which tables contain "visitor" or "advertiser" data? Show me the
relevant columns and how they join to other tables.
```

The agent should resolve "visitor" to `cookie_registry.visitor_id` (synonym for
`cookie_id`) and "advertiser" to `campaigns.advertiser` (synonym for `brand`)
via the Business Glossary synonym links.

### LTV Analysis
```
Build a customer lifetime value pipeline. Group transactions by
pan_token, calculate total spend, transaction count, and first
purchase date. Flag high-value customers (top 10% by lifetime spend).
```

## Metadata That Powers the Agent

The agent relies on these metadata layers (all set up by the ingestion pipeline):

- **Catalog entries** with display names and descriptions (`catalog.py`)
- **Tag template** `marketing_table_metadata` with business_owner, data_domain,
  pii_class, refresh_cadence, row_count_approx (`tag_writer.py`)
- **Business Glossary** with synonym links: cookie_id↔visitor_id,
  hem↔hashed_email, brand↔advertiser, lat↔location_lat (`glossary_manager.py`)
- **Column descriptions** from `metadata/*.yaml` applied via
  `enrich-metadata` command

The richer the metadata, the better the agent performs at schema discovery and
SQL generation.
