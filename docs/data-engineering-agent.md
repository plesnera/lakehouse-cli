# BigQuery Data Engineering Agent — Setup Guide

This guide explains how to use BigQuery Data Engineering Agent with the metadata pipeline in this repository.

## Purpose

This project does not create data tables itself; it manages catalog metadata, glossary terms, and governance context so the Data Engineering Agent can reason over existing tables more effectively.

Reference:
- https://cloud.google.com/bigquery/docs/data-engineering-agent-pipelines

## Prerequisites

1. The target BigQuery dataset (default: `marketing`) already contains the six expected tables:
   - `audience`
   - `cookie_registry`
   - `campaigns`
   - `creatives`
   - `pixel_events`
   - `transactions`
2. A Lakehouse REST catalog already exists.
3. You have permission to run Dataplex and BigQuery metadata operations.

## Recommended preparation workflow

Run these steps before using the Data Engineering Agent in BigQuery Studio:

```bash
# 1) Verify catalog + namespace
uv run python -m ingestion.cli setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full

# 2) Register Dataplex assets, entries, tags, and glossary
uv run python -m ingestion.cli catalog \
  --catalog-name YOUR_CATALOG_NAME

# 3) Apply table/column descriptions
uv run python -m ingestion.cli enrich-metadata

# 4) Ensure glossary links are applied
uv run python -m ingestion.cli manage-glossary --action apply
```

## Example prompts

### Audience discovery
```
Find US audience segments that over-index on Meta and have high income. Return segment_name, age_band, and brand_affinity_scores.
```

### Campaign performance pipeline
```
Build a pipeline that joins campaigns and pixel_events to calculate impressions, clicks, CTR, and spend by campaign for completed campaigns.
```

### Cross-channel attribution
```
Create a pipeline that attributes transactions to ad exposures using cookie_id first and hem as fallback within a 30-day window. Return ROAS by campaign and market.
```

### Semantic discovery
```
Which tables contain visitor or advertiser data, and how should they be joined?
```

## Metadata signals used by the agent

The agent benefits from:
- Dataplex catalog entries (table descriptions and display names)
- Applied tags from `metadata/*.yaml`
- Business glossary term links from `metadata/glossary.yaml`
- Column descriptions applied by `enrich-metadata`

Better metadata coverage generally improves SQL generation quality and reduces schema ambiguity.