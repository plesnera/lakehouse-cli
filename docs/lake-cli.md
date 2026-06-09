# CLI Functionality Reference

This document describes every command implemented in `lake_cli/cli.py` and what
each one actually does, both at the surface and (where useful) one layer below.

## Overview

The CLI is focused on metadata and governance operations around an existing
marketing lakehouse:

- Lakehouse REST catalog verification and namespace setup
- Dataplex topology, catalog entries, tags, and glossary
- Metadata enrichment (manual YAML and Dataplex insights)
- Dataplex scans (dataset insights, profiling, data quality)
- BigQuery setup helpers (vector search, BQML Gemini, continuous queries)
- Glossary ↔ table linking via Dataplex `entryLinkTypes/definition`

The CLI is a thin Typer wrapper. Each command instantiates `Config()` and
delegates to a manager class. See "Source files" at the bottom.

## Configuration behavior

Most commands instantiate `Config()` from `lake_cli/config.py`.

### Project resolution priority

1. Explicit CLI flags (for commands that expose overrides)
2. Current `gcloud` project (`gcloud config get-value project`)
3. `GOOGLE_CLOUD_PROJECT` environment variable
4. If none of the above yields a project, `Config.get_current_gcloud_project`
   returns `None` and the field validation in pydantic raises — there is no
   silent literal fallback. Set `GOOGLE_CLOUD_PROJECT` or run
   `gcloud config set project` before invoking the CLI.

### Core defaults

- `iceberg_namespace`: `marketing`
- `location`: `us-east1`
- `lakehouse_catalog_name`: empty by default (must be provided for
  catalog-dependent operations; the `catalog` and `setup-catalog` commands
  require `--catalog-name`)

## Typical workflow

```bash
# 1) Verify catalog and create namespace
uv run lake setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full

# 2) Register Dataplex assets, entries, tags, and glossary
uv run lake catalog \
  --catalog-name YOUR_CATALOG_NAME

# 3) Apply metadata descriptions
uv run lake enrich-metadata             # manual mode (metadata/*.yaml)
uv run lake enrich-metadata --google-insights   # Dataplex-generated only

# 4) Run quality and profiling scans
uv run lake quality
uv run lake profile
```

## Command reference

The 15 commands are listed in the order they appear in `lake --help`.

### `catalog`

Runs the full cataloging pipeline: verifies the Lakehouse REST catalog, creates
the namespace, then orchestrates five managers in sequence:

1. `LakehouseCatalogManager.ensure_catalog` / `ensure_namespace` — verify the
   catalog exists, then create the configured namespace if missing.
2. `DataplexManager.ensure_topology` + `register_assets` — set up the
   BigQuery asset-aspect entries that point at the Iceberg tables.
3. `CatalogManager.ensure_entry_group` + `ensure_entry_type` + `register_entries`
   — create the Dataplex entry group / type and register one entry per table.
4. `TagWriter.ensure_tag_template` + `apply_tags` — create the configured tag
   template and apply tags to all entries.
5. `BusinessGlossaryManager` — apply the configured glossary to entries.

If the catalog name is missing, the command exits early with guidance.

```bash
uv run lake catalog \
  --catalog-name YOUR_CATALOG_NAME
```

Options:
- `--catalog-name` (required in practice): Lakehouse REST catalog name
- `--data-project`: project where data resources are hosted
- `--catalog-project`: project where Dataplex catalog resources are hosted
- `--iceberg-warehouse`: warehouse path (for example `gs://bucket/iceberg`)
- `--biglake-connection`: explicit BigLake connection template
- `--full`: register all tables (default behaviour; flag exists for explicitness)
- `--reset-glossary`: tear down the existing glossary before re-applying

### `setup-catalog`

Verifies the Lakehouse REST catalog exists and (with `--full`) creates the
namespace. Does **not** create the catalog itself — that is a manual step.

