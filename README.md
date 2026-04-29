# Lakehouse Content — Marketing Data Platform

This project has been create to deliver a synthetic, end-to-end Marketing Data Platform demonstration built to try and demonstrate the various features of  **Google Cloud Dataplex**, **BigQuery** and **BigLake** with **Apache Iceberg**.
It relies on the terraform for an Analytics Lakhouse provided by google available here: https://github.com/GoogleCloudPlatform/terraform-google-analytics-lakehouse

The project contains a CLI to generate synthetic data which has been configured to produce a set of synthetic marketing tables.
For more details on changing and extending the data generated see [Data Generation Guide](docs/data_generation.md)

The CLI does also expose all tooling to set up and control dataplex metadata catalog, glossary and other services such data profiling, data quality services as well 
vector search.
For more details on this see [CLI Functionality](docs/cli_functionality.md)


## 🚀 Quick Start

```bash
# Set your GCP project
gcloud config set project your-project-id

# Install dependencies
uv sync

# Run full generation and ingestion
uv run python -m ingestion.cli ingest
```

## 🔧 Lakehouse REST Catalog Setup

The CLI supports setting up a BigLake Iceberg REST Catalog for cross-engine table discovery (BigQuery, Spark, Trino).

### Prerequisites

```bash
# Enable required APIs
gcloud services enable biglake.googleapis.com
```

### Create the Catalog (Vended Credentials Mode)

For enterprise deployments using credential vending, the catalog must be created via the **GCP Console**.
gcloud does not properly support the `X-Iceberg-Access-Delegation: vended-credentials` header required for table registration.

Navigate to: **BigLake > Iceberg catalogs > Create catalog**

For more details, see: https://docs.cloud.google.com/lakehouse/docs/lakehouse-iceberg-rest-catalog#process

### Run Setup via CLI

```bash
# Verify catalog, create namespace, and register tables
uv run python -m ingestion.cli setup-catalog \
  --catalog-name YOUR-CATALOG-NAME \
  --full
```

### Table Registration with Vended Credentials

The CLI automatically registers tables via **Dataproc Serverless (Managed Service for Apache Spark)**, which properly handles the `X-Iceberg-Access-Delegation: vended-credentials` header. No manual steps required.

### Alternative: End-User Credentials Mode

If you don't need credential vending, use end-user mode (gcloud CLI works fully):

```bash
gcloud biglake iceberg catalogs create YOUR-CATALOG-NAME \
  --project=YOUR-PROJECT-ID \
  --catalog-type=gcs-bucket \
  --credential-mode=end-user
```

With end-user mode, `setup-catalog --full` will fully work including table registration.

## 📦 Project Structure

- `docs/` - Documentation files
- `ingestion/` - CLI and ingestion logic
- `generators/` - Data generation modules
- `metadata/` - Table metadata and business glossary configurations

## 🔗 Links

- [Google Cloud Dataplex Documentation](https://cloud.google.com/dataplex)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)
- [BigQuery BigLake Documentation](https://cloud.google.com/bigquery/docs/biglake-overview)