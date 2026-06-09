# BigLake Iceberg REST Catalog — Operational Notes

This document is a **troubleshooting and operational context file** for the
BigLake Iceberg REST Catalog integration. It is intentionally separate from
`lake-cli-details.md`, which documents the CLI surface (the *how* — flags,
examples, side effects). This document covers the *why* and the *what-can-go-wrong*:

- **Operational constraints** specific to BigLake Iceberg REST Catalogs (for
  example, vended credentials and the `X-Iceberg-Access-Delegation` header
  that gcloud does not send).
- **The narrow scope** of what this CLI automates versus what the user must
  do by hand.
- **A pre-built troubleshooting checklist** for the most common catalog-related
  failures.

If you are new to the CLI, read `lake-cli-details.md` first for command
reference; come back here when something fails or when you need to understand
the limits of what the tool can do.

## Current stance in this project

For environments using **vended credentials**, this project treats catalog creation as a manual prerequisite and only automates:
- catalog existence checks
- namespace creation/deletion

The reason catalog creation is manual: in vended-credentials mode, the
Iceberg REST endpoint requires the `X-Iceberg-Access-Delegation` HTTP
header, which `gcloud biglake iceberg catalogs create` does not set. The
practical workaround is to create the catalog in the GCP Console
(Console sends the header), then run `setup-catalog` from this CLI to
verify it exists and create the namespace.

These operations are implemented in `lake_cli/lakehouse_catalog.py` and wired through:
- `setup-catalog`
- `catalog`
- `reset` (namespace delete only)

Note: the manager also exposes a `delete_catalog` method, but `reset` does
not currently call it. `reset` therefore prints a manual
`gcloud biglake iceberg catalogs delete ...` command for the user to run
themselves. This is deliberate (it forces a human to confirm a destructive
catalog-level action) but worth knowing if you are looking for a one-shot
teardown.

## Supported workflow

### 1) Create catalog outside this CLI

Create the Iceberg catalog in the Google Cloud Console first, then run this CLI.

Reference:
- https://docs.cloud.google.com/lakehouse/docs/lakehouse-iceberg-rest-catalog

### 2) Verify and create namespace

```bash
uv run lake setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full
```

### 3) Continue with Dataplex registration

```bash
uv run lake catalog \
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
4. Manager raises `gcloud CLI not available` or `Failed to delete catalog: ...`:
   - The manager shells out to `gcloud` for all catalog/namespace operations.
     Confirm the Google Cloud SDK is installed and on `PATH`
     (`gcloud --version` should succeed), and that you are authenticated
     (`gcloud auth list` should show an active account).
5. Manager raises `... timed out`:
   - The gcloud subprocess has a 30-second timeout. Transient network issues
     or large responses can hit it. Re-run; if it persists, run the same
     `gcloud biglake iceberg catalogs describe <name> --project <p>`
     command manually to see the underlying error.

## Relevant code
- `lake_cli/lakehouse_catalog.py` — `LakehouseCatalogManager` (the only
  file that talks to `gcloud biglake iceberg ...`)
- `lake_cli/cli.py` — `setup_catalog`, `catalog`, and `reset` are the
  three command entry points that use the manager