> The catalog must be created MANUALLY before running this command. For
> vended-credentials mode, use the GCP Console (gcloud does not support the
> required `X-Iceberg-Access-Delegation` header):
> <https://docs.cloud.google.com/lakehouse/docs/lakehouse-iceberg-rest-catalog#process>
> See `docs/iceberg_rest_implementations.md` for the full operational notes.

```bash
# Verify only (does not create the namespace)
uv run lake setup-catalog --catalog-name YOUR_CATALOG_NAME

# Verify and create the namespace
uv run lake setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full

# Preview what would be done
uv run lake setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full \
  --dry-run
```

Options:
- `--catalog-name` (required)
- `--dry-run`: preview without executing
- `--full`: also create the namespace (without it, the command only verifies)

### `enrich-metadata`

Updates table and column descriptions in BigQuery. Two mutually exclusive
modes — they are never combined in the same run (see AGENT.md §3.A):

- **Manual mode (default):** reads `metadata/<table>.yaml` (one YAML per table
  in the preset marketing set) and applies the descriptions. The YAML files
  are written by `create-templates` and edited by hand.
- **Google Insights mode (`--google-insights`):** fires a one-time
  Dataplex `DATA_DOCUMENTATION` scan per table, polls for results, and applies
  the generated descriptions.

```bash
# All tables, manual mode
uv run lake enrich-metadata

# All tables, Google Insights mode
uv run lake enrich-metadata --google-insights

# Specific tables with explicit metadata files (manual mode)
uv run lake enrich-metadata \
  --table-names audience,campaigns \
  --metadata-files audience_profile.yaml,campaigns.yaml

# Specific tables, Google Insights mode
uv run lake enrich-metadata \
  --table-names campaigns,transactions \
  --google-insights

# Preview only
uv run lake enrich-metadata --dry-run
```

Options:
- `--table-names`: comma-separated list of tables
- `--metadata-files`: comma-separated list of YAML files (must match
  `--table-names` in order)
- `--google-insights`: switch to Dataplex-generated descriptions
- `--dry-run`: preview metadata changes without applying them

### `create-templates`

Generates starter YAML files in the `metadata/` directory so you can fill in
table/column descriptions by hand before running `enrich-metadata` in manual
mode. Two things happen:

1. `HybridMetadataEnricher.create_all_templates` lists every table in the
   configured BigQuery dataset and writes `metadata/<table>.yaml` for any
   that does not already have a corresponding file (it scans existing files
   by `table_id` first, so `audience_profile.yaml` will not be duplicated
   if it already represents the `audience` table).
2. `BusinessGlossaryManager.generate_template_files` writes
   `metadata/glossary.yaml` if it does not already exist. If a bundled
   glossary template ships in the repo, it is copied verbatim; otherwise a
   minimal default is generated.

Re-runs are safe: existing files are not overwritten. To regenerate a file,
delete it first.

```bash
uv run lake create-templates
```

This command takes no options.

### `manage-glossary`

Manages Dataplex business glossary resources from `metadata/glossary.yaml` (or
a custom file via `--input`). Glossary resources are created via the dedicated
Dataplex Glossary REST API (glossaries, categories, terms, and
synonym/related entryLinks), not via generic catalog entryLinks.

The `--action` flag selects the sub-mode. The default action is `create`.

```bash
# Preview the parsed glossary (no Dataplex calls)
uv run lake manage-glossary --dry-run

# Create glossary, categories, terms, and links
uv run lake manage-glossary --action create

# Create from a custom file
uv run lake manage-glossary --action create --input my_glossary.yaml

# Reset glossary resources before creating
uv run lake manage-glossary --action create --reset

# Validate glossary YAML structure (no Dataplex calls)
uv run lake manage-glossary --action validate

# Link terms to BigQuery assets
uv run lake manage-glossary --action apply

# Reset glossary resources
uv run lake manage-glossary --action reset
```

Options:
- `--action`: `create`, `validate`, `apply`, or `reset` (default: `create`)
- `--input`: glossary YAML path (default: `metadata/glossary.yaml`)
- `--dry-run`: parse and print the plan without creating any Dataplex
  resources. Only meaningful with `--action create`; the other actions
  ignore it.
