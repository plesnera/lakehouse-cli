# Lakehouse Content — Marketing Data Platform

A synthetic, end-to-end Marketing Data Platform demonstration built for **Google Cloud Dataplex**, **BigQuery BigLake** with **Apache Iceberg**. 

## 📖 Documentation

For detailed information, see our documentation:

- [Data Generation Guide](docs/data_generation.md) - Learn about synthetic data generation, architecture, and how to extend tables
- [CLI Functionality](docs/cli_functionality.md) - Comprehensive guide to all CLI commands and usage patterns

## 🚀 Quick Start

```bash
# Set your GCP project
gcloud config set project your-project-id

# Install dependencies
uv sync

# Run full ingestion
uv run python -m ingestion.cli ingest
```

## 📦 Project Structure

- `docs/` - Documentation files
- `ingestion/` - CLI and ingestion logic
- `generators/` - Data generation modules
- `metadata_descriptions/` - Table metadata configurations
- `business_glossaries/` - Business glossary definitions

## 🔗 Links

- [Google Cloud Dataplex Documentation](https://cloud.google.com/dataplex)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)
- [BigQuery BigLake Documentation](https://cloud.google.com/bigquery/docs/biglake-overview)