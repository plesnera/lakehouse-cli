import typer
from ingestion.config import Config, TABLES
from ingestion.dataplex_lake import DataplexManager
from ingestion.catalog import CatalogManager
from ingestion.tag_writer import TagWriter
from ingestion.glossary_writer import GlossaryWriter
from ingestion.table_and_column_insights import HybridMetadataEnricher
from ingestion.glossary_manager import BusinessGlossaryManager
from ingestion.lakehouse_catalog import LakehouseCatalogManager
from ingestion.data_profiling import DataProfilingManager
from ingestion.data_quality import DataQualityManager
from ingestion.dataset_insights import DatasetInsightsManager
from ingestion.vector_search import VectorSearchManager
from ingestion.bqml_gemini import BQMLGeminiManager
from ingestion.continuous_queries import ContinuousQueryManager

app = typer.Typer()

def _run_catalog(config: Config):
    """Internal helper to run the full cataloging process."""
    # 0. Validate catalog name is set
    if not config.lakehouse_catalog_name:
        print("❌ Error: lakehouse_catalog_name is not set.")
        print("   Pass --catalog-name <name> or set it in your config.")
        print("   Create the catalog first via GCP Console if it doesn't exist.")
        return

    # 1. Lakehouse REST Catalog (Iceberg) - replaces BigLakeRegistrar
    lakehouse = LakehouseCatalogManager(config)
    result = lakehouse.ensure_catalog()
    if not result.get("catalog_exists", False):
        print(f"❌ Catalog does not exist: {config.lakehouse_catalog_name}")
        print("   Create it manually in GCP Console first, then re-run.")
        return

    lakehouse.ensure_namespace()

    # 2. Dataplex Lake Topology
    dp = DataplexManager(config)
    dp.ensure_topology()
    dp.register_assets()

    # 3. Catalog Entries
    cat = CatalogManager(config)
    cat.ensure_entry_group()
    cat.ensure_entry_type()
    cat.register_entries()

    # 4. Tags
    tag = TagWriter(config)
    tag.ensure_tag_template()
    tag.apply_tags()

    # 5. Glossary
    gloss = GlossaryWriter(config)
    gloss.create_glossary()
    gloss.create_terms()
    gloss.apply()

    # 6. Metadata Enrichment (Optional - can be time-consuming)
    print("Note: Run 'uv run python -m ingestion.cli enrich-metadata' to add table/column descriptions")


@app.command()
def catalog(
    data_project: str = typer.Option(None, "--data-project", help="GCP project where data is stored (GCS, Iceberg)"),
    catalog_project: str = typer.Option(None, "--catalog-project", help="GCP project where Dataplex catalog resides"),
    iceberg_warehouse: str = typer.Option(None, "--iceberg-warehouse", help="GCS path for Iceberg data"),
    biglake_connection: str = typer.Option(None, "--biglake-connection", help="BigLake connection template"),
    catalog_name: str = typer.Option(None, "--catalog-name", help="Lakehouse REST catalog name (required)"),
):
    """Register Iceberg tables in BigQuery and Dataplex catalog.

    Supports cross-project scenarios where data and catalog reside in different projects.
    """
    config = Config()

    # Apply cross-project configuration if provided
    if data_project:
        config.data_project_id = data_project
    if catalog_project:
        config.catalog_project_id = catalog_project
    if iceberg_warehouse:
        config.iceberg_warehouse = iceberg_warehouse
    if biglake_connection:
        config.biglake_connection = biglake_connection
    if catalog_name:
        config.lakehouse_catalog_name = catalog_name

    _run_catalog(config)


@app.command()
def setup_catalog(
    catalog_name: str = typer.Option(..., "--catalog-name", help="Name for the Lakehouse catalog (REQUIRED - no default)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview actions without executing"),
    full: bool = typer.Option(False, "--full", help="Verify catalog, create namespace, and register all tables"),
):
    """
    Set up the Lakehouse REST Catalog for Iceberg metadata.

    The catalog must be created MANUALLY before running this command.
    For vended-credentials mode, use the GCP Console (gcloud does not support
    the required X-Iceberg-Access-Delegation header):
      https://docs.cloud.google.com/lakehouse/docs/lakehouse-iceberg-rest-catalog#process

    This command then:
    1. Verifies the catalog exists
    2. Creates the namespace (if missing)

    Table registration is handled by Dataplex catalog entries
    (via ``catalog`` command).

    Examples:
        # Preview what would be done
        uv run python -m ingestion.cli setup-catalog --catalog-name marketing-lakehouse --full --dry-run

        # Verify catalog and create namespace
        uv run python -m ingestion.cli setup-catalog --catalog-name marketing-lakehouse --full

        # Verify catalog only (no namespace)
        uv run python -m ingestion.cli setup-catalog --catalog-name marketing-lakehouse
    """
    config = Config()

    # Apply catalog name if provided
    if catalog_name:
        config.lakehouse_catalog_name = catalog_name

    lakehouse = LakehouseCatalogManager(config)

    # First verify catalog exists (user must create manually)
    result = lakehouse.ensure_catalog(dry_run=dry_run)
    if not result.get("catalog_exists", False):
        print("❌ Catalog does not exist. Create it manually first.")
        return

    if full:
        # Create namespace
        lakehouse.ensure_namespace(dry_run=dry_run)


