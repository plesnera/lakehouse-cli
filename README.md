# Lakehouse CLI

This repository provides a Python CLI for operating metadata and governance workflows for a marketing lakehouse on Google Cloud.

It focuses on Lakehouse REST Catalog verification, Dataplex catalog/glossary management, metadata enrichment, and Dataplex scan operations for profiling and quality.
It comes with a preset configurations and files in the metadata directory for 6 marketing tables as well as a business glossary.
All configuration can be changed in the config.py - will most likely change to a better config in next update.

## Scope

### What this project does
- Verifies a BigLake Iceberg REST catalog and creates the Iceberg namespace
- Registers Dataplex assets, entries, and tags for six marketing tables
- Applies business glossary definitions from `metadata/glossary.yaml`
- Enriches table and column descriptions from YAML and/or Dataplex insights
- Creates/runs dataset insights, profiling scans, and data-quality scans
- Bootstraps vector search, BQML Gemini, and continuous-query setup SQL

### What this project does not do
- It does **not** generate synthetic data in this repository
- It assumes the relevant BigQuery/Iceberg tables already exist

## Prerequisites
- Python 3.13+
- `uv` for dependency management
- Google Cloud SDK (`gcloud`) authenticated to your project
- Required IAM roles for Dataplex, BigQuery, and BigLake operations

Install dependencies:

```bash
uv sync
```

## Quick start

```bash
# 1) Set the active GCP project (used as default by the CLI)
gcloud config set project YOUR_PROJECT_ID

# 2) Verify catalog and create namespace
uv run lake setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full

# 3) Register Dataplex assets/entries/tags/glossary
uv run lake catalog \
  --catalog-name YOUR_CATALOG_NAME
```

## Command overview
- `catalog`: Runs the cataloging pipeline (Dataplex topology, entries, tags, glossary)
- `setup-catalog`: Verifies Lakehouse catalog and optionally creates namespace
- `enrich-metadata`: Applies table/column descriptions
- `create-templates`: Creates metadata/glossary template files
- `manage-glossary`: Create/validate/apply/reset Dataplex glossary resources
- `dataset-insights`: Creates/runs dataset-level Dataplex documentation scans
- `profile`: Creates/runs Dataplex profile scans
- `quality`: Compares/syncs/runs Dataplex data-quality scans from YAML rules
- `vector-search`: Creates vector-search setup artifacts in BigQuery
- `bqml-setup`: Creates BQML Gemini remote model setup artifacts
- `continuous-queries`: Generates/executes continuous query setup (dry-run by default)
- `list-related-entries`: Finds catalog entries whose schema contains a column matching a glossary term
- `scan-for-related-entries`: Compares a BigLake catalog against a glossary to find matching and unmatched terms
- `apply-related-entries`: Applies curated related-entry proposals from a YAML file by creating Dataplex `entryLinks` of type `entryLinkTypes/definition`
- `reset`: Deletes namespace, glossary resources, and Dataplex entries (with `--confirm`)

Detailed usage and examples: `docs/lake-cli-details.md`

## Documentation index
- `docs/lake-cli-details.md`: Full CLI reference and workflows
- `docs/BigQuery-lake-specialties.md`: BigQuery Graph/PGQ modeling reference and Data Engineering Agent setup guide
- `docs/iceberg_rest_implementations.md`: Notes on BigLake Iceberg catalog operational constraints

## References
- https://cloud.google.com/dataplex
- https://cloud.google.com/bigquery/docs/biglake-overview
- https://docs.cloud.google.com/lakehouse/docs/lakehouse-iceberg-rest-catalog