- `--reset`: delete all glossary resources before creating (use with
  `--action create`)

What each action does:
- `create` — parse the file, print a summary, then call `_print_dry_run` if
  `--dry-run`, otherwise upsert the glossary + categories + terms +
  synonym/related links via REST. Synonym/related terms that do not exist
  as real terms are created as implicit terms in the same glossary.
- `validate` — parse the file and check structure; prints any errors found.
- `apply` — link existing glossary terms to BigQuery assets (one
  tag-style aspect per term on the entry's aspects).
- `reset` — delete all glossary resources in the project before recreating.

### `dataset-insights`

Creates and/or runs a dataset-level Dataplex `DATA_DOCUMENTATION` scan that
analyzes an entire BigQuery dataset to produce:

- AI-generated dataset description
- Relationship graph (how tables connect)
- Cross-table SQL sample queries
- Discovered primary/foreign key relationships

Results are written to BigQuery as table labels / published tables once the
asynchronous scan completes. Use `--results` to fetch the latest result JSON
locally.

```bash
# Create and run the scan (default behaviour)
uv run lake dataset-insights

# Preview scan creation without executing
uv run lake dataset-insights --dry-run

# Explicitly run a scan that was created but not executed
uv run lake dataset-insights --run

# Read the latest results to a local JSON file
uv run lake dataset-insights --results
uv run lake dataset-insights --results -o my_insights.json
uv run lake dataset-insights --results --timeout 300
```

Options:
- `--dry-run`: preview scan creation without executing
- `--run`: run the scan explicitly (when you created it on a previous call
  without executing)
- `--results`: show latest insights results instead of creating a scan
- `--timeout`: seconds to wait for results (default: `600`)
- `--output` / `-o`: output file path for insights results (default:
  `dataset_insights.json`)

### `profile`

Creates and runs Dataplex data profiling scans for all configured tables
(reads `Config.TABLES`). Profiling scans produce per-column statistics
(null fraction, distinct count, min/max, top-N values, histograms) and are
useful for discovering data-shape issues before they hit downstream consumers.

```bash
# Create and run scans
uv run lake profile

# Preview without creating
uv run lake profile --dry-run

# Read latest profiling results instead of creating scans
uv run lake profile --results
```

Options:
- `--dry-run`: print plan without creating scans
- `--results`: show latest profiling results instead of creating scans

### `quality`

Full lifecycle management for Dataplex data quality scans. Rules are loaded
from the `data_quality_rules` section of each `metadata/<table>.yaml` file.
The action flags are mutually exclusive; if none are provided, the command
defaults to `--run` (i.e. sync rules and run scans).

```bash
# Sync rules and run scans (default)
uv run lake quality

# Compare configured rules vs active Dataplex rules (no changes)
uv run lake quality --check-rules

# Sync rules without running scans
uv run lake quality --sync-only

# Preview sync actions
uv run lake quality --sync-only --dry-run

# Run scans only (skip rule sync)
uv run lake quality --run

# Restrict to a subset of tables
uv run lake quality --table-names campaigns,transactions

# View results of previous runs
uv run lake quality --results
```

Options:
- `--dry-run`: print plan without creating scans
- `--results`: show latest quality results instead of creating scans
- `--check-rules`: compare configured rules with active Dataplex rules
- `--sync-only`: sync rules without running scans
- `--run`: run scans (implied if no other action flags are given)
- `--table-names`: comma-separated list of tables to process

### `vector-search`

Sets up BigQuery Vector Search on the marketing dataset by running four SQL
steps in order. Each step prints its SQL (in `--dry-run`) or executes it
against BigQuery and waits for completion:

1. `CREATE OR REPLACE MODEL` — remote text-embedding model
   (`embedding_model` in the configured dataset) using the configured
   BigLake connection.
2. Generate audience-segment embeddings from text columns.
3. Create a vector index on the generated embeddings.
4. Run an example `VECTOR_SEARCH` query demonstrating semantic similarity.

Use `--dry-run` to inspect the SQL before executing. Failures in any step
are printed but do not abort the loop.

```bash
uv run lake vector-search
uv run lake vector-search --dry-run
```

Options:
- `--dry-run`: print SQL without executing

### `bqml-setup`

Sets up BigQuery ML Gemini remote-model resources and runs four demonstration
SQL steps:

1. `CREATE OR REPLACE MODEL` — remote Gemini text-generation model
   (`gemini_model`) using the configured BigLake connection.
2. Summarise campaign performance.
3. Classify creative themes.
4. Generate creative recommendations.

Steps 2–4 print the first row of the result for quick verification. Failures
in any step are printed but do not abort the loop.

```bash
uv run lake bqml-setup
uv run lake bqml-setup --dry-run
```

Options:
- `--dry-run`: print SQL without executing

### `continuous-queries`

Generates (and optionally executes) BigQuery continuous-query SQL that
aggregates pixel events for real-time CTR. The continuous query creates a
destination table and a query that runs continuously as new pixel events
arrive.

> Continuous queries require an **Enterprise reservation** with a
> `CONTINUOUS` job type and incur ongoing slot charges. This command
> defaults to `--dry-run` to prevent accidental execution. Pass
> `--no-dry-run` to actually execute.

```bash
# Print the SQL (default — safe)
uv run lake continuous-queries

# Execute the SQL (requires Enterprise reservation + CONTINUOUS assignment)
uv run lake continuous-queries --no-dry-run
```

Options:
- `--dry-run` / `--no-dry-run`: print SQL without executing
  (default: `--dry-run`)

### `list-related-entries`

Given a glossary term (e.g. `advertiser`), searches every Dataplex catalog
entry's schema and returns those that contain a matching column, with
Resource Name, Column Name, Project, and Fully Qualified Name. The match is
exact (case-insensitive) on the column name.

This is the lightweight "what is this term used in?" lookup. For bulk
discovery and curation, use `scan-for-related-entries` instead.

```bash
# Search for all entries with a column matching 'advertiser'
uv run lake list-related-entries --term advertiser

# Specify a glossary (default: first glossary found)
uv run lake list-related-entries --term brand \
  --glossary marketing-business-glossary
```

Options:
- `--term` (required): glossary term to search for (e.g. `advertiser`)
- `--glossary`: glossary ID or display name (default: first glossary found)

### `scan-for-related-entries`

Compares a BigLake catalog against a glossary to find matching and unmatched
terms using exact, synonym, and fuzzy semantic matching.

This command scans all table columns in the specified BigLake catalog and
matches them against glossary terms. It produces a two-phase report:

- **Phase A — Exact & Synonym Matches**: terms that have a direct column
  name match or match via a synonym relationship defined in the glossary.
- **Phase B — Fuzzy Semantic Proposals**: for terms with no exact match,
  a keyword-based scoring system proposes candidate columns based on the
  term's description. Columns are scored by exact keyword match (+10),
  substring match (+5), and table-name match (+3).

When `--output` is provided, Phase B proposals are written to a YAML file
that can be curated (rows removed or commented out) and then applied with
`apply-related-entries`.

```bash
# Scan catalog against default glossary
uv run lake scan-for-related-entries \
  --catalog wpp-dataproducts-lakehouse-warehouse

# Scan with namespace filter
uv run lake scan-for-related-entries \
  --catalog wpp-dataproducts-lakehouse-warehouse \
  --namespace marketing

# Specify glossary explicitly
uv run lake scan-for-related-entries \
  --catalog wpp-dataproducts-lakehouse-warehouse \
  --glossary marketing-business-glossary

# Export proposals to YAML for curation
uv run lake scan-for-related-entries \
  --catalog wpp-dataproducts-lakehouse-warehouse \
  --namespace marketing \
  --output proposals.yaml \
  --fuzzy-score-threshold 10
```

Options:
- `--catalog` (required): BigLake catalog name to scan
- `--namespace`: optional namespace filter within the catalog
- `--glossary`: glossary ID or display name (default: first glossary found)
- `--output` / `-o`: write Phase B proposals to a YAML file for curation
  and later apply
- `--fuzzy-score-threshold`: filter out fuzzy proposals with a score below
  this threshold (default: 0, i.e. include everything)
- `--project`: override the Google Cloud project written into the exported
  YAML (default: derived from the discovered glossary's resource path)
- `--location`: override the location written into the exported YAML
  (default: derived from the discovered glossary's resource path)

The project and location used when `--output` is given are resolved in this
order:

1. Explicit `--project` / `--location` flag
2. Project and location parsed out of the discovered glossary's `name`
   (e.g. `projects/{p}/locations/{l}/glossaries/{id}`)
3. The values from `Config`

This avoids writing a silent fallback (e.g. a placeholder project string)
into the YAML, so the subsequent `apply-related-entries` step targets the
correct Dataplex project.

#### Workflow for `scan-for-related-entries`

Below is a step-by-step description of what happens when you run the command:

1. **Glossary discovery** — The CLI resolves the glossary (either the one
   specified via `--glossary` or the first glossary in the project/location).
   It lists all terms and their categories.
2. **BigLake entry listing** — All entries in the `@biglake` entry group
   are listed. Only table-type entries are kept; optionally filtered to a
   single namespace via `--namespace`.
3. **Schema extraction** — For each table entry, the CLI fetches the full
   entry description (including schema aspects) and extracts all column names.
4. **Phase A — Exact & synonym matching** — Each glossary term is compared
   against the extracted column names:
   - A direct match occurs when the normalized term name equals a normalized
     column name.
   - Synonym matching checks whether a term's description starts with
     "Synonym for \<canonical-term\>" and inherits the canonical term's
     match if one exists.
5. **Phase B — Fuzzy semantic matching** — Terms not matched in Phase A are
   processed by tokenizing their description into keywords (filtering stop
   words). Each column/table is scored against those keywords. Proposals are
   sorted by score (highest first) so the most likely matches appear at
   the top.
6. **Report output** — A summary is printed showing glossary and catalog
   statistics, the Phase A matches table, and the Phase B proposals table
   with scores and match rationale.

### `apply-related-entries`

Applies curated related-entry proposals from a YAML file to Dataplex Catalog.

This command reads a proposals file (produced by
`scan-for-related-entries --output`), validates each proposal, and creates
**Dataplex entry-links** of type `entryLinkTypes/definition` via the
`gcloud alpha dataplex entry-links create` subcommand. Each link is a
`term ↔ asset` relation between a glossary-term entry and a BigLake table
entry. The command is idempotent: existing relations (gcloud's
`ALREADY_EXISTS` error) are skipped with an informational message rather
than duplicated.

The link is created in the **`@biglake`** entry-group (the SOURCE entry's
group, which the API requires for a `definition` link) with the BigLake
entry listed first as `SOURCE` and the term entry second as `TARGET`.

#### Workflow

1. **Scan** — `scan-for-related-entries --output proposals.yaml` exports
   proposals.
2. **Curate** — A data steward edits `proposals.yaml`, removing incorrect
   rows.
3. **Preview** — `apply-related-entries --input proposals.yaml --dry-run`
   validates and previews.
4. **Apply** — `apply-related-entries --input proposals.yaml` creates the
   entry-links.

```bash
# Preview changes
uv run lake apply-related-entries \
  --input proposals.yaml --dry-run

# Execute
uv run lake apply-related-entries \
  --input proposals.yaml

# Override glossary
uv run lake apply-related-entries \
  --input proposals.yaml --glossary my-glossary

# Override project and location
uv run lake apply-related-entries \
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

1. Pre-flights a `gcloud dataplex entries describe` against the BigLake
   entry to surface actionable errors for typos in catalog/table/namespace.
2. Resolves the GCP project **number** for the catalog project (via
   `gcloud projects describe`) — the Dataplex API requires the project
   number in entry-name references and rejects the project ID with
   "Entry ID must contain project number."
3. Builds the BigLake entry resource path (SOURCE) using the project
   number on the outer Dataplex path and the project ID on the inner
   BigLake segment:
   `projects/{project_number}/locations/{location}/entryGroups/@biglake/entries/biglake.googleapis.com/projects/{project_id}/catalogs/{catalog}/namespaces/{ns}/tables/{table}`
4. Builds the term-entry resource path (TARGET) using the project number
   on both outer and inner segments:
   `projects/{project_number}/locations/{location}/entryGroups/@dataplex/entries/projects/{project_number}/locations/{location}/glossaries/{glossary_id}/terms/{term_slug}`
   The inner project segment is read from the first term's `parent`
   resource path (so the link targets the right Dataplex project even
   when terms live in a different project from the catalog).
5. Computes a deterministic entry-link id:
   `definition-{term_slug}-{ns}-{table_slug}` truncated to 63 chars
   (the Dataplex resource-id limit). Both the term name and the table
   name are slugified (lowercase, spaces/underscores → hyphens) so the
   id only contains `[a-z0-9-]`.
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
7. Maps the gcloud exit code to an `ApplyResult`: `created` on exit 0,
   `skipped` on `ALREADY_EXISTS`, `error` on any other failure. The raw
   gcloud stderr is surfaced in the `detail` column.

When a row fails (e.g. the target entry does not exist on the project), the
summary includes the underlying error in the `detail` column — the raw
gcloud error from the pre-flight describe, or the raw gcloud stderr from
`entry-links create` (e.g. `Permission denied: dataplex.googleapis.com`) —
instead of a generic "Entry not found" message. This makes it easy to spot
IAM or project-mismatch issues.

### `reset`

Tears down generated metadata resources for a clean re-run. **Destructive
and requires `--confirm`** — without the flag the command prints a warning
and exits without making any changes.

```bash
# Required confirmation flag
uv run lake reset --confirm
```

What it deletes (in order):

1. **Lakehouse namespace** — the namespace is deleted; the Iceberg catalog
   itself must be deleted manually via
   `gcloud biglake iceberg catalogs delete <name> --project=<project>`
   (this is printed to stdout after the namespace step).
2. **Glossary resources** — the configured glossary, its categories, and
   its terms.
3. **Dataplex catalog entries** — for each table in `Config.TABLES`, the
   entry under `config.entry_group_path` is deleted.

What it does **not** delete:

- The Iceberg catalog itself (manual step — see above)
- GCS data in the warehouse bucket
- BigQuery datasets and tables
- Dataplex scans, profile results, or quality results

Per-step errors are caught and printed as warnings, so the command
continues even if one step fails partway through.

## Source files

- CLI entrypoint: `lake_cli/cli.py`
- Config model: `lake_cli/config.py`
- Lakehouse REST catalog: `lake_cli/lakehouse_catalog.py`
- Dataplex topology & assets: `lake_cli/dataplex_lake.py`
- Dataplex catalog entries: `lake_cli/catalog.py`
- Tag writer: `lake_cli/tag_writer.py`
- Glossary writer: `lake_cli/glossary_writer.py`
- Glossary manager: `lake_cli/glossary_manager.py`
- Metadata parsing: `lake_cli/table_metadata.py`
- Metadata enrichment (hybrid + Google insights):
  `lake_cli/table_and_column_insights.py`
- Dataset insights manager: `lake_cli/dataset_insights.py`
- Data profiling manager: `lake_cli/data_profiling.py`
- Data quality manager: `lake_cli/data_quality.py`
- Vector search manager: `lake_cli/vector_search.py`
- BQML Gemini manager: `lake_cli/bqml_gemini.py`
- Continuous queries manager: `lake_cli/continuous_queries.py`
- Related entries manager: `lake_cli/related_entries.py` (proposals
  export/import, the gcloud-based entry-link creation helper, and the
  apply logic that targets `entryLinkTypes/definition`)
