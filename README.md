# Lakehouse Content — Marketing Data Platform

A synthetic, end-to-end Marketing Data Platform demonstration built on **Google Cloud Dataplex**, **BigQuery BigLake**, and **Apache Iceberg**. 

## 🎯 Project Purpose
The primary goal of this project is to demonstrate the value of the **Dataplex Knowledge Catalog** through agent-based data discovery and analysis. By generating high-fidelity synthetic marketing data and registering it with rich metadata, we showcase how AI agents can navigate complex data estates, resolve semantic synonyms, and perform cross-channel attribution without prior knowledge of the physical schema.

## 📈 Marketing Use Cases
The platform is designed to support four foundational marketing scenarios:
*   **Audience Discovery**: Identifying demographics and interest traits that over-index for specific products and locating their geographic clusters.
*   **Audience Performance Prediction**: Forecasting response rates and identifying similar audience cohorts for lookalike modeling.
*   **Content Performance Prediction**: Comparing the effectiveness of individual creative assets across multiple campaigns and time windows.
*   **Post-Campaign Analysis**: Aggregating performance metrics (Impressions, CTR, ROAS) across regions and markets.

---

## 🏗 Architecture Overview

### 1. Data Model
The platform models a high-fidelity marketing ecosystem across six core entities:
*   **`audience`**: Modelled segments (8K panel participants) with demographics and interest scores.
*   **`cookie_registry`**: Identity mapping table (80K cookies) linking devices to audience IDs and Hashed Emails (HEM).
*   **`pixel_events`**: Event-level stream (2M events) of impressions, clicks, and video engagement.
*   **`campaigns`**: Metadata for advertising flights, budgets, and objectives.
*   **`creatives`**: Asset library linked to campaigns with format and theme metadata.
*   **`transactions`**: Mastercard-style purchase feed (500K rows) for ROAS and LTV calculation.

### 2. Local Development
The project uses a **local SQL catalog** (`iceberg_catalog.db`) to manage Iceberg metadata state during development. This SQLite database:
- Tracks Iceberg table schemas and locations
- Manages table versions and snapshots
- Is automatically created/updated during ingestion
- Can be safely deleted and regenerated if corrupted

### 3. The "Semantic Demo" (Synonyms)
To demonstrate Dataplex's Knowledge Graph capabilities, specific tables contain physical synonym columns with identical values:
*   **Identity**: `cookie_id` ↔ `visitor_id` ↔ `device_id`
*   **Contact**: `hem` ↔ `hashed_email`
*   **Geo**: `lat`/`lon` ↔ `location_lat`/`location_lon`
*   **Org**: `brand` ↔ `advertiser`

### 4. Dataplex Topology
*   **Lake**: `demo-data` (Region: `us-east1`)
*   **Zones**:
    *   `raw-data` (RAW): GCS-backed, contains the `pixel_events` Iceberg table.
    *   `curated-data` (CURATED): BigLake/Iceberg-backed, contains enriched marketing tables.
*   **Governance**: Includes a **Business Glossary** (`marketing-glossary`) and **Tag Templates** (`marketing-table-metadata`).

### 5. Iceberg Catalog Management
The project uses PyIceberg with a **local SQL catalog** for development:
- **Catalog Type**: SQLite (`iceberg_catalog.db`)
- **Purpose**: Manages Iceberg table metadata locally before syncing to GCS
- **Location**: Project root directory
- **Behavior**: Automatically created on first run, persists table schemas and versions

### 6. Markdown-Driven Configuration

Almost all metadata in this project is controlled via markdown files — **no code changes are needed** to modify catalog descriptions, tag values, synonym column mappings, or glossary terms. The three markdown-driven systems are:

| System | File(s) | What it controls |
|--------|---------|------------------|
| **Table metadata** | `metadata_descriptions/*.md` | Catalog display names, descriptions, Dataplex tag values, column descriptions, synonym column mappings |
| **Business glossary** | `business_glossaries/glossary.md` | Dataplex glossary terms, synonym links, related-term links, term-to-table definition links |
| **Column descriptions** | (same as table metadata) | BigQuery column descriptions applied via `enrich-metadata` |

#### Table Metadata File Format (`metadata_descriptions/<table>.md`)

Each table has a markdown file that drives **four concerns** at once:

