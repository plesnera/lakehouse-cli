import typer
from generators.config import GeneratorConfig, TABLES
from generators.orchestrator import Orchestrator
from ingestion.iceberg_writer import IcebergWriter
from ingestion.bq_external import BigLakeRegistrar
from ingestion.dataplex_lake import DataplexManager
from ingestion.catalog import CatalogManager
from ingestion.tag_writer import TagWriter
from ingestion.glossary_writer import GlossaryWriter
from ingestion.bq_metadata_hybrid import HybridMetadataEnricher
from ingestion.glossary_manager import BusinessGlossaryManager
from ingestion.data_profiling import DataProfilingManager
from ingestion.data_quality import DataQualityManager
from ingestion.vector_search import VectorSearchManager
from ingestion.bqml_gemini import BQMLGeminiManager
from ingestion.continuous_queries import ContinuousQueryManager
import os

app = typer.Typer()

@app.command()
def generate(
    local: bool = True,
    full_scale: bool = typer.Option(False, "--full-scale", help="Use production-scale row counts from Agent.md (8K audience, 80K cookies, 2M events, etc.)"),
    data_project: str = typer.Option(None, "--data-project", help="GCP project where data is stored (GCS, Iceberg)"),
    iceberg_warehouse: str = typer.Option(None, "--iceberg-warehouse", help="GCS path for Iceberg data"),
):
    from generators.config import FULL_SCALE
    config = GeneratorConfig(**FULL_SCALE) if full_scale else GeneratorConfig()
    
    # Apply cross-project configuration if provided
    if data_project:
        config.data_project_id = data_project
    if iceberg_warehouse:
        config.iceberg_warehouse = iceberg_warehouse
    
    orchestrator = Orchestrator(config)
    
    if local:
        os.makedirs("local_output", exist_ok=True)
        # For local, we still aggregate for simple parquet write, or we could write multiple files
        # Let's aggregate for local demo
        tables = orchestrator.generate_all()
        for name, table in tables.items():
            path = f"local_output/{name}.parquet"
            pq.write_table(table, path)
            print(f"Saved {name} to {path}")
    else:
        # Streamed GCP write
        writer = IcebergWriter(config)
        writer.write_stream(orchestrator.generate_all_streamed())

def _run_catalog(config: GeneratorConfig):
    """Internal helper to run the full cataloging process."""
    # 1. BQ Registration (Ensures dataset exists)
    bq = BigLakeRegistrar(config)
    bq.register_tables()

    # 2. Dataplex Lake Topology
    dp = DataplexManager(config)
    dp.ensure_topology()
    dp.register_assets()

    # 3. Catalog Entries
    cat = CatalogManager(config)
    cat.ensure_entry_group()
    cat.register_entries()

    # 4. Tags
    tag = TagWriter(config)
    tag.ensure_tag_template()
    tag.apply_tags()

    # 5. Glossary
    gloss = GlossaryWriter(config)
    gloss.create_glossary()
    gloss.create_terms()

    # 6. Metadata Enrichment (Optional - can be time-consuming)
    print("Note: Run 'uv run python -m ingestion.cli enrich-metadata' to add table/column descriptions")


@app.command()
def catalog(
    data_project: str = typer.Option(None, "--data-project", help="GCP project where data is stored (GCS, Iceberg)"),
    catalog_project: str = typer.Option(None, "--catalog-project", help="GCP project where Dataplex catalog resides"),
    iceberg_warehouse: str = typer.Option(None, "--iceberg-warehouse", help="GCS path for Iceberg data"),
    biglake_connection: str = typer.Option(None, "--biglake-connection", help="BigLake connection template")
):
    """Register Iceberg tables in BigQuery and Dataplex catalog.

    Supports cross-project scenarios where data and catalog reside in different projects.
    """
    config = GeneratorConfig()

    # Apply cross-project configuration if provided
    if data_project:
        config.data_project_id = data_project
    if catalog_project:
        config.catalog_project_id = catalog_project
    if iceberg_warehouse:
        config.iceberg_warehouse = iceberg_warehouse
    if biglake_connection:
        config.biglake_connection = biglake_connection

    _run_catalog(config)

