# Lakehouse Data Model and Content Demo

## Purpose

This project has together with The Google Cloud Project `wpp-dataproducts-lakehouse` and been created to demonstrate the functionality of a Google Cloud Lakehouse.
The specific goals of this project are the following:
* To generate synthetic marketing data for a demo. 
* Create the necessary utilities to ingest data in the Apache Icerberg format into a lake (the 'marketing" lake for this demo).
* Demonstrate the following Dataplex services in use on the synthetic data:
  * Create a Lakehouse Metastore Catalogue: Ensures that the different processing engines such as BigQuery and Apache Spark can utilize the same data with same governance and without transforming it: https://docs.cloud.google.com/biglake/docs/biglake-console)  
  * Automated Data Insights Generation: Generates natural language summaries and column descriptions to help agents understand schema context (https://docs.cloud.google.com/bigquery/docs/data-insights#generate-column-table-descriptions)
  * Automated Profiling of Data: Scans data to identify statistical distributions and potential anomalies, providing agents with "grounding" context regarding data health (https://docs.cloud.google.com/dataplex/docs/data-profiling-overview)
  * Knowledge Catalog (Dataplex): The unified repository for metadata, providing agents with a semantic map of the entire data estate (https://docs.cloud.google.com/dataplex/docs/catalog-overview#catalog-model)
  * BigLake Unified Storage: Enables agents to interact with data in open formats (like Iceberg or Parquet) across multi-cloud environments with unified security (https://cloud.google.com/bigquery/docs/biglake-intro)
  * BigQuery Vector Search: The "retrieval" engine for agents; allows for semantic similarity searches and Retrieval-Augmented Generation (RAG) at scale (https://cloud.google.com/bigquery/docs/vector-search-intro)
  * Dataplex Data Quality: Automatically executes quality checks to ensure agents are only making decisions based on "Gold-standard" data (https://docs.cloud.google.com/dataplex/docs/data-quality-overview)
  * BigQuery Data Engineering Agent: An AI-powered service that builds and self-heals data pipelines via natural language prompts (https://cloud.google.com/bigquery/docs/data-engineering-agent-pipelines)
  * BigQuery ML (Remote Models & Gemini): Allows agents to invoke Gemini models directly within SQL queries to process unstructured text or generate embeddings (https://cloud.google.com/bigquery/docs/generate-text-tutorial)
  * BigQuery Continuous Queries: Enables event-driven ingestion and real-time processing, allowing agents to respond to data changes as they happen (https://cloud.google.com/bigquery/docs/continuous-queries)
  * Dataform for Agentic Pipelines: A framework for managing SQL-based transformations that agents can programmatically update to evolve data models (https://cloud.google.com/dataform/docs/overview)
* Develop MVP code utilities that accelerates enablement of the above services such as batch generation and loading of metadata and glossary data.

Dataform for Agentic Pipelines: A framework for managing SQL-based transformations that agents can programmatically update to evolve data models.
---

## Infrastructure Configuration

| Parameter | Value |
|-----------|-------|
| GCP Project | `wpp-dataproducts-lakehouse` |
| Region | `us-east1` |
| Iceberg table format | BigLake Iceberg tables (docs: https://docs.cloud.google.com/bigquery/docs/biglake-iceberg-tables-in-bigquery) |
| GCS warehouse bucket | `gs://{project-id}-warehouse/iceberg/` |
| Dataplex Lake name | `demo-data` |
| Dataplex Zone | `curated-data` (CURATED) — single-zone light approach |
| Catalog Entry Group | `marketing-lakehouse` |
| Business Glossary | `marketing-glossary` |

### Architecture Approach

This demo uses a **lightweight single-zone architecture**:

- **No RAW zone**: Data is generated as synthetic Iceberg tables and registered directly in BigQuery as BigLake external tables. There is no separate "landing" or "raw" storage layer.
- **Single CURATED zone**: The BigQuery dataset (`marketing`) is registered as a Dataplex asset in the `curated-data` zone. All tables are queryable via BigQuery immediately after ingestion.
- **Simplified pipeline**: Data flows directly: Generator → Iceberg (GCS) → BigLake → BigQuery → Dataplex Catalog

This approach reduces complexity and storage costs while still demonstrating all Dataplex features (Data Quality, Profiling, Catalog, Business Glossary). For production workloads requiring data lineage, recovery, or transformation pipelines, consider implementing a full RAW/CURATED zone separation with Dataform or Cloud Composer.

### BigQuery Tables

After ingestion, the following tables are available in BigQuery:

| Table | Dataset | Description |
|-------|---------|-------------|
| `audience` | `marketing` | Modelled audience segments from panel data |
| `cookie_registry` | `marketing` | Device/cookie identity map |
| `campaigns` | `marketing` | Campaign and flight metadata |
| `creatives` | `marketing` | Creative asset library |
| `pixel_events` | `marketing` | Ad tracking pixel events |
| `transactions` | `marketing` | Purchase transaction feed |

### Infrastructure Pre-requisites

The following resources must exist before ingestion utilities are run:

1. **GCS bucket** — warehouse bucket in `us-east1` with uniform bucket-level IAM
2. **BigLake connection** — `projects/wpp-dataproducts-lakehouse/locations/us-east1/connections/biglake-conn`
3. **BigQuery dataset** — `wpp-dataproducts-lakehouse.marketing` in `us-east1`
4. **Dataplex Lake** — `demo-data` in `us-east1`
5. **Dataplex Zone** — `curated-data` (CURATED) under `demo-data`
6. **IAM roles** required by the service account running ingestion:
   - `roles/bigquery.dataEditor`
   - `roles/bigquery.connectionAdmin`
   - `roles/dataplex.editor`
   - `roles/storage.objectAdmin`

---

## Target Markets and Brands

| Parameter | Values |
|-----------|--------|
| Markets | US, UK, Japan |
| Fictional brands | Lucky Cola, Force Automotive, AEKI Living |
| Per-market match-rate variation | US baseline, UK −5pp, Japan −10pp on all cookie/hem join rates |

---

## Use Cases

The data model must support the following marketing use cases:

### Audience Discovery
A brand planning to launch a new product in a market queries panel data to find which audience traits over-index with their product, characterises the audience by demographics and interests, determines geographic concentration, and identifies the strongest channels (Meta, YouTube, TikTok).

### Audience Performance Prediction
Given an identified audience segment, predict average response rates, identify the nearest similar audience groups, and forecast performance across channels.

### Content Performance Prediction
Determine how an individual creative asset performs on average across campaigns. Retrieve the assets served in a previous campaign and compare asset performance across a selection of campaigns or a defined time window.

### Post-Campaign Analysis
Identify campaigns that have run in a given country or region, and retrieve their performance metrics or average performance across a region.

---

## Required Data Entities

The lakehouse must contain the following data objects:

| Entity | Description |
|--------|-------------|
| `audience` | Modelled audience segments derived from panel survey data (8 K panel participants) |
| `cookie_registry` | Device/cookie identity map linking cookies to audience profiles and hashed emails |
| `pixel_events` | Ad tracking pixel event stream (impressions, clicks, video engagements) |
| `campaigns` | Campaign and flight metadata including budget, channels, and markets |
| `creatives` | Content asset library linked to campaigns |
| `transactions` | Mastercard-style purchase feed with loyalty-card PAN token as the primary join key |

---

## Scale Parameters

| Table | Row count |
|-------|-----------|
| `audience` | 8 000 panel participants / ~500 modelled segments |
| `cookie_registry` | 80 000 cookies |
| `pixel_events` | 2 000 000 events |
| `campaigns` | ~200 campaigns |
| `creatives` | ~1 000 creative assets |
| `transactions` | ~500 000 transactions |

---

## Identity Join Keys and Match Rates

Join keys must be realistic — not 100% populated and not perfectly consistent across tables. The following rates govern how FK columns are filled during data generation:

| Join key | Tables | Fill rate | Notes |
|----------|--------|-----------|-------|
| `audience_hem` | audience.hem | 60% | Panel participants with consented email |
| `cookie → audience` | cookie_registry.audience_id | 40% | Cookies resolvable to a modelled segment |
| `cookie → hem` | cookie_registry.hem | 35% | Logged-in / authenticated rate |
| `pixel → cookie` | pixel_events.cookie_id | 82% | ~18% cookieless (ITP, iOS, CTV) |
| `transaction → cookie` | transactions.cookie_id | 25% | Cross-channel card-to-cookie resolution (US: 30%, JP: 15%) |
| `transaction → hem` | transactions.hem | 20% | Loyalty card + email collection (US: 25%, JP: 10%) |

The `pan_token` (loyalty-card PAN token) is the primary stable join key within the transactions table and is always populated.

---

## Semantic Synonym Pairs

The data intentionally contains columns with different names that are semantically equivalent, in order to demonstrate Dataplex Knowledge Catalog semantic graph / Business Glossary capabilities:

| Canonical term | Synonym(s) and location |
|----------------|------------------------|
| `cookie_id` | `visitor_id` (cookie_registry), `device_id` (cookie_registry) |
| `hashed_email` / `hem` | `hem` (audience, transactions), `hashed_email` (cookie_registry) |
| `brand` | `advertiser` (campaigns) |
| `lat` / `lon` | `location_lat` / `location_lon` (audience segment centroid columns) |
| `country_code` | `market` (used in some segment label fields) |

---

## Required Metrics

The data must directly or implicitly support calculation of the following metrics:

### 1. Awareness (Top of Funnel)
- **Impressions** — count of impression events in `pixel_events`
- **Reach** — distinct `cookie_id` values among impression events
- **Frequency** — Impressions / Reach
- **CPM** — (SUM spend_usd / impressions) × 1 000

### 2. Engagement & Consideration (Middle of Funnel)
- **Clicks** — count of click events in `pixel_events`
- **CTR** — (Clicks / Impressions) × 100
- **CPC** — Total Spend / Clicks
- **VTR** — video_complete events / video_start events
- **Engagement Rate** — engagement events / Impressions

### 3. Conversion & Efficiency (Bottom of Funnel)
- **Conversions** — `transactions` joined to `pixel_events` via cookie_id or hem within an attribution window
- **CVR** — (Conversions / Clicks) × 100
- **CPA** — actual_spend_usd / Conversions
- **ROAS** — SUM(transaction amount_usd) / actual_spend_usd
- **MER** — Total Revenue / Total Ad Spend

### 4. Long-Term Value
- **LTV** — SUM(amount_usd) per pan_token over the full transaction history
- **CAC** — actual_spend_usd / count of new customers (first transaction)

---

## Deliverables

### D1 — Data Model Design Document
A design document covering the full data model, table schemas with column names, types, nullability, fill rates, and the semantic synonym column strategy. See `lakehouse-tasks-claude.md`.

### D2 — Dataplex Knowledge Catalog Metadata
Descriptive metadata for every data object and all attributes, structured for Dataplex Knowledge Catalog requirements:
- Dataplex Lake / Zone topology (single `curated-data` zone)
- Entry Group and per-table catalog entries with display names and descriptions
- Column-level annotations including synonym cross-references
- Tag template (`marketing_table_metadata`) applied to all entries
- Business Glossary with canonical terms and synonym links for the semantic graph demo

### D3 — Synthetic Data Generators
Python generators (`generators/`) producing synthetic data conforming to the agreed schemas:
- `GeneratorConfig` pydantic model with all scale and match-rate parameters
- One generator class per table, respecting the dependency order (audience → cookies → campaigns → creatives → pixel events → transactions)
- Deterministic output via seeded Faker and NumPy
- Output written as BigLake Iceberg tables to GCS in `us-east1`

**Acceptance criteria:** generator completes in under 5 minutes for full scale; all tables pass `pyiceberg` schema validation; match rates are within ±3pp of configured targets.

### D4 — Ingestion and Catalog Registration Utilities
Python utilities (`ingestion/`) managing the full pipeline from Iceberg write to catalog metadata:
- `iceberg_writer.py` — writes and registers BigLake Iceberg tables
- `dataplex_lake.py` — creates Dataplex Lake, Zones, and Asset registrations under `demo-data`
- `catalog.py` — registers catalog entries in the Entry Group
- `tag_writer.py` — applies the `marketing_table_metadata` tag template
- `glossary_writer.py` — creates Business Glossary terms and synonym graph links
- `cli.py` — Typer-based CLI supporting `ingest`, `generate --local`, `catalog`, `validate`, and `reset` commands

**Acceptance criteria:** `cli.py ingest` runs end-to-end without errors; all tables are queryable via BigQuery; all catalog entries appear in Dataplex with correct tags; synonym term links are visible in the Knowledge Graph.