```markdown
# Display Name

Description paragraph(s). This becomes the Dataplex catalog entry description.

## Tags
- business_owner: Marketing Data Products
- data_domain: audience
- pii_class: pseudonymous
- refresh_cadence: daily
- row_count_approx: 8000
- marketing_usecases: audience_discovery,audience_performance_prediction

## Columns
- audience_id: Surrogate primary key (UUID v4).
- hem: SHA-256 of normalised email. ~60% populated.
- lat: Centroid latitude of dominant geo cluster.
- location_lat: Synonym for lat.
  - Synonym Of: lat
- location_lon: Synonym for lon.
  - Synonym Of: lon
```

**How each section is consumed:**
*   `# Display Name` → `catalog.py` uses this as the Dataplex entry display name
*   Description paragraph → `catalog.py` uses this as the entry description
*   `## Tags` → `tag_writer.py` applies these as the `marketing_table_metadata` aspect fields
*   `## Columns` → `enrich-metadata` applies these as BigQuery column descriptions
*   `Synonym Of: <column>` → the orchestrator copies the source column's values into the synonym column at generation time

#### Adding Synonym Columns for a New Table

To add a synonym column pair (e.g. `email_hash` as a synonym of `hem`):
1.  Add the synonym column to your generator's schema and data dict (with `None` placeholder values)
2.  Add the column to the metadata markdown with a `Synonym Of:` sub-bullet:
    ```markdown
    - email_hash: Alternative name for hashed email.
      - Synonym Of: hem
    ```
3.  The orchestrator will automatically copy `hem` values into `email_hash` at generation time
4.  Add the synonym relationship to `business_glossaries/glossary.md` so Dataplex creates the link:
    ```markdown
    - **hashed_email**
      - Synonyms: hem, email_hash
    ```

#### Adding a New Data Source

When integrating a new table into the lakehouse:
1.  **Create `metadata_descriptions/<table_name>.md`** with the display name, description, `## Tags`, and `## Columns` sections. This single file configures catalog entries, tags, and column descriptions.
2.  **Write a generator** in `generators/` that produces the base columns. Synonym columns should be included in the schema but left as `None` — the orchestrator fills them from the metadata.
3.  **Add the table to the orchestrator** (`generators/orchestrator.py`)
4.  **Add glossary terms** to `business_glossaries/glossary.md` if the table introduces new canonical terms or synonyms
5.  Run `uv run python -m ingestion.cli generate --local` then `validate --local` to verify

### 7. Business Glossary Management
Batch create and manage Dataplex business glossaries from markdown files using the dedicated **Dataplex Glossary API** (`BusinessGlossaryServiceClient`).

**Architecture:**
*   `business_glossaries/glossary.md` — markdown definition of terms, categories, synonyms, and related-term links
*   `ingestion/glossary_manager.py` — parses markdown and calls the Dataplex Glossary & Catalog APIs
*   `ingestion/glossary_writer.py` — legacy wrapper, delegates to `glossary_manager.py`

**Dataplex Resources Created:**
*   **Glossary** → `POST /v1/.../glossaries`
*   **Categories** (Identity, Campaign, Geography) → `POST .../glossaries/{id}/categories`
*   **Terms** (cookie_id, hashed_email, brand, country_code, lat, lon + synonym terms) → `POST .../glossaries/{id}/terms`
*   **Synonym links** → `POST .../entryGroups/@dataplex/entryLinks` with `entryLinkTypes/synonym`
*   **Related-term links** → `entryLinkTypes/related`
*   **Definition links** (term → BigQuery table) → `entryLinkTypes/definition`

**Workflow:**
```bash
# 1. Generate glossary template (one-time)
uv run python -m ingestion.cli create-templates

# 2. Edit business_glossaries/glossary.md

# 3. Preview what will be created
uv run python -m ingestion.cli manage-glossary --dry-run

# 4. Create Dataplex glossary
uv run python -m ingestion.cli manage-glossary --action create

# 5. Validate glossary resources exist
uv run python -m ingestion.cli manage-glossary --action validate

# 6. Link terms to BigQuery assets
uv run python -m ingestion.cli manage-glossary --action apply

# Reset and recreate from scratch
uv run python -m ingestion.cli manage-glossary --action create --reset

# Use a custom glossary file
uv run python -m ingestion.cli manage-glossary --action create --input my_glossary.md
```

