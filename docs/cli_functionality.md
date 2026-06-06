# CLI Functionality Reference

This document describes the current command surface implemented in `ingestion/cli.py`.

## Overview

The CLI is focused on metadata and governance operations around an existing marketing lakehouse:
- Lakehouse REST catalog verification and namespace setup
- Dataplex topology, catalog entries, tags, and glossary
- Metadata enrichment (manual YAML and Dataplex insights)
- Dataplex scans (dataset insights, profiling, data quality)
- BigQuery setup helpers (vector search, BQML Gemini, continuous queries)

## Configuration behavior

Most commands instantiate `Config()` from `ingestion/config.py`.

### Project resolution priority
1. Explicit CLI flags (for commands that expose overrides)
2. Current `gcloud` project (`gcloud config get-value project`)
3. `GOOGLE_CLOUD_PROJECT` environment variable
4. Fallback default: `wpp-dataproducts-lakehouse`

### Core defaults
- `iceberg_namespace`: `marketing`
- `location`: `us-east1`
- `lakehouse_catalog_name`: empty by default (must be provided for catalog-dependent operations)

## Typical workflow

### 1) Verify catalog and create namespace
```bash
uv run python -m ingestion.cli setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full
```

### 2) Register Dataplex assets, entries, tags, and glossary
```bash
uv run python -m ingestion.cli catalog \
  --catalog-name YOUR_CATALOG_NAME
```

### 3) Apply metadata descriptions
```bash
# Apply manual metadata from metadata/*.yaml
uv run python -m ingestion.cli enrich-metadata

# Or use Dataplex-generated insights only
uv run python -m ingestion.cli enrich-metadata --google-insights
```

### 4) Run quality and profiling scans
```bash
uv run python -m ingestion.cli quality
uv run python -m ingestion.cli profile
```

## Command reference

### `catalog`
Registers Iceberg tables in Dataplex catalog resources and applies tags/glossary.

```bash
uv run python -m ingestion.cli catalog \
  --catalog-name YOUR_CATALOG_NAME
```

Options:
- `--data-project`: project where data resources are hosted
- `--catalog-project`: project where Dataplex catalog resources are hosted
- `--iceberg-warehouse`: warehouse path (for example `gs://bucket/iceberg`)
- `--biglake-connection`: explicit BigLake connection template
- `--catalog-name`: Lakehouse REST catalog name (required in practice)

Notes:
- If catalog name is missing, the command exits early with guidance.
- The command verifies catalog existence and creates namespace before Dataplex registration steps.

### `setup-catalog`
Verifies catalog existence and optionally creates namespace.

```bash
# Verify only
uv run python -m ingestion.cli setup-catalog --catalog-name YOUR_CATALOG_NAME

# Verify + namespace
uv run python -m ingestion.cli setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full

# Preview
uv run python -m ingestion.cli setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full \
  --dry-run
```

Options:
- `--catalog-name` (required)
- `--dry-run`
- `--full`

### `enrich-metadata`
Updates table and column descriptions in BigQuery.

Modes:
- Manual metadata mode (`metadata/*.yaml`)
- Google insights mode (`--google-insights`)

Examples:
```bash
# All tables, manual metadata mode
uv run python -m ingestion.cli enrich-metadata

# All tables, Google insights mode
uv run python -m ingestion.cli enrich-metadata --google-insights

# Specific tables with explicit metadata files
uv run python -m ingestion.cli enrich-metadata \
  --table-names audience,campaigns \
  --metadata-files audience_profile.yaml,campaigns.yaml

# Specific tables, Google insights mode
uv run python -m ingestion.cli enrich-metadata \
  --table-names campaigns,transactions \
  --google-insights

# Preview only
uv run python -m ingestion.cli enrich-metadata --dry-run
```

Options:
- `--table-names` comma-separated list
- `--metadata-files` comma-separated list (required for `--table-names` in manual mode)
- `--google-insights`
- `--dry-run`

### `create-templates`
Creates template files for metadata and glossary management.

```bash
uv run python -m ingestion.cli create-templates
```