@app.command()
def enrich_metadata(
    table_names: str = typer.Option(None, help="Comma-separated list of table names in format project_id.dataset_id.table_id (e.g., 'wpp-dataproducts-lakehouse.marketing.audience')"),
    metadata_files: str = typer.Option(None, help="Comma-separated list of metadata files to use (e.g., 'audience.md,campaigns.md'). Must match table_names in order"),
    google_insights: bool = typer.Option(False, help="Use Google-style automated insights instead of manual markdown files"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview metadata changes without applying them to BigQuery")
):
    """
    Generate and apply table/column descriptions using hybrid or Google-only approach.
    
    This command offers two modes:
    1. Manual : Use manual markdown instead of Google Insights
    2. Google Insights Only: Use pure Google Dataplex-style automated metadata generation
    
    Examples:
        # Mode 1: Manual approach (
        # Enrich all tables (uses default markdown files if they exist)
        uv run python -m ingestion.cli enrich-metadata

        #You can use the automated google insights as a starting point by running and then copy-paste in to markdown
        # Enrich specific tables with manual files
        uv run python -m ingestion.cli enrich-metadata \\
          --table-names wpp-dataproducts-lakehouse.marketing.audience,wpp-dataproducts-lakehouse.marketing.campaigns \\
          --metadata-files audience.md,campaigns.md
        
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
        
        # Create markdown templates for manual descriptions
        uv run python -m ingestion.cli create-templates
    """
    config = GeneratorConfig()
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
                print("Example: --table-names audience,campaigns --metadata-files audience.md,campaigns.md")
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
    config = GeneratorConfig()
    enricher = HybridMetadataEnricher(config)
    glossary_manager = BusinessGlossaryManager(config)
    
    # Create metadata templates
    enricher.create_all_templates()
    
    # Create glossary templates
    glossary_manager.generate_template_files()

@app.command()
def manage_glossary(
    action: str = typer.Option("create", help="Action to perform: create, validate, apply, or reset"),
    input: str = typer.Option(None, "--input", help="Path to glossary markdown file (default: business_glossaries/glossary.md)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse and print the plan without creating any Dataplex resources"),
    reset: bool = typer.Option(False, "--reset", help="Delete all glossary resources before creating (use with action=create)"),
):
    """
    Manage Dataplex business glossaries from markdown files.

    This command creates and manages semantic synonym glossaries in Dataplex
    using the dedicated Glossary API (glossaries, categories, terms, and
    synonym/related entryLinks).

    Examples:
        # Preview what would be created
        uv run python -m ingestion.cli manage-glossary --dry-run

        # Create glossary from default template
        uv run python -m ingestion.cli manage-glossary --action create

        # Create from a custom file
        uv run python -m ingestion.cli manage-glossary --action create --input my_glossary.md

        # Reset and recreate
        uv run python -m ingestion.cli manage-glossary --action create --reset

        # Validate existing glossary
        uv run python -m ingestion.cli manage-glossary --action validate

        # Link terms to BigQuery assets
        uv run python -m ingestion.cli manage-glossary --action apply
    """
    config = GeneratorConfig()
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
def ingest(
    data_project: str = typer.Option(None, "--data-project", help="GCP project where data is stored (GCS, Iceberg)"),
    catalog_project: str = typer.Option(None, "--catalog-project", help="GCP project where Dataplex catalog resides"),
    iceberg_warehouse: str = typer.Option(None, "--iceberg-warehouse", help="GCS path for Iceberg data"),
    biglake_connection: str = typer.Option(None, "--biglake-connection", help="BigLake connection template")
):
    print("Starting full streamed ingestion...")
    config = GeneratorConfig()
    if data_project:
        config.data_project_id = data_project
    if catalog_project:
        config.catalog_project_id = catalog_project
    if iceberg_warehouse:
        config.iceberg_warehouse = iceberg_warehouse
    if biglake_connection:
        config.biglake_connection = biglake_connection

    orchestrator = Orchestrator(config)
    writer = IcebergWriter(config)
    
    # 1. Generate & Write Streamed
    writer.write_stream(orchestrator.generate_all_streamed())
    
    # 2. Register Catalog
    _run_catalog(config)
    print("Ingestion complete.")

@app.command()
def validate(local: bool = True):
    print("Running validation checks...")
    config = GeneratorConfig()
    
    if local:
        import pyarrow.parquet as pq
        for name in TABLES:
            path = f"local_output/{name}.parquet"
            if not os.path.exists(path):
                print(f"FAILED: Local file {path} missing.")
                continue
            
            import pyarrow.parquet as pq
            table = pq.read_table(path)
            print(f"Checking {name} ({len(table)} rows)...")
            
            # Row count check
            expected = {
                "audience": config.n_audience_participants,
                "cookie_registry": config.n_cookies,
                "campaigns": config.n_campaigns,
                "creatives": config.n_campaigns * config.n_creatives_per_campaign,
                "pixel_events": config.n_pixel_events,
                "transactions": config.n_transactions
            }
            if len(table) != expected[name]:
                print(f"  WARNING: Row count mismatch. Expected {expected[name]}, got {len(table)}")

            # ---- Validation checks per table ----
            def _fill_rate(col_data):
                return sum(1 for x in col_data if x is not None) / len(col_data) if col_data else 0

            def _check_rate(label, actual, target, tolerance=0.03):
                print(f"  {label}: {actual:.1%} (target {target:.0%})")
                if abs(actual - target) > tolerance:
                    print(f"  FAILED: {label} {actual:.1%} outside +/- 3pp of {target:.0%}")

            def _check_synonym(col_a_name, col_b_name):
                a = table.column(col_a_name).to_pylist()
                b = table.column(col_b_name).to_pylist()
                if a != b:
                    print(f"  FAILED: {col_a_name} != {col_b_name}")
                else:
                    print(f"  OK: {col_a_name} == {col_b_name}")

            if name == "audience":
                _check_rate("audience.hem fill", _fill_rate(table.column("hem").to_pylist()), config.audience_hem_fill_rate)
                _check_synonym("lat", "location_lat")
                _check_synonym("lon", "location_lon")

            if name == "cookie_registry":
                _check_synonym("cookie_id", "visitor_id")
                _check_synonym("hem", "hashed_email")
                _check_rate("cookie->audience fill", _fill_rate(table.column("audience_id").to_pylist()), config.cookie_audience_fill_rate)
                _check_rate("cookie->hem fill", _fill_rate(table.column("hem").to_pylist()), config.cookie_hem_fill_rate)

            if name == "campaigns":
                _check_synonym("brand", "advertiser")

            if name == "pixel_events":
                _check_rate("pixel->cookie fill", _fill_rate(table.column("cookie_id").to_pylist()), config.pixel_cookie_fill_rate)

            if name == "transactions":
                # Per-market transaction rates
                import pyarrow.compute as pc
                for market, rates in config.market_txn_rates.items():
                    mask = pc.equal(table.column("country_code"), market)
                    market_table = table.filter(mask)
                    if len(market_table) == 0:
                        continue
                    c_rate = _fill_rate(market_table.column("cookie_id").to_pylist())
                    h_rate = _fill_rate(market_table.column("hem").to_pylist())
                    _check_rate(f"txn->cookie ({market})", c_rate, rates.txn_cookie_fill_rate)
                    _check_rate(f"txn->hem ({market})", h_rate, rates.txn_hem_fill_rate)

    print("Validation checks finished.")


@app.command()
def profile(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan without creating scans"),
    results: bool = typer.Option(False, "--results", help="Show latest profiling results instead of creating scans"),
):
    """Create and run Dataplex data profile scans for all tables."""
    config = GeneratorConfig()
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
    config = GeneratorConfig()
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
    config = GeneratorConfig()
    mgr = VectorSearchManager(config)
    mgr.setup(dry_run=dry_run)


@app.command()
def bqml_setup(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print SQL without executing"),
):
    """Set up BigQuery ML Gemini remote model and run example text generation queries."""
    config = GeneratorConfig()
    mgr = BQMLGeminiManager(config)
    mgr.setup(dry_run=dry_run)


@app.command()
def continuous_queries(
    dry_run: bool = typer.Option(True, help="Print SQL without executing (default: True, requires Enterprise reservation)"),
):
    """Set up BigQuery continuous query for real-time CTR aggregation on pixel_events."""
    config = GeneratorConfig()
    mgr = ContinuousQueryManager(config)
    mgr.setup(dry_run=dry_run)


@app.command()
def reset(
    confirm: bool = typer.Option(False, "--confirm", help="Required to actually delete resources"),
):
    """Tear down all generated resources for a clean re-run.

    Deletes: BQ external tables, Dataplex entries/tags, glossary resources,
    and Iceberg catalog entries. Does NOT delete GCS data by default.
    """
    if not confirm:
        print("⚠️  This will delete all marketing lakehouse resources.")
        print("   Pass --confirm to proceed.")
        return

    config = GeneratorConfig()
    from google.cloud import bigquery

    # 1. Delete BQ external tables
    print("Deleting BigQuery external tables...")
    bq_client = bigquery.Client(project=config.project_id)
    dataset_id = f"{config.project_id}.{config.iceberg_namespace}"
    for name in TABLES:
        table_id = f"{dataset_id}.{name}"
        bq_client.delete_table(table_id, not_found_ok=True)
        print(f"  Deleted BQ table: {name}")

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

    # 4. Reset local Iceberg catalog
    if os.path.exists("iceberg_catalog.db"):
        os.remove("iceberg_catalog.db")
        print("  Deleted local Iceberg catalog")

    print("✅ Reset complete.")


if __name__ == "__main__":
    app()
