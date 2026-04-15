# CLI Functionality - Marketing Data Platform

## 🚀 Getting Started

### 🎯 Quick Start (Zero Configuration)

**No project parameters needed!** The system automatically detects your current gcloud project:

```bash
# Set your GCP project
gcloud config set project your-project-id

# Run commands - they automatically use your current project
uv run python -m ingestion.cli generate
uv run python -m ingestion.cli catalog
uv run python -m ingestion.cli ingest
```

### 1. Prerequisites
*   Python 3.13+
*   [uv](https://github.com/astral-sh/uv) for dependency management.
*   Google Cloud SDK (`gcloud`) authenticated to your project(s).

### 2. Setup
Clone the repository and synchronize the environment:
```bash
uv sync
```

Ensure your `gcloud` project is set:
```bash
# For single-project setup
gcloud config set project wpp-dataproducts-lakehouse

# For cross-project setup, ensure you have access to both projects
# and configure application default credentials appropriately
```

### 3. Cross-Project Configuration (Optional)

The platform now supports **cross-project scenarios** where:
- **Data storage** (GCS, Iceberg tables) resides in one GCP project
- **Catalog/metadata** (Dataplex, BigQuery) resides in another GCP project

**When to use cross-project setup:**
- Data lake spans multiple projects
- Separation of concerns between data teams and governance teams
- Multi-region deployments with centralized catalog
- Compliance requirements for data isolation

**Cross-project CLI parameters:**
```bash
# Cross-project catalog registration
uv run python -m ingestion.cli catalog \
  --data-project data-storage-project \
  --catalog-project catalog-project \
  --iceberg-warehouse gs://data-project-bucket/iceberg

# Cross-project data generation
uv run python -m ingestion.cli generate \
  --data-project data-storage-project \
  --iceberg-warehouse gs://data-project-bucket/iceberg
```

**IAM Requirements for Cross-Project:**
1. **Service Account** needs permissions in BOTH projects:
   - **Data project**: Storage Admin, BigQuery Data Editor
   - **Catalog project**: Dataplex Admin, BigQuery Admin
2. **BigLake connections** require cross-project access configuration
3. **Dataplex service agent** needs access to data project resources

### 4. Single-Project Setup (Default)

By default, all operations **automatically use your current gcloud project**:
```bash
# Set your gcloud project
gcloud config set project your-project-id

# Commands automatically use the current gcloud project
uv run python -m ingestion.cli catalog
uv run python -m ingestion.cli generate
uv run python -m ingestion.cli ingest
```

**How it works:**
- The system automatically detects your current gcloud project
- Uses it for both data operations and catalog operations
- Falls back to `GOOGLE_CLOUD_PROJECT` environment variable if gcloud not available
- Defaults to `wpp-dataproducts-lakehouse` only if neither is set

### 5. Project Detection Priority

The platform uses this **priority order** for project detection:

| Priority | Method | Example |
|----------|--------|---------|
| 1️⃣ **Highest** | Explicit CLI parameters | `--data-project my-project` |
| 2️⃣ | Current gcloud project | `gcloud config set project my-project` |
| 3️⃣ | Environment variable | `export GOOGLE_CLOUD_PROJECT=my-project` |
| 4️⃣ **Fallback** | Hardcoded default | `wpp-dataproducts-lakehouse` |

**This means you can:**

✅ **Zero-configuration mode** - Just set gcloud project and run commands:
```bash
gcloud config set project my-marketing-project
uv run python -m ingestion.cli ingest  # Automatically uses my-marketing-project
```

✅ **Explicit control** - Override when needed:
```bash
uv run python -m ingestion.cli catalog --data-project different-project
```

✅ **Hybrid approach** - Mix automatic and explicit:
```bash
# Use current gcloud project for catalog, specify data project
gcloud config set project catalog-project
uv run python -m ingestion.cli catalog --data-project data-project
```

✅ **Environment variable fallback** - For CI/CD and automation:
```bash
export GOOGLE_CLOUD_PROJECT=production-project
uv run python -m ingestion.cli generate  # Uses production-project
```

### 6. Practical Examples

**Example 1: Simple single-project setup (most common)**
```bash
# Set your project once
gcloud config set project my-marketing-lakehouse

# All commands automatically use this project
uv run python -m ingestion.cli generate
uv run python -m ingestion.cli catalog
uv run python -m ingestion.cli ingest
```

**Example 2: Cross-project with minimal configuration**
```bash
# Set catalog project via gcloud
gcloud config set project catalog-project

# Only specify data project when needed
uv run python -m ingestion.cli catalog --data-project data-storage-project
```

**Example 3: Full cross-project specification**
```bash
# Explicitly specify everything for clarity
uv run python -m ingestion.cli catalog \
  --data-project data-storage-prod \
  --catalog-project catalog-prod \
  --iceberg-warehouse gs://data-bucket-prod/iceberg \
  --biglake-connection projects/catalog-prod/locations/us/connections/prod-conn
```

**Example 4: CI/CD automation**
```bash
# In your CI/CD pipeline
export GOOGLE_CLOUD_PROJECT=$PRODUCTION_PROJECT
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

uv run python -m ingestion.cli generate --full-scale
uv run python -m ingestion.cli catalog
```

## 📋 Usage Guide

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

#### **Template Generation**
Create template files for metadata and glossary management:

```bash
# Create all template files
uv run python -m ingestion.cli create-templates

# This creates:
# - metadata_descriptions/*.md files for each table
# - business_glossaries/glossary.md with sample structure
```

## 🔧 Metadata Enrichment

Generate table and column descriptions to improve data discovery:

```bash
# Enrich all tables
uv run python -m ingestion.cli enrich-metadata

# Enrich specific tables
uv run python -m ingestion.cli enrich-metadata --table-names audience,campaigns

# Enrich a single table
uv run python -m ingestion.cli enrich-metadata --table-names pixel_events
```

### Two Distinct Modes:

#### 🔧 Mode 1: Hybrid Approach (Manual + Google Insights)
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
uv run python -m ingestion.cli enrich-metadata \
  --table-names wpp-dataproducts-lakehouse.marketing.audience \
  --metadata-files audience.md
```

#### 🤖 Mode 2: Google Insights Only (Pure Automation)
**For users who want fully automated Google Dataplex-style metadata**

- **Requires**: NO manual markdown files
- **Uses**: ONLY automated Google-style insights
- **Use Case**: Quick setup, standard metadata patterns, or when manual descriptions aren't available

**Workflow:**
```bash
# Apply pure Google insights to specific tables
uv run python -m ingestion.cli enrich-metadata \
  --table-names wpp-dataproducts-lakehouse.marketing.campaigns \
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

## 📚 Business Glossary Management

Batch create and manage the Dataplex Business Glossary with semantic synonym links:

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

## 📊 Data Profiling

Create and run Dataplex data profile scans for statistical analysis:

```bash
# Profile all tables
uv run python -m ingestion.cli profile

# Profile specific tables
uv run python -m ingestion.cli profile --table-names audience,pixel_events

# Preview what would be created (dry-run)
uv run python -m ingestion.cli profile --dry-run

# View results of previous profiling runs
uv run python -m ingestion.cli profile --results
```

## 🛡️ Data Quality

Create and run Dataplex data quality scans with marketing-specific rules:

```bash
# Run quality scans on all tables
uv run python -m ingestion.cli quality

# Run quality scans on specific tables
uv run python -m ingestion.cli quality --table-names campaigns,transactions

# Preview what would be created (dry-run)
uv run python -m ingestion.cli quality --dry-run

# View results of previous quality scans
uv run python -m ingestion.cli quality --results
```

## 🚀 Advanced Features

### Vector Search
Set up BigQuery Vector Search for semantic search and similarity analysis:

```bash
# Set up vector search with embedding model and index
uv run python -m ingestion.cli vector-search

# Preview SQL without executing (dry-run)
uv run python -m ingestion.cli vector-search --dry-run
```

### BigQuery ML Gemini
Set up BigQuery ML with Gemini remote models for text generation:

```bash
# Set up BQML Gemini model and run example queries
uv run python -m ingestion.cli bqml-setup

# Preview SQL without executing (dry-run)
uv run python -m ingestion.cli bqml-setup --dry-run
```

### Continuous Queries
Set up BigQuery continuous queries for real-time data processing:

```bash
# Set up continuous query for real-time CTR aggregation
uv run python -m ingestion.cli continuous-queries

# Preview SQL without executing (dry-run - default)
uv run python -m ingestion.cli continuous-queries --dry-run
```

## 🔄 Resource Management

### Reset/Cleanup
Tear down all generated resources for a clean re-run:

```bash
# Reset all marketing lakehouse resources (requires --confirm)
uv run python -m ingestion.cli reset --confirm

# This deletes: BQ external tables, Dataplex entries/tags, glossary resources, Iceberg catalog
# Does NOT delete GCS data by default
```

## 📊 Data Consumption & Analysis

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

## 📦 Ingestion Classes Overview

The ingestion module contains the following classes that handle data ingestion and metadata management:

### Data Writing & Registration
- **`IcebergWriter`** (`ingestion/iceberg_writer.py`): Writes data to Iceberg tables in GCS
- **`BigLakeRegistrar`** (`ingestion/bq_external.py`): Registers BigLake external tables in BigQuery
- **`DataplexManager`** (`ingestion/dataplex_lake.py`): Manages Dataplex lake topology and asset registration
- **`CatalogManager`** (`ingestion/catalog.py`): Creates and manages Dataplex catalog entries

### Metadata & Governance
- **`TagWriter`** (`ingestion/tag_writer.py`): Applies Dataplex tags to tables based on markdown metadata
- **`GlossaryWriter`** (`ingestion/glossary_writer.py`): Legacy wrapper for glossary operations (delegates to BusinessGlossaryManager)
- **`BusinessGlossaryManager`** (`ingestion/glossary_manager.py`): Manages Dataplex business glossary creation and term linking
- **`HybridMetadataEnricher`** (`ingestion/bq_metadata_hybrid.py`): Enriches tables with hybrid (manual + automated) metadata

### Data Quality & Analysis
- **`DataProfilingManager`** (`ingestion/data_profiling.py`): Creates and runs Dataplex data profile scans for statistical analysis (row counts, distributions, patterns)
- **`DataQualityManager`** (`ingestion/data_quality.py`): Creates and runs Dataplex data quality scans with marketing-specific validation rules

### Advanced Features
- **`VectorSearchManager`** (`ingestion/vector_search.py`): Sets up BigQuery Vector Search with embedding models and indexes
- **`BQMLGeminiManager`** (`ingestion/bqml_gemini.py`): Manages BigQuery ML Gemini remote model setup and text generation
- **`ContinuousQueryManager`** (`ingestion/continuous_queries.py`): Sets up BigQuery continuous queries for real-time aggregation