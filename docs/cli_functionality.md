# Google DataPlex and BigQuery Lake CLI 

This project contains a collection of CLI tools that (intends) to accellerate ingestions, metadata generation and management of various 
key componenet in the Google DataPlex and BigQuery domain.
They were build out of frustration with the slow approach of doing everything via the console and the lack of a batched
process for maintaing many tables with manually ingested metadata.

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
# - metadata/*.yaml files for each table
# - metadata/glossary.yaml with sample structure
```

## 🔧 Metadata Enrichment

#### Adding Synonym Columns for a New Table

To add a synonym column pair (e.g. `email_hash` as a synonym of `hem`):
1.  Add the synonym column to your generator's schema and data dict (with `None` placeholder values)
2.  Add the column to the metadata YAML with a `synonym_of` key:
    ```yaml
    columns:
      - name: email_hash
        description: Alternative name for hashed email.
        synonym_of: hem
    ```
3.  The orchestrator will automatically copy `hem` values into `email_hash` at generation time
4.  Add the synonym relationship to `metadata/glossary.yaml` so Dataplex creates the link:
    ```markdown
    - **hashed_email**
      - Synonyms: hem, email_hash
    ```

#### Defining Data Quality Rules in YAML
Deep dive on syntax in the docs (https://docs.cloud.google.com/dataplex/docs/auto-data-quality-overview#rule-definition)
Data quality rules are defined in the `data_quality_rules` list of each table's metadata YAML file.
This replaces the previous approach of hardcoded Python rules and allows DQ rules to be version-controlled
alongside table metadata.

**Rule syntax:**
```yaml
data_quality_rules:
  - column: column_name
    rule_type: rule_name
    threshold: 0.95
    dimension: COMPLETENESS
```

**Supported rule types:**

| Rule Type | Parameters | Example |
|-----------|------------|---------|
| `non_null` | `threshold` (float, default 1.0), `dimension` (str, default COMPLETENESS) | `rule_type: non_null` |
| `set` | `values` (comma-sep list), `dimension` (default VALIDITY) | `rule_type: set` |
| `regex` | `pattern` (str), `threshold`, `dimension` | `rule_type: regex` |
| `range` | `min`, `max`, `strict_min`, `strict_max`, `threshold`, `dimension` | `rule_type: range` |

**Complete example — `metadata/campaigns.yaml`:**
```yaml
table_id: campaigns
display_name: Campaign / Flight Metadata
description: >
  Master record for advertising campaigns...

tags:
  business_owner: Marketing Data Products
  data_domain: campaigns

columns:
  - name: campaign_id
    description: Primary key (UUID v4).
  - name: status
    description: "Lifecycle state: planned | active | completed | paused."

data_quality_rules:
  - column: campaign_id
    rule_type: non_null
  - column: brand
    rule_type: non_null
  - column: advertiser
    rule_type: non_null
  - column: status
    rule_type: set
    values: planned,active,completed,paused
    dimension: VALIDITY
```

**Example with threshold — `metadata/audience_profile.yaml`:**
```yaml
data_quality_rules:
  - column: audience_id
    rule_type: non_null
  - column: segment_name
    rule_type: non_null
  - column: hem
    rule_type: non_null
    threshold: 0.57
    dimension: COMPLETENESS
  - column: lat
    rule_type: non_null
  - column: lon
    rule_type: non_null
