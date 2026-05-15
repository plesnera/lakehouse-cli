# BigLake Iceberg REST Catalog — Operational Notes

This document captures the current practical behavior assumed by this repository for Lakehouse REST catalog operations.

## Current stance in this project

For environments using **vended credentials**, this project treats catalog creation as a manual prerequisite and only automates:
- catalog existence checks
- namespace creation/deletion

These operations are implemented in `ingestion/lakehouse_catalog.py` and wired through:
- `setup-catalog`
- `catalog`
- `reset` (namespace delete only)

## Supported workflow

### 1) Create catalog outside this CLI

Create the Iceberg catalog in the Google Cloud Console first, then run this CLI.

Reference:
- https://docs.cloud.google.com/lakehouse/docs/lakehouse-iceberg-rest-catalog

### 2) Verify and create namespace

```bash
uv run python -m ingestion.cli setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full
```

### 3) Continue with Dataplex registration

```bash
uv run python -m ingestion.cli catalog \
  --catalog-name YOUR_CATALOG_NAME
```

## Notes on table registration

This repository does not use a `register-table` CLI command.

Instead, the pipeline focuses on Dataplex catalog entries, tags, glossary, and metadata enrichment for the expected marketing table set.

## Troubleshooting checklist

1. `setup-catalog` says catalog not found:
   - Verify the catalog name exactly matches what you created in BigLake.
   - Confirm you are targeting the expected GCP project.
2. Namespace creation fails:
   - Confirm IAM permissions for BigLake namespace operations.
3. `catalog` exits early:
   - Ensure `--catalog-name` is provided (or configured in `Config`).

## Relevant code
- `ingestion/lakehouse_catalog.py`
- `ingestion/cli.py` (`setup_catalog`, `catalog`, `reset`)