# Data Generation - Synthetic Marketing Data Platform

## 🎯 Project Purpose
The primary goal of this project is to demonstrate the value of the **Dataplex Knowledge Catalog** through agent-based data discovery and analysis. By generating high-fidelity synthetic marketing data and registering it with rich metadata, we showcase how AI agents can navigate complex data estates, resolve semantic synonyms, and perform cross-channel attribution without prior knowledge of the physical schema.

## 📈 Marketing Use Cases
The platform is designed to support four foundational marketing scenarios:
*   **Audience Discovery**: Identifying demographics and interest traits that over-index for specific products and locating their geographic clusters.
*   **Audience Performance Prediction**: Forecasting response rates and identifying similar audience cohorts for lookalike modeling.
*   **Content Performance Prediction**: Comparing the effectiveness of individual creative assets across multiple campaigns and time windows.
*   **Post-Campaign Analysis**: Aggregating performance metrics (Impressions, CTR, ROAS) across regions and markets.

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

### 6. YAML-Driven Configuration

Almost all metadata in this project is controlled via YAML files — **no code changes are needed** to modify catalog descriptions, tag values, synonym column mappings, or glossary terms. The three YAML-driven systems are:

| System | File(s) | What it controls |
|--------|---------|------------------|
| **Table metadata** | `metadata/*.yaml` | Catalog display names, descriptions, Dataplex tag values, column descriptions, synonym column mappings |
| **Business glossary** | `metadata/glossary.yaml` | Dataplex glossary terms, synonym links, related-term links, term-to-table definition links |
| **Column descriptions** | (same as table metadata) | BigQuery column descriptions applied via `enrich-metadata` |

#### Table Metadata File Format (`metadata/<table>.yaml`)

Each table has a YAML file that drives **four concerns** at once:

```yaml
table_id: audience
display_name: Audience Profile
description: >
  Description paragraph(s). This becomes the Dataplex catalog entry description.

tags:
  business_owner: Marketing Data Products
  data_domain: audience
  pii_class: pseudonymous
  refresh_cadence: daily
  row_count_approx: 8000
  marketing_usecases: audience_discovery,audience_performance_prediction

columns:
  - name: audience_id
    description: Surrogate primary key (UUID v4).
  - name: hem
    description: SHA-256 of normalised email. ~60% populated.
  - name: lat
    description: Centroid latitude of dominant geo cluster.
  - name: location_lat
    description: Synonym for lat.
    synonym_of: lat
  - name: location_lon
    description: Synonym for lon.
    synonym_of: lon
```

**How each section is consumed:**
*   `display_name` → `catalog.py` uses this as the Dataplex entry display name
*   `description` → `catalog.py` uses this as the entry description
*   `tags` → `tag_writer.py` applies these as the `marketing_table_metadata` aspect fields
*   `columns` → `enrich-metadata` applies these as BigQuery column descriptions
*   `synonym_of: <column>` → the orchestrator copies the source column's values into the synonym column at generation time

#### Adding a New Data Source

When integrating a new table into the lakehouse:
1.  **Create `metadata/<table_name>.yaml`** with the display name, description, `tags`, and `columns` sections. This single file configures catalog entries, tags, and column descriptions.
2.  **Write a generator** in `generators/` that produces the base columns. Synonym columns should be included in the schema but left as `None` — the orchestrator fills them from the metadata.
3.  **Add the table to the orchestrator** (`generators/orchestrator.py`)
4.  **Add glossary terms** to `metadata/glossary.yaml` if the table introduces new canonical terms or synonyms
5.  Run `uv run python -m ingestion.cli generate --local` then `validate --local` to verify

## 🌍 Markets & Brands
The data generation covers three target markets with realistic variation in data quality:
*   **Markets**: US, UK, Japan.
*   **Fictional Brands**: Lucky Cola, Force Automotive, AEKI Living.
*   **Regional Variation**: Join success rates are adjusted per market (US baseline, UK -5pp, Japan -10pp) to simulate real-world identity resolution challenges.

## 📊 Data Generation Logic