**Glossary File Format** (`business_glossaries/glossary.md`):
```markdown
# Marketing Business Glossary

Standardised vocabulary for the Marketing Lakehouse data estate.

## Category: Identity

Terms related to user and device identity resolution.

- **cookie_id**
  - Synonyms: visitor_id, device_id
  - Description: Unique identifier for a browser or device session.
  - Tables: cookie_registry, pixel_events
  - Business Context: Identity resolution

- **hashed_email**
  - Synonyms: hem
  - Description: SHA-256 hash of a normalised email address.
  - Tables: audience, cookie_registry, transactions
  - Business Context: Cross-channel attribution
```

**Pre-populated Synonym Pairs** (from `Agent.md`):
*   **Identity**: `cookie_id` ↔ `visitor_id`, `device_id` · `hashed_email` ↔ `hem`
*   **Campaign**: `brand` ↔ `advertiser` · `country_code` ↔ `market`
*   **Geography**: `lat` ↔ `location_lat` · `lon` ↔ `location_lon`

---

### 8. Metadata Enrichment (Detail)
The platform includes **Google Dataplex-style metadata enrichment** with a clear choice between manual and automated approaches:

**Two Distinct Modes:**

### 🔧 Mode 1: Hybrid Approach (Manual + Google Insights)
**For users who want precise control over metadata content**

- **Requires**: Manual markdown files in `metadata_descriptions/`
- **Combines**: Your semantic context with Google-style automated insights
- **Use Case**: When you need specific business terminology or context

**Workflow:**
```bash
# 1. Generate templates (one-time setup)
uv run python -m ingestion.cli create-templates

# 2. Edit the markdown files in metadata_descriptions/

# 3. Apply hybrid enrichment
uv run python -m ingestion.cli enrich-metadata \\
  --table-names wpp-dataproducts-lakehouse.marketing.audience \\
  --metadata-files audience.md
```

### 🤖 Mode 2: Google Insights Only (Pure Automation)
**For users who want fully automated Google Dataplex-style metadata**

- **Requires**: NO manual markdown files
- **Uses**: ONLY automated Google-style insights
- **Use Case**: Quick setup, standard metadata patterns, or when manual descriptions aren't available

**Workflow:**
```bash
# Apply pure Google insights to specific tables
uv run python -m ingestion.cli enrich-metadata \\
  --table-names wpp-dataproducts-lakehouse.marketing.campaigns \\
  --google-insights

# Apply pure Google insights to ALL tables
uv run python -m ingestion.cli enrich-metadata --google-insights
```

**Key Differences:**

| Aspect | Hybrid Mode | Google Insights Mode |
|--------|-------------|---------------------|
| **Manual Files** | Required ✅ | Not Used ❌ |
| **Automation** | Supplemental | Primary ✅ |
| **Control** | Precise | Standardized |
| **Setup** | More involved | Instant |
| **Use Case** | Custom metadata | Quick/standard metadata |

**Important Rules:**

1. **Mutually Exclusive**: You cannot use both `--metadata-files` and `--google-insights` together
2. **Explicit Choice**: For selective operations, you MUST choose one approach
3. **Bulk Operations**: Default mode uses hybrid, use `--google-insights` for pure automation

**Error Examples:**
```bash
# ❌ Missing both flags for selective operation
uv run python -m ingestion.cli enrich-metadata --table-names campaigns
# Error: When specifying table names without --google-insights, you must provide metadata files

# ❌ Using both flags (mutually exclusive)
uv run python -m ingestion.cli enrich-metadata --table-names campaigns --metadata-files campaigns.md --google-insights
# Error: Cannot use both manual files and Google insights together
```

**When to Use Each Mode:**

**Choose Hybrid Mode when:**
- You have specific business terminology to include
- You need precise control over descriptions
- You want to combine manual expertise with automation
- You're following a governed metadata process

**Choose Google Insights Mode when:**
- You need quick, standardized metadata
- You don't have time for manual descriptions
- You want pure Google Dataplex compliance
- You're doing initial exploration or prototyping

**Metadata File Format (Hybrid Mode Only):**
```markdown
# Table Name

High-level description of the table's purpose and content.

## Columns

- column_name: Description of what this column represents
- another_column: Description of this column's purpose and content
```
---