```

The `hem` rule specifies a 57% completeness threshold (matching the ~60% populate rate
in the synthetic data, with a small margin).

**Rules are loaded automatically when running DQ scans:**
```bash
uv run python -m ingestion.cli quality --dry-run
```

The `DataQualityManager` reads all `data_quality_rules` sections from `metadata/*.yaml`
files and converts them to Dataplex `DataQualityRule` objects at scan creation time.

To add a new rule, simply edit the appropriate YAML file and re-run the quality CLI.

####  Generate table and column descriptions to improve data discovery:

```bash
# Enrich all tables
uv run python -m ingestion.cli enrich-metadata

# Enrich specific tables
uv run python -m ingestion.cli enrich-metadata --table-names audience,campaigns

# Enrich a single table
uv run python -m ingestion.cli enrich-metadata --table-names pixel_events
```

### Two Distinct Modes:

#### 🔧 Mode 1: Manual YAML Approach (Pure Manual)
**For users who want precise control over metadata content**

- **Requires**: Manual YAML files in `metadata/`
- **Uses**: ONLY manual descriptions (no automated insights)
- **Use Case**: When you need specific business terminology or context

**Workflow:**
```bash
# 1. Generate templates (one-time setup)
uv run python -m ingestion.cli create-templates

# 2. Edit the YAML files in metadata/

# 3. Apply manual metadata enrichment
uv run python -m ingestion.cli enrich-metadata \
  --table-names wpp-dataproducts-lakehouse.marketing.audience \
  --metadata-files audience.yaml
```

#### 🤖 Mode 2: Google Insights Only (Pure Automation)
**For users who want fully automated Google Dataplex-style metadata**

- **Requires**: NO manual markdown files
- **Uses**: ONLY automated Google-style insights (no heuristics)
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

| Aspect | Manual YAML Mode | Google Insights Mode |
|--------|---------------------|---------------------|
| **Manual Files** | Required ✅ | Not Used ❌ |
| **Automation** | Not Used ❌ | Primary ✅ |
| **Control** | Precise | Standardized |
| **Setup** | More involved | Instant |
| **Use Case** | Custom metadata | Quick/standard metadata |

**When to Use Each Mode:**

**Choose Manual YAML Mode when:**
- You have specific business terminology to include
- You need precise control over descriptions
- You want to use only manual descriptions (no automation)
- You're following a governed metadata process

**Choose Google Insights Mode when:**
- You need quick, standardized metadata
- You don't have time for manual descriptions
- You want pure Google Dataplex compliance (no heuristics)
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

Create and run Dataplex data profile scans for statistical analysis. Results are automatically
published to a dedicated BigQuery dataset (`<namespace>_profile_results`) for easy querying
and Looker Studio dashboards.

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

**Results table location:**

Profile results are written to BigQuery tables in the `marketing_profile_results` dataset
(named `<table>_profile`, e.g. `audience_profile`, `campaigns_profile`).

Query results directly:
```sql
SELECT * FROM `wpp-dataproducts-lakehouse.marketing_profile_results.audience_profile`
ORDER BY job_start_time DESC
LIMIT 10;
```

Or view the "Data profile" tab on the source table in BigQuery Studio (results are
accessible from any project).

## 🛡️ Data Quality

Create, sync, and run Dataplex data quality scans. Rules are loaded from `metadata/*.yaml`
files (the `data_quality_rules` list per table), keeping DQ logic version-controlled
alongside table metadata.

The data quality command provides full lifecycle management:

```bash
# Compare YAML rules with active Dataplex rules (no changes made)
uv run python -m ingestion.cli quality --check-rules

# Sync rules from YAML to Dataplex without running scans
uv run python -m ingestion.cli quality --sync-only

# Sync rules AND run scans (default behavior)
uv run python -m ingestion.cli quality

# Preview what would be synced
uv run python -m ingestion.cli quality --sync-only --dry-run

# Run quality scans on specific tables only
uv run python -m ingestion.cli quality --table-names campaigns,transactions

# View results of previous quality scans
uv run python -m ingestion.cli quality --results
```

**Understanding the workflow:**

1. **Check rules** (`--check-rules`): Compares rules in YAML files with active rules in Dataplex.
   Shows which rules would be added, removed, or changed. Makes no changes.

2. **Sync only** (`--sync-only`): Updates Dataplex scans to match YAML rules.
   Creates new scans if needed, updates existing ones if rules differ. Does NOT run scans.

3. **Sync and run** (default): Syncs rules AND triggers scan runs. This is the standard
   workflow for running data quality checks.

**Rule comparison output example:**
```
Checking data quality rules for 6 table(s)...

📋 campaigns:
   Markdown rules: 4
   Active rules: 4
   Status: ✅ In sync

📋 transactions:
   Markdown rules: 3
   Active rules: 2
   Status: ⚠️  Out of sync
   + Add: 1 rule(s)
       - non_null_amount_usd on amount_usd
```

**Sync output example:**
```
Synchronizing data quality rules for 6 table(s)...

  ✅ Created scan: quality-campaigns (4 rules)
  ✅ Updated scan: quality-transactions
     + Added 1 rules
     - Removed 0 rules
     ~ Changed 0 rules
     = Total: 3 rules
  ℹ️  Scan quality-audience rules are up to date (5 rules)
```

**To add or modify rules**, edit the `data_quality_rules` list in the relevant
`metadata/<table>.yaml` file and re-run the quality command.

## 🔍 Dataset Insights

Create and run Dataplex DATA_DOCUMENTATION scans at the dataset level for AI-generated
metadata about an entire BigQuery dataset. Unlike table-level insights which target individual
tables, dataset-level insights analyze relationships and generate cross-table metadata.

Dataset insights produce:
- AI-generated dataset description
- Relationship graph (how tables connect)
- Cross-table SQL sample queries
- Discovered primary/foreign key relationships

```bash
# Create and run dataset insights scan (default behavior)
uv run python -m ingestion.cli dataset-insights

# Preview scan without executing
uv run python -m ingestion.cli dataset-insights --dry-run

# Get latest insights results
uv run python -m ingestion.cli dataset-insights --results

# Explicitly trigger scan creation and execution
uv run python -m ingestion.cli dataset-insights --run

# Wait up to 5 minutes for results (default: 10 minutes)
uv run python -m ingestion.cli dataset-insights --results --timeout 300
```

**Resource targeting:**
- Dataset-level scan targets: `//bigquery.googleapis.com/projects/{project}/datasets/{dataset}`
- Scan ID format: `dataset-insights-{namespace}` (fixed, reusable)

**Results structure:**
- `description`: AI-generated dataset description
- `relationship_graph`: Nodes and edges showing table relationships
- `sample_queries`: Cross-table SQL query examples
- `discovered_primary_keys`: Table primary key discoveries
- `discovered_foreign_keys`: Cross-table foreign key relationships

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

# This deletes: Lakehouse REST catalog, BQ external tables, Dataplex entries/tags, glossary resources, Iceberg catalog
# Does NOT delete GCS data by default
```

### Lakehouse REST Catalog Setup
The Lakehouse REST Catalog provides a single source of truth for Iceberg metadata, enabling BigQuery, Spark, and Trino to discover tables via the same REST endpoint.

```bash
# 1. Create namespace and register tables via CLI
#    (catalog must exist before running setup-catalog)
uv run python -m ingestion.cli setup-catalog --catalog-name marketing-lakehouse --full
```

> **gcloud limitation with vended-credentials**
>
> For catalogs using **vended-credentials** mode, the gcloud CLI **cannot reliably create catalogs or register tables**. It does not properly send the `X-Iceberg-Access-Delegation: vended-credentials` header that BigLake requires in this mode.
>
> | Operation | gcloud + vended-credentials | Workaround |
> |-----------|----------------------------|------------|
> | Create catalog | ❌ Does not work | **GCP Console** → BigLake > Iceberg catalogs > Create catalog |
> | Register tables | ❌ Does not work | **This CLI** (uses Dataproc Spark) |

**Creating the Catalog:**

Catalogs using **vended-credentials** mode must be created via the **GCP Console**.

Navigate to: **BigLake > Iceberg catalogs > Create catalog**

Choose:
- Catalog type: **GCS bucket**
- Credential mode: **Vended credentials**

For more details, see the official documentation:
https://docs.cloud.google.com/lakehouse/docs/lakehouse-iceberg-rest-catalog#process

**Credential Modes:**
- `vended-credentials` (recommended for enterprise): Short-lived GCS tokens, no direct bucket access needed
- `end-user`: Users need direct GCS permissions

**Table Registration:**
The CLI automatically registers tables via **Dataproc Serverless (Managed Service for Apache Spark)**,
which properly handles the `X-Iceberg-Access-Delegation: vended-credentials` header.
No manual steps are required — `setup-catalog --full` submits a PySpark batch job that
registers all existing Iceberg tables using the `register_table` system procedure.

### Registering External or Custom Tables

The `register-table` command registers **arbitrary** existing Iceberg tables (not just the
built-in synthetic marketing tables). Use it when you have pre-existing Iceberg data
in GCS that needs to be registered in the Lakehouse REST Catalog.

**Key difference:**
- `setup-catalog --full` — registers the built-in tables (`audience`, `campaigns`, etc.) defined in `generators/config.py`
- `register-table` — registers any tables you specify by name and metadata location

#### Register a single external table
```bash
uv run python -m ingestion.cli register-table \
  --table-names my_table \
  --metadata-locations gs://my-bucket/my_table/metadata.json \
  --catalog-name marketing-lakehouse
```

#### Register multiple external tables
```bash
uv run python -m ingestion.cli register-table \
  --table-names t1,t2,t3 \
  --metadata-locations gs://b/t1/metadata.json,gs://b/t2/metadata.json,gs://b/t3/metadata.json \
  --catalog-name marketing-lakehouse \
  --namespace external
```

#### Preview without executing (dry-run)
```bash
uv run python -m ingestion.cli register-table \
  --table-names my_table \
  --metadata-locations gs://bucket/my_table/metadata.json \
  --dry-run
```

**Command options:**
- `--table-names` — comma-separated list of table names (required)
- `--metadata-locations` — comma-separated list of metadata.json GCS paths (required)
- `--catalog-name` — Lakehouse catalog name (defaults to config)
- `--namespace` — Iceberg namespace (defaults to config, e.g. `marketing`)
- `--data-project` — GCP project where data is stored
- `--iceberg-warehouse` — GCS path for Iceberg data
- `--dry-run` — preview actions without executing

### Programmatic Registration

For automation or custom scripts, use `LakehouseCatalogManager.register_external_tables()` directly:

```python
from ingestion.lakehouse_catalog import LakehouseCatalogManager
from generators.config import GeneratorConfig

config = GeneratorConfig(
    data_project_id="my-project",
    lakehouse_catalog_name="marketing-lakehouse",
    iceberg_namespace="marketing",
)

manager = LakehouseCatalogManager(config)

# Verify catalog exists
result = manager.ensure_catalog()
if not result["catalog_exists"]:
    raise RuntimeError("Catalog does not exist")

# Ensure namespace exists
manager.ensure_namespace()

# Register arbitrary tables
tables = {
    "external_a": "gs://other-bucket/external_a/metadata.json",
    "external_b": "gs://other-bucket/external_b/metadata.json",
}
result = manager.register_external_tables(tables=tables)
print(f"Registered {result['tables_registered']} tables")
```

This is the same mechanism the CLI `register-table` command uses internally.

**Key features:**
- Credential vending enables fine-grained access without users needing direct GCS permissions
- Tables accessible via BigQuery four-part name: `project.catalog.namespace.table`
- Spark/Trino can discover tables via the same REST endpoint

## 📊 Data Consumption & Analysis

Once the ingestion is complete, data is accessible through several interfaces:

### 1. BigQuery (Iceberg REST Catalog)
The tables are registered via the **Lakehouse REST Catalog** (Iceberg) which serves as a single source of truth. BigQuery accesses tables via four-part name:

```sql
-- Join transactions and cookies via the semantic synonym 'hem'
SELECT t.merchant_name, c.device_type, SUM(t.amount_usd) as revenue
FROM `project.marketing-lakehouse.marketing.transactions` t
JOIN `project.marketing-lakehouse.marketing.cookie_registry` c
  ON t.hem = c.hashed_email
GROUP BY 1, 2;
```

**Note:** The `marketing-lakehouse` catalog name is separate from the GCS bucket and enables Spark/Trino access via the same REST endpoint.

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
- **`LakehouseCatalogManager`** (`ingestion/lakehouse_catalog.py`): Manages Google Cloud Lakehouse REST Catalog for Iceberg metadata. Provides `register_tables()` for the built-in marketing tables and `register_external_tables()` for arbitrary table registration
- **`DataplexManager`** (`ingestion/dataplex_lake.py`): Manages Dataplex lake topology and asset registration
- **`CatalogManager`** (`ingestion/catalog.py`): Creates and manages Dataplex catalog entries

### Metadata & Governance
- **`TagWriter`** (`ingestion/tag_writer.py`): Applies Dataplex tags to tables based on YAML metadata
- **`GlossaryWriter`** (`ingestion/glossary_writer.py`): Legacy wrapper for glossary operations (delegates to BusinessGlossaryManager)
- **`BusinessGlossaryManager`** (`ingestion/glossary_manager.py`): Manages Dataplex business glossary creation and term linking
- **`HybridMetadataEnricher`** (`ingestion/table_and_column_insights.py`): Enriches tables with pure metadata (manual OR Google Insights, not combined)

### Data Quality & Analysis
- **`DataProfilingManager`** (`ingestion/data_profiling.py`): Creates and runs Dataplex data profile scans for statistical analysis (row counts, distributions, patterns)
- **`DataQualityManager`** (`ingestion/data_quality.py`): Creates and runs Dataplex data quality scans with marketing-specific validation rules

### Advanced Features
- **`VectorSearchManager`** (`ingestion/vector_search.py`): Sets up BigQuery Vector Search with embedding models and indexes
- **`BQMLGeminiManager`** (`ingestion/bqml_gemini.py`): Manages BigQuery ML Gemini remote model setup and text generation
- **`ContinuousQueryManager`** (`ingestion/continuous_queries.py`): Sets up BigQuery continuous queries for real-time aggregation