The synthetic data generation includes realistic patterns and variations that can be controlled through configuration:

### Data Flow and BigQuery Visibility

It's important to understand the two main stages for data to appear in BigQuery:

1.  **Data Generation (`generate` command):** This step creates the synthetic data and writes it to a storage location.
    *   By default, `uv run python -m ingestion.cli generate` will save data locally as Parquet files in the `local_output/` directory. This is for quick local testing and development.
    *   To write data to Google Cloud Storage (GCS) as Iceberg tables, you must explicitly use the `--no-local` flag: `uv run python -m ingestion.cli generate --no-local`. The data will be stored in the GCS bucket configured for the Iceberg warehouse.
    *   **Crucially, after this step, the data is ONLY in the specified storage location (local or GCS). It is NOT yet visible in BigQuery.**

2.  **Catalog Registration (`catalog` command):** This separate step is required to make the GCS-based Iceberg data accessible and queryable within BigQuery.
    *   The command `uv run python -m ingestion.cli catalog` reads the Iceberg metadata from your GCS warehouse and registers these tables as BigLake external tables in your BigQuery dataset.
    *   **Only after successfully running the `catalog` command will the data appear in BigQuery.**

For a full, end-to-end process that includes both generation (to GCS) and catalog registration, use the `ingest` command:

```bash
uv run python -m ingestion.cli ingest
```

This command automates both steps, ensuring your generated data is written to GCS and immediately made available in BigQuery.

### Controlling Generator Size and Match Rates

You can control the size of generated data and match rates through:

1. **CLI Flag**: Use `--full-scale` for production-scale data generation:
   ```bash
   uv run python -m ingestion.cli generate --full-scale
   ```

2. **Configuration File**: Modify `generators/config.py` to customize:
   - Row counts for each table (`n_audience_participants`, `n_campaigns`, etc.)
   - Fill rates for relationships (`audience_hem_fill_rate`, `cookie_audience_fill_rate`, etc.)
   - Market-specific match rates in the `market_txn_rates` dictionary

3. **Default vs Full Scale**:
   - Default (development): Smaller dataset for quick testing
   - Full Scale: Production-sized dataset with realistic volumes

### Key Configuration Parameters

| Parameter | Default Value | Full Scale Value | Description |
|-----------|---------------|------------------|-------------|
| `n_audience_participants` | 100 | 8,000 | Number of audience participants |
| `n_campaigns` | 10 | 200 | Number of marketing campaigns |
| `n_pixel_events` | 5,000 | 2,000,000 | Number of pixel events |
| `n_transactions` | 1,000 | 500,000 | Number of transactions |
| `audience_hem_fill_rate` | 0.60 | 0.60 | % of audience with hashed email |
| `cookie_audience_fill_rate` | 0.40 | 0.40 | % of cookies linked to audience |
| `pixel_cookie_fill_rate` | 0.82 | 0.82 | % of pixel events with cookie ID |

### Market-Specific Variations

Transaction match rates vary by market to simulate real-world conditions:

| Market | Cookie Fill Rate | HEM Fill Rate |
|--------|------------------|---------------|
| US | 30% | 25% |
| UK | 20% | 15% |
| Japan | 15% | 10% |

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

## Extending Current Tables

### Adding New Columns
To add a new column to an existing table:
1. Update the table's schema in the appropriate generator
2. Add the column to the metadata YAML file with description
3. For synonym columns, add the `synonym_of` key
4. Update the data generation logic to populate values

### Creating New Synonym Relationships
1. Add the new column to the schema with `None` values
2. Add to metadata YAML with `synonym_of` reference
3. Update glossary.yaml with the new synonym relationship

### Modifying Data Generation Logic
1. Locate the appropriate generator in `generators/`
2. Modify the data generation methods
3. Update any related schemas or metadata
4. Test with `generate --local` and `validate --local`

### Adding Entirely New Tables
1. Create new metadata file in `metadata/`
2. Create new generator class in `generators/`
3. Add to orchestrator in `generators/orchestrator.py`
4. Update glossary if needed
5. Test locally before full ingestion