import typer
from generators.config import GeneratorConfig
from generators.orchestrator import Orchestrator
from ingestion.iceberg_writer import IcebergWriter
from ingestion.bq_external import BigLakeRegistrar
from ingestion.dataplex_lake import DataplexManager
from ingestion.catalog import CatalogManager
from ingestion.tag_writer import TagWriter
from ingestion.glossary_writer import GlossaryWriter
from ingestion.bq_metadata_hybrid import HybridMetadataEnricher
from ingestion.glossary_manager import BusinessGlossaryManager
import os
import pyarrow.parquet as pq

app = typer.Typer()

@app.command()
def generate(local: bool = False):
    config = GeneratorConfig()
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

@app.command()
def catalog():
    config = GeneratorConfig()
    
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
def enrich_metadata(
    table_names: str = typer.Option(None, help="Comma-separated list of table names in format project_id.dataset_id.table_id (e.g., 'wpp-dataproducts-lakehouse.marketing.audience')"),
    metadata_files: str = typer.Option(None, help="Comma-separated list of metadata files to use (e.g., 'audience.md,campaigns.md'). Must match table_names in order"),
    google_insights: bool = typer.Option(False, help="Use Google-style automated insights instead of manual markdown files")
):
    """
    Generate and apply table/column descriptions using hybrid or Google-only approach.
    
    This command offers two modes:
    1. Manual + Google Insights (hybrid): Combine manual markdown with Google-style automation
    2. Google Insights Only: Use pure Google Dataplex-style automated metadata generation
    
    Examples:
        # Mode 1: Hybrid approach (manual + Google insights)
        # Enrich all tables (uses default markdown files if they exist)
        uv run python -m ingestion.cli enrich-metadata
        
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
            enricher.generate_descriptions_for_tables_with_google_insights(tables_to_enrich, timeout=300)
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
            enricher.generate_descriptions_for_tables_with_files(tables_to_enrich, metadata_files_list, timeout=300)
    else:
        if google_insights:
            print("Enriching metadata for all tables using Google insights...")
            enricher.generate_descriptions_with_google_insights(timeout=300)
        else:
            print("Enriching metadata for all tables in dataset (using default markdown files)...")
            enricher.generate_descriptions(timeout=300)

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
def ingest():
    print("Starting full streamed ingestion...")
    config = GeneratorConfig()
    orchestrator = Orchestrator(config)
    writer = IcebergWriter(config)
    
    # 1. Generate & Write Streamed
    writer.write_stream(orchestrator.generate_all_streamed())
    
    # 2. Register Catalog
    catalog()
    print("Ingestion complete.")

@app.command()
def validate(local: bool = True):
    print("Running validation checks...")
    config = GeneratorConfig()
    
    if local:
        for name in ["audience", "cookie_registry", "campaigns", "creatives", "pixel_events", "transactions"]:
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

            # Synonym check
            if name == "cookie_registry":
                c_id = table.column("cookie_id").to_pylist()
                v_id = table.column("visitor_id").to_pylist()
                if c_id != v_id:
                    print("  FAILED: cookie_id != visitor_id")
                
                # Match rate checks
                a_id = table.column("audience_id").to_pylist()
                a_rate = sum(1 for x in a_id if x is not None) / len(a_id)
                print(f"  cookie->audience fill rate: {a_rate:.1%}")
                if abs(a_rate - config.cookie_audience_fill_rate) > 0.03:
                    print(f"  FAILED: cookie->audience rate {a_rate:.1%} outside +/- 3pp of {config.cookie_audience_fill_rate:.1%}")

            if name == "pixel_events":
                c_id = table.column("cookie_id").to_pylist()
                p_rate = sum(1 for x in c_id if x is not None) / len(c_id)
                print(f"  pixel->cookie fill rate: {p_rate:.1%}")
                if abs(p_rate - config.pixel_cookie_fill_rate) > 0.03:
                    print(f"  FAILED: pixel->cookie rate {p_rate:.1%} outside +/- 3pp of {config.pixel_cookie_fill_rate:.1%}")
            
            if name == "audience":
                lat = table.column("lat").to_pylist()
                l_lat = table.column("location_lat").to_pylist()
                if lat != l_lat:
                    print("  FAILED: lat != location_lat")

    print("Validation checks finished.")

if __name__ == "__main__":
    app()