### `manage-glossary`
Manages Dataplex business glossary resources from `metadata/glossary.yaml` (or a custom file).

```bash
# Preview
uv run python -m ingestion.cli manage-glossary --dry-run

# Create
uv run python -m ingestion.cli manage-glossary --action create

# Validate
uv run python -m ingestion.cli manage-glossary --action validate

# Apply term-to-asset links
uv run python -m ingestion.cli manage-glossary --action apply

# Reset glossary resources
uv run python -m ingestion.cli manage-glossary --action reset
```

Options:
- `--action`: `create`, `validate`, `apply`, `reset`
- `--input`: glossary YAML path
- `--dry-run`
- `--reset` (pre-reset before create)

### `dataset-insights`
Creates and/or runs a dataset-level Dataplex DATA_DOCUMENTATION scan.

```bash
# Create and run (default)
uv run python -m ingestion.cli dataset-insights

# Preview only
uv run python -m ingestion.cli dataset-insights --dry-run

# Read latest results
uv run python -m ingestion.cli dataset-insights --results --timeout 300
```

Options:
- `--dry-run`
- `--results`
- `--run`
- `--timeout` (seconds, default `600`)

### `profile`
Creates and runs Dataplex data profiling scans.

```bash
uv run python -m ingestion.cli profile
uv run python -m ingestion.cli profile --dry-run
uv run python -m ingestion.cli profile --results
```

### `quality`
Compares, syncs, runs, and reports Dataplex data quality scans.

Rules are loaded from `metadata/*.yaml` (`data_quality_rules` sections).

```bash
# Default behavior: sync + run
uv run python -m ingestion.cli quality

# Compare configured rules vs active scan rules
uv run python -m ingestion.cli quality --check-rules

# Sync rules without running scans
uv run python -m ingestion.cli quality --sync-only

# Preview sync actions
uv run python -m ingestion.cli quality --sync-only --dry-run

# Results view
uv run python -m ingestion.cli quality --results

# Restrict to tables
uv run python -m ingestion.cli quality --table-names campaigns,transactions
```

Options:
- `--dry-run`
- `--results`
- `--check-rules`
- `--sync-only`
- `--run`
- `--table-names`

### `vector-search`
Sets up BigQuery vector-search resources.

```bash
uv run python -m ingestion.cli vector-search
uv run python -m ingestion.cli vector-search --dry-run
```

### `bqml-setup`
Sets up BigQuery ML Gemini remote-model resources and sample queries.

```bash
uv run python -m ingestion.cli bqml-setup
uv run python -m ingestion.cli bqml-setup --dry-run
```

### `continuous-queries`
Sets up BigQuery continuous-query resources.

```bash
# Dry-run by default
uv run python -m ingestion.cli continuous-queries

# Execute setup
uv run python -m ingestion.cli continuous-queries --dry-run false
```

### `list-related-entries`
Finds catalog entries whose schema contains a column matching a given glossary term.

Given a glossary term (e.g. `advertiser`), searches all Dataplex catalog entries and returns those that contain a matching column, along with the Resource Name, Column Name, Project, and Fully Qualified Name.

```bash
# Search for all entries with a column matching 'advertiser'
uv run python -m ingestion.cli list-related-entries --term advertiser

# Specify a glossary
uv run python -m ingestion.cli list-related-entries --term brand \
  --glossary marketing-business-glossary
```

Options:
- `--term` (required): glossary term to search for (e.g. `advertiser`)
- `--glossary`: glossary ID or display name (default: first glossary found)

### `scan-for-related-entries`
Compares a BigLake catalog against a glossary to find matching and unmatched terms using exact, synonym, and fuzzy semantic matching.

This command scans all table columns in the specified BigLake catalog and matches them against glossary terms. It produces a two-phase report:

- **Phase A — Exact & Synonym Matches**: terms that have a direct column name match or match via a synonym relationship defined in the glossary.
- **Phase B — Fuzzy Semantic Proposals**: for terms with no exact match, a keyword-based scoring system proposes candidate columns based on the term's description. Columns are scored by exact keyword match (+10), substring match (+5), and table-name match (+3).