## 🌍 Markets & Brands
The data generation covers three target markets with realistic variation in data quality:
*   **Markets**: US, UK, Japan.
*   **Fictional Brands**: Lucky Cola, Force Automotive, AEKI Living.
*   **Regional Variation**: Join success rates are adjusted per market (US baseline, UK -5pp, Japan -10pp) to simulate real-world identity resolution challenges.

---

## 🚀 Getting Started

### 1. Prerequisites
*   Python 3.13+
*   [uv](https://github.com/astral-sh/uv) for dependency management.
*   Google Cloud SDK (`gcloud`) authenticated to your project.

### 2. Setup
Clone the repository and synchronize the environment:
```bash
uv sync
```

Ensure your `gcloud` project is set:
```bash
gcloud config set project wpp-dataproducts-lakehouse
```

### 3. Usage
The project uses a unified CLI for all operations:

#### **Full Ingestion (One-shot)**
Generates data, writes to Iceberg/GCS, and registers all Dataplex Catalog metadata:
```bash
uv run python -m ingestion.cli ingest
```

#### **Local Testing**
Generate Parquet files locally to `local_output/` and validate schemas/match-rates:
```bash
uv run python -m ingestion.cli generate --local
uv run python -m ingestion.cli validate --local
```

#### **Catalog Registration Only**
If you need to re-register tables after data generation:
```bash
uv run python -m ingestion.cli catalog
```

#### **Metadata Enrichment**
Generate table and column descriptions to improve data discovery:

```bash
# Enrich all tables
uv run python -m ingestion.cli enrich-metadata

# Enrich specific tables
uv run python -m ingestion.cli enrich-metadata --table-names audience,campaigns

# Enrich a single table
uv run python -m ingestion.cli enrich-metadata --table-names pixel_events
```

#### **Business Glossary**
Create and manage the Dataplex Business Glossary with semantic synonym links:

```bash
# Preview glossary resources (no API calls)
uv run python -m ingestion.cli manage-glossary --dry-run

# Create glossary, categories, terms, and synonym links
uv run python -m ingestion.cli manage-glossary --action create

# Validate all resources exist in Dataplex
uv run python -m ingestion.cli manage-glossary --action validate

# Link glossary terms to BigQuery table entries
uv run python -m ingestion.cli manage-glossary --action apply
```

---

## 🔍 Data Consumption & Analysis

Once the ingestion is complete, data is accessible through several interfaces:

### 1. BigQuery (BigLake)
The tables are registered as **BigLake External Tables** in the `marketing` dataset. You can query them directly using standard SQL:
```sql
-- Join transactions and cookies via the semantic synonym 'hem'
SELECT t.merchant_name, c.device_type, SUM(t.amount_usd) as revenue
FROM `wpp-dataproducts-lakehouse.marketing.transactions` t
JOIN `wpp-dataproducts-lakehouse.marketing.cookie_registry` c 
  ON t.hem = c.hashed_email
GROUP BY 1, 2;
```

### 2. Dataplex Search & Glossary
*   **Business Glossary**: Navigate the `marketing-glossary` to find definitions for terms like "ROAS" or "HEM".
*   **Catalog Search**: Search for terms like "Advertiser" to discover the `campaigns` table, even if you weren't aware of the `brand` column name, thanks to the synonym links.

---

## 🤖 AI-Powered Analysis (Agent + MCP)

The Lakehouse is designed to be analyzed by AI agents (like GStack/Gemini CLI) equipped with **Dataplex MCP (Model Context Protocol)**. 

### How to use an Agent with this Lakehouse:

1.  **Metadata Discovery**: Ask the agent to find relevant tables for a query.
    *   *User prompt*: "What tables do I have that contain visitor identifiers and geographic locations?"
    *   *Agent Action*: The agent uses Dataplex MCP to search the catalog. It identifies `cookie_registry` (via `visitor_id` synonym) and `audience` (via `location_lat` synonym).

2.  **Schema Understanding**: The agent retrieves the Iceberg schema and column descriptions.
    *   *User prompt*: "Tell me about the fill rates for identity keys in the Japanese market."
    *   *Agent Action*: The agent reads the `marketing_table_metadata` tags and descriptions to understand the market-specific variations (`JP` rates: 15% cookie, 10% hem).

3.  **Automated SQL Generation**: The agent leverages synonym mapping to write robust joins.
    *   *User prompt*: "Show me total spend by advertiser for the last 30 days."
    *   *Agent Action*: The agent recognizes that "advertiser" maps to the `advertiser` column in `campaigns`, and generates the SQL join to `pixel_events` (which uses `campaign_id`).

### Key Benefits of MCP Access:
*   **No Guesswork**: The agent doesn't need to "guess" column meanings; it reads the canonical glossary links.
*   **Semantic Awareness**: The agent can bridge gaps between business terms (e.g., "Customer Email") and physical columns (`hem`, `hashed_email`).
*   **Data Lineage & Quality**: By reading the `pii_class` and `refresh_cadence` tags, the agent can warn you about data freshness or sensitivity.

---

## 📊 Data Generation Logic
*   **Realistic Match Rates**: Identity joins carry realistic null rates (Baseline: 82%).
*   **Market Variation**: Transaction match rates vary by market (US: 30%, UK: 20%, JP: 15%).
*   **Iceberg Native**: Data is written using `pyiceberg` with partitioning on `_partition_date`.

## 🛠 Tech Stack
*   **Storage**: GCS, Apache Iceberg
*   **Compute**: BigQuery BigLake
*   **Governance**: Dataplex Catalog, Business Glossary
*   **Generation**: Python, Faker, PyArrow, NumPy, Pydantic v2

### 📦 Dataclasses Overview

The ingestion module uses Python dataclasses to model metadata structures:

#### Table Metadata (`ingestion/table_metadata.py`)
- **`ColumnMeta`**: Represents metadata for a single column (name, description, synonym relationships)
- **`TableMeta`**: Aggregates all metadata for a table (display name, description, tags, columns)

#### Glossary Management (`ingestion/glossary_manager.py`)
- **`GlossaryTermDef`**: Defines a glossary term with synonyms, related terms, and table associations
- **`GlossaryCategoryDef`**: Groups related terms into categories (e.g., Identity, Campaign, Geography)
- **`GlossaryDef`**: Top-level container for the entire glossary structure

These dataclasses provide type-safe parsing and manipulation of markdown-driven configuration files.

### 🏗 Ingestion Classes Overview

The ingestion module contains the following classes that handle data ingestion and metadata management:

#### Data Writing & Registration
- **`IcebergWriter`** (`ingestion/iceberg_writer.py`): Writes data to Iceberg tables in GCS
- **`BigLakeRegistrar`** (`ingestion/bq_external.py`): Registers BigLake external tables in BigQuery
- **`DataplexManager`** (`ingestion/dataplex_lake.py`): Manages Dataplex lake topology and asset registration
- **`CatalogManager`** (`ingestion/catalog.py`): Creates and manages Dataplex catalog entries

#### Metadata & Governance
- **`TagWriter`** (`ingestion/tag_writer.py`): Applies Dataplex tags to tables based on markdown metadata
- **`GlossaryWriter`** (`ingestion/glossary_writer.py`): Legacy wrapper for glossary operations (delegates to BusinessGlossaryManager)
- **`BusinessGlossaryManager`** (`ingestion/glossary_manager.py`): Manages Dataplex business glossary creation and term linking
- **`HybridMetadataEnricher`** (`ingestion/bq_metadata_hybrid.py`): Enriches tables with hybrid (manual + automated) metadata

#### Data Quality & Analysis
- **`DataProfilingManager`** (`ingestion/data_profiling.py`): Creates and runs Dataplex data profiling scans
- **`DataQualityManager`** (`ingestion/data_quality.py`): Creates and runs Dataplex data quality scans with marketing-specific rules

#### Advanced Features
- **`VectorSearchManager`** (`ingestion/vector_search.py`): Sets up BigQuery Vector Search with embedding models and indexes
- **`BQMLGeminiManager`** (`ingestion/bqml_gemini.py`): Manages BigQuery ML Gemini remote model setup and text generation
- **`ContinuousQueryManager`** (`ingestion/continuous_queries.py`): Sets up BigQuery continuous queries for real-time aggregation

These classes are orchestrated through the CLI (`ingestion/cli.py`) to provide a comprehensive data ingestion and governance pipeline.