@app.command()
def enrich_metadata(
    table_names: str = typer.Option(None, help="Comma-separated list of table names in format project_id.dataset_id.table_id (e.g., 'wpp-dataproducts-lakehouse.marketing.audience')"),
    metadata_files: str = typer.Option(None, help="Comma-separated list of metadata files to use (e.g., 'audience.yaml,campaigns.yaml'). Must match table_names in order"),
    google_insights: bool = typer.Option(False, help="Use Google-style automated insights instead of manual markdown files"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview metadata changes without applying them to BigQuery")
):
    """
    Generate and apply table/column descriptions using hybrid or Google-only approach.

    This command offers two modes:
    1. Manual : Use manual YAML metadata files instead of Google Insights
    2. Google Insights Only: Use pure Google Dataplex-style automated metadata generation

    Examples:
        # Mode 1: Manual approach
        # Enrich all tables (uses default YAML files if they exist)
        uv run python -m ingestion.cli enrich-metadata

        # You can use the automated google insights as a starting point by running and then copy-paste in to YAML
        # Enrich specific tables with manual files
        uv run python -m ingestion.cli enrich-metadata \\
          --table-names wpp-dataproducts-lakehouse.marketing.audience,wpp-dataproducts-lakehouse.marketing.campaigns \\
          --metadata-files audience.yaml,campaigns.yaml

        # Mode 2: Google insights only (no manual files needed)
        # Enrich specific tables with pure Google insights
        uv run python -m ingestion.cli enrich-metadata \\
          --table-names wpp-dataproducts-lakehouse.marketing.campaigns \\
          --google-insights

        # Enrich all tables with pure Google insights
        uv run python -m ingestion.cli enrich-metadata --google-insights

        # Preview changes without applying (dry-run mode)
        uv run python -m ingestion.cli enrich-metadata --dry-run
        uv run python -m ingestion.cli enrich-metadata --table-names campaigns --google-insights --dry-run

        # Create YAML metadata templates for manual descriptions
        uv run python -m ingestion.cli create-templates
    """
    config = Config()
    enricher = HybridMetadataEnricher(config)

    if table_names:
        # Convert comma-separated strings to lists
        tables_to_enrich = [t.strip() for t in table_names.split(',')]

        # Check if using Google insights (no metadata files needed)
        if google_insights:
            print(f"Enriching metadata for specific tables using Google insights:")
            for table in tables_to_enrich:
                print(f"  {table} (Google insights)")

            # Use Google insights only (no manual files)
            enricher.generate_descriptions_for_tables_with_google_insights(tables_to_enrich, timeout=300, dry_run=dry_run)
        else:
            # Validate that metadata files are provided when table names are specified
            if not metadata_files:
                print("❌ Error: When specifying table names without --google-insights, you must provide metadata files using --metadata-files")
                print("Example: --table-names audience,campaigns --metadata-files audience.yaml,campaigns.yaml")
                print("Or use: --table-names audience --google-insights")
                return

            metadata_files_list = [m.strip() for m in metadata_files.split(',')]

            # Validate that the number of tables matches the number of metadata files
            if len(tables_to_enrich) != len(metadata_files_list):
                print(f"❌ Error: Number of table names ({len(tables_to_enrich)}) does not match number of metadata files ({len(metadata_files_list)})")
                return

            print(f"Enriching metadata for specific tables with manual files:")
            for table, metadata_file in zip(tables_to_enrich, metadata_files_list):
                print(f"  {table} <- {metadata_file}")

            # Use the explicit metadata files
            enricher.generate_descriptions_for_tables_with_files(tables_to_enrich, metadata_files_list, timeout=300, dry_run=dry_run, use_google_insights=False)
    else:
        if google_insights:
            print("Enriching metadata for all tables using Google insights...")
            enricher.generate_descriptions_with_google_insights(timeout=300, dry_run=dry_run)
        else:
            print("Enriching metadata for all tables in dataset (using default markdown files)...")
            enricher.generate_descriptions(timeout=300, dry_run=dry_run)

@app.command()
def create_templates():
    """
    Create template files for metadata and glossary management.

    This command creates template files for both metadata descriptions and
    business glossary definitions that you can edit before running enrichment.

    Example:
        uv run python -m ingestion.cli create-templates
    """
    config = Config()
    enricher = HybridMetadataEnricher(config)
    glossary_manager = BusinessGlossaryManager(config)

    # Create metadata templates
    enricher.create_all_templates()

    # Create glossary templates
    glossary_manager.generate_template_files()

@app.command()
def manage_glossary(
    action: str = typer.Option("create", help="Action to perform: create, validate, apply, or reset"),
    input: str = typer.Option(None, "--input", help="Path to glossary YAML file (default: metadata/glossary.yaml)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse and print the plan without creating any Dataplex resources"),
    reset: bool = typer.Option(False, "--reset", help="Delete all glossary resources before creating (use with action=create)"),
):
    """
    Manage Dataplex business glossaries from YAML files.

    This command creates and manages semantic synonym glossaries in Dataplex
    using the dedicated Glossary API (glossaries, categories, terms, and
    synonym/related entryLinks).

    Examples:
        # Preview what would be created
        uv run python -m ingestion.cli manage-glossary --dry-run

        # Create glossary from default template
        uv run python -m ingestion.cli manage-glossary --action create

        # Create from a custom file
        uv run python -m ingestion.cli manage-glossary --action create --input my_glossary.yaml

        # Reset and recreate
        uv run python -m ingestion.cli manage-glossary --action create --reset

        # Validate existing glossary
        uv run python -m ingestion.cli manage-glossary --action validate

        # Link terms to BigQuery assets
        uv run python -m ingestion.cli manage-glossary --action apply
    """
    config = Config()
    glossary_manager = BusinessGlossaryManager(config)

    if reset:
        glossary_manager.reset_glossary(input_path=input)

    if action == "create":
        glossary_manager.create_glossary_from_markdown(input_path=input, dry_run=dry_run)
    elif action == "validate":
        glossary_manager.validate_glossary(input_path=input)
    elif action == "apply":
        glossary_manager.apply_glossary_to_assets(input_path=input)
    elif action == "reset":
        if not reset:
            glossary_manager.reset_glossary(input_path=input)
    else:
        print(f"❌ Unknown action: {action}. Use create, validate, apply, or reset.")


@app.command()
def dataset_insights(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview scan creation without executing"),
    results: bool = typer.Option(False, "--results", help="Show latest insights results"),
    run: bool = typer.Option(False, "--run", help="Run the dataset insights scan"),
    timeout: int = typer.Option(600, "--timeout", help="Seconds to wait for results"),
):
    """Create and run Dataplex dataset-level insights scans for AI-generated metadata.

    Dataset-level insights analyze an entire BigQuery dataset to produce:
    - AI-generated dataset description
    - Relationship graph (how tables connect)
    - Cross-table SQL sample queries
    - Discovered primary/foreign key relationships

    Examples:
        # Create and run scan (default behavior)
        uv run python -m ingestion.cli dataset-insights

        # Preview scan without executing
        uv run python -m ingestion.cli dataset-insights --dry-run

        # Get latest results
        uv run python -m ingestion.cli dataset-insights --results

        # Explicitly run scan
        uv run python -m ingestion.cli dataset-insights --run
    """
    config = Config()
    mgr = DatasetInsightsManager(config)

    if results:
        mgr.get_results(timeout=timeout)
    else:
        scan_id = mgr.create_scan(dry_run=dry_run)
        if scan_id and not dry_run:
            mgr.run_scan()


@app.command()
def profile(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan without creating scans"),
    results: bool = typer.Option(False, "--results", help="Show latest profiling results instead of creating scans"),
):
    """Create and run Dataplex data profile scans for all tables."""
    config = Config()
    mgr = DataProfilingManager(config)
    if results:
        mgr.get_results()
    else:
        mgr.create_and_run_scans(dry_run=dry_run)


@app.command()
def quality(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan without creating scans"),
    results: bool = typer.Option(False, "--results", help="Show latest quality results instead of creating scans"),
    check_rules: bool = typer.Option(False, "--check-rules", help="Compare markdown rules with active Dataplex rules"),
    sync_only: bool = typer.Option(False, "--sync-only", help="Sync rules without running scans"),
    run: bool = typer.Option(False, "--run", help="Run scans (implied if no other action flags)"),
    table_names: str = typer.Option(None, help="Comma-separated list of table names to process"),
):
    """Manage Dataplex data quality scans with marketing-specific rules.

    This command provides full lifecycle management for data quality scans:
    - Create/update scans with rules from markdown files
    - Compare markdown rules with active Dataplex rules
    - Sync rules without running scans
    - Run quality scans

    Examples:
        # Check if markdown rules match active Dataplex rules (no changes made)
        uv run python -m ingestion.cli quality --check-rules

        # Sync rules without running scans
        uv run python -m ingestion.cli quality --sync-only

        # Sync rules and run scans (default behavior)
        uv run python -m ingestion.cli quality

        # Preview what would be synced
        uv run python -m ingestion.cli quality --sync-only --dry-run

        # Run specific tables only
        uv run python -m ingestion.cli quality --table-names campaigns,transactions

        # View results of previous runs
        uv run python -m ingestion.cli quality --results
    """
    config = Config()
    mgr = DataQualityManager(config)

    # Parse table names if provided
    tables = None
    if table_names:
        tables = [t.strip() for t in table_names.split(',')]

    # Default to run behavior if no action flags specified
    if not any([results, check_rules, sync_only, run]):
        run = True

    if results:
        mgr.get_results(tables)
    elif check_rules:
        mgr.check_rules(tables)
    elif sync_only:
        mgr.sync_only(tables, dry_run=dry_run)
    elif run:
        mgr.create_and_run_scans(tables, dry_run=dry_run)


@app.command()
def vector_search(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print SQL without executing"),
):
    """Set up BigQuery Vector Search: embedding model, embeddings, vector index, and example query."""
    config = Config()
    mgr = VectorSearchManager(config)
    mgr.setup(dry_run=dry_run)


@app.command()
def bqml_setup(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print SQL without executing"),
):
    """Set up BigQuery ML Gemini remote model and run example text generation queries."""
    config = Config()
    mgr = BQMLGeminiManager(config)
    mgr.setup(dry_run=dry_run)


@app.command()
def continuous_queries(
    dry_run: bool = typer.Option(True, help="Print SQL without executing (default: True, requires Enterprise reservation)"),
):
    """Set up BigQuery continuous query for real-time CTR aggregation on pixel_events."""
    config = Config()
    mgr = ContinuousQueryManager(config)
    mgr.setup(dry_run=dry_run)


@app.command()
def reset(
    confirm: bool = typer.Option(False, "--confirm", help="Required to actually delete resources"),
):
    """Tear down all generated resources for a clean re-run.

    Deletes: Lakehouse REST catalog, Dataplex entries/tags, and glossary resources.
    Does NOT delete GCS data.
    """
    if not confirm:
        print("⚠️  This will delete all marketing lakehouse resources.")
        print("   Pass --confirm to proceed.")
        return

    config = Config()

    # 1. Delete Lakehouse namespace (catalog itself must be deleted manually)
    print("Deleting Lakehouse namespace...")
    lakehouse = LakehouseCatalogManager(config)
    try:
        lakehouse.delete_namespace()
    except Exception as e:
        print(f"  ⚠️  Lakehouse namespace reset: {e}")

    # Note: The catalog itself must be deleted manually via:
    #   gcloud biglake iceberg catalogs delete <name> --project=<project>
    print("  (Catalog not deleted - remove manually if needed)")

    # 2. Reset glossary
    print("Resetting glossary...")
    glossary_mgr = BusinessGlossaryManager(config)
    try:
        glossary_mgr.reset_glossary()
    except Exception as e:
        print(f"  ⚠️  Glossary reset: {e}")

    # 3. Delete catalog entries
    print("Deleting catalog entries...")
    from google.cloud import dataplex_v1
    catalog_client = dataplex_v1.CatalogServiceClient()
    for name in TABLES:
        try:
            catalog_client.delete_entry(name=f"{config.entry_group_path}/entries/{name}")
            print(f"  Deleted entry: {name}")
        except Exception:
            pass

    print("✅ Reset complete.")


if __name__ == "__main__":
    app()