When `--output` is provided, Phase B proposals are written to a YAML file that can be curated (rows removed or commented out) and then applied with `apply-related-entries`.

```bash
# Scan catalog against default glossary
uv run python -m ingestion.cli scan-for-related-entries \
  --catalog wpp-dataproducts-lakehouse-warehouse

# Scan with namespace filter
uv run python -m ingestion.cli scan-for-related-entries \
  --catalog wpp-dataproducts-lakehouse-warehouse \
  --namespace marketing

# Specify glossary explicitly
uv run python -m ingestion.cli scan-for-related-entries \
  --catalog wpp-dataproducts-lakehouse-warehouse \
  --glossary marketing-business-glossary

# Export proposals to YAML for curation
uv run python -m ingestion.cli scan-for-related-entries \
  --catalog wpp-dataproducts-lakehouse-warehouse \
  --namespace marketing \
  --output proposals.yaml \
  --fuzzy-score-threshold 10
```

Options:
- `--catalog` (required): BigLake catalog name to scan
- `--namespace`: optional namespace filter within the catalog
- `--glossary`: glossary ID or display name (default: first glossary found)
- `--output` / `-o`: write Phase B proposals to a YAML file for curation and later apply
- `--fuzzy-score-threshold`: filter out fuzzy proposals with a score below this threshold
- `--project`: override the Google Cloud project written into the exported YAML (default: derived from the discovered glossary's resource path)
- `--location`: override the location written into the exported YAML (default: derived from the discovered glossary's resource path)

The project and location used when `--output` is given are resolved in this order:
1. explicit `--project` / `--location` flag
2. project and location parsed out of the discovered glossary's `name` (e.g. `projects/{p}/locations/{l}/glossaries/{id}`)
3. the values from `Config`

This avoids writing a silent fallback (e.g. a placeholder project string) into the YAML, so the subsequent `apply-related-entries` step targets the correct Dataplex project.

#### Workflow for `scan-for-related-entries`

Below is a step-by-step description of what happens when you run the command:

1. **Glossary discovery** — The CLI resolves the glossary (either the one specified via `--glossary` or the first glossary in the project/location). It lists all terms and their categories.
2. **BigLake entry listing** — All entries in the `@biglake` entry group are listed. Only table-type entries are kept; optionally filtered to a single namespace via `--namespace`.
3. **Schema extraction** — For each table entry, the CLI fetches the full entry description (including schema aspects) and extracts all column names.
4. **Phase A — Exact & synonym matching** — Each glossary term is compared against the extracted column names:
   - A direct match occurs when the normalized term name equals a normalized column name.
   - Synonym matching checks whether a term's description starts with "Synonym for <canonical-term>" and inherits the canonical term's match if one exists.
5. **Phase B — Fuzzy semantic matching** — Terms not matched in Phase A are processed by tokenizing their description into keywords (filtering stop words). Each column/table is scored against those keywords. Proposals are sorted by score (highest first) so the most likely matches appear at the top.
6. **Report output** — A summary is printed showing glossary and catalog statistics, the Phase A matches table, and the Phase B proposals table with scores and match rationale.

### `apply-related-entries`
Applies curated related-entry proposals from a YAML file to Dataplex Catalog.

This command reads a proposals file (produced by `scan-for-related-entries --output`), validates each proposal, and creates **Dataplex entry-links** of type `entryLinkTypes/definition` via the `gcloud alpha dataplex entry-links create` subcommand. Each link is a `term ↔ asset` relation between a glossary-term entry and a BigLake table entry. The command is idempotent: existing relations (gcloud's `ALREADY_EXISTS` error) are skipped with an informational message rather than duplicated.

The link is created in the **`@biglake`** entry-group (the SOURCE entry's group, which the API requires for a `definition` link) with the BigLake entry listed first as `SOURCE` and the term entry second as `TARGET`.

#### Workflow

1. **Scan** — `scan-for-related-entries --output proposals.yaml` exports proposals.
2. **Curate** — A data steward edits `proposals.yaml`, removing incorrect rows.
3. **Preview** — `apply-related-entries --input proposals.yaml --dry-run` validates and previews.
4. **Apply** — `apply-related-entries --input proposals.yaml` creates the entry-links.

```bash
# Preview changes
uv run python -m ingestion.cli apply-related-entries \
  --input proposals.yaml --dry-run

# Execute
uv run python -m ingestion.cli apply-related-entries \
  --input proposals.yaml

# Override glossary
uv run python -m ingestion.cli apply-related-entries \
  --input proposals.yaml --glossary my-glossary

# Override project and location
uv run python -m ingestion.cli apply-related-entries \
  --input proposals.yaml --project my-project --location eu-west1
```

Options:
- `--input` (required): path to curated proposals YAML file
- `--dry-run`: validate and preview; do not mutate
- `--glossary`: override glossary ID from the file
- `--project`: override the Google Cloud project
- `--location`: override the location (default: from file or `us-east1`)

#### How the link is created

For each curated row, the CLI:

1. Pre-flights a `gcloud dataplex entries describe` against the BigLake entry to surface actionable errors for typos in catalog/table/namespace.
2. Resolves the GCP project **number** for the catalog project (via `gcloud projects describe`) — the Dataplex API requires the project number in entry-name references and rejects the project ID with "Entry ID must contain project number."
3. Builds the BigLake entry resource path (SOURCE) using the project number on the outer Dataplex path and the project ID on the inner BigLake segment:
   `projects/{project_number}/locations/{location}/entryGroups/@biglake/entries/biglake.googleapis.com/projects/{project_id}/catalogs/{catalog}/namespaces/{ns}/tables/{table}`
4. Builds the term-entry resource path (TARGET) using the project number on both outer and inner segments:
   `projects/{project_number}/locations/{location}/entryGroups/@dataplex/entries/projects/{project_number}/locations/{location}/glossaries/{glossary_id}/terms/{term_slug}`
   The inner project segment is read from the first term's `parent` resource path (so the link targets the right Dataplex project even when terms live in a different project from the catalog).
5. Computes a deterministic entry-link id: `definition-{term_slug}-{ns}-{table_slug}` truncated to 63 chars (the Dataplex resource-id limit). Both the term name and the table name are slugified (lowercase, spaces/underscores → hyphens) so the id only contains `[a-z0-9-]`.
6. Invokes `gcloud alpha dataplex entry-links create`:
   ```
   gcloud alpha dataplex entry-links create <entry_link_id> \
     --entry-group=@biglake \
     --location=<location> \
     --project=<project> \
     --entry-link-type=projects/dataplex-types/locations/global/entryLinkTypes/definition \
     --entry-references=<tempfile.yaml>
   ```
   where `<tempfile.yaml>` contains:
   ```yaml
   - name: <biglake_entry_ref>
     type: SOURCE
   - name: <term_entry_ref>
     type: TARGET
   ```
7. Maps the gcloud exit code to an `ApplyResult`: `created` on exit 0, `skipped` on `ALREADY_EXISTS`, `error` on any other failure. The raw gcloud stderr is surfaced in the `detail` column.

When a row fails (e.g. the target entry does not exist on the project), the summary includes the underlying error in the `detail` column — the raw gcloud error from the pre-flight describe, or the raw gcloud stderr from `entry-links create` (e.g. `Permission denied: dataplex.googleapis.com`) — instead of a generic "Entry not found" message. This makes it easy to spot IAM or project-mismatch issues.

### `reset`
Deletes generated metadata resources for a clean re-run.

```bash
# Required confirmation flag
uv run python -m ingestion.cli reset --confirm
```

Behavior:
- Deletes Iceberg namespace (catalog deletion remains manual)
- Resets glossary resources
- Deletes Dataplex entries for configured tables

## Source files
- CLI entrypoint: `ingestion/cli.py`
- Config model: `ingestion/config.py`
- Metadata parsing: `ingestion/table_metadata.py`
- Glossary manager: `ingestion/glossary_manager.py`
- Data quality manager: `ingestion/data_quality.py`
- Related entries manager: `ingestion/related_entries.py` (includes proposals export/import, the gcloud-based entry-link creation helper, and the apply logic that targets `entryLinkTypes/definition`)
