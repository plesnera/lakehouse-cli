import json

import typer
from lake_cli.config import Config, TABLES
from lake_cli.dataplex_lake import DataplexManager
from lake_cli.catalog import CatalogManager
from lake_cli.tag_writer import TagWriter
from lake_cli.glossary_writer import GlossaryWriter
from lake_cli.table_and_column_insights import HybridMetadataEnricher
from lake_cli.glossary_manager import BusinessGlossaryManager
from lake_cli.lakehouse_catalog import LakehouseCatalogManager
from lake_cli.data_profiling import DataProfilingManager
from lake_cli.data_quality import DataQualityManager
from lake_cli.dataset_insights import DatasetInsightsManager
from lake_cli.vector_search import VectorSearchManager
from lake_cli.bqml_gemini import BQMLGeminiManager
from lake_cli.continuous_queries import ContinuousQueryManager
from lake_cli.related_entries import RelatedEntriesManager

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
    lake_catalog = LakehouseCatalogManager(config)
    result = lake_catalog.ensure_catalog()
    if not result.get("catalog_exists", False):
        print(f"❌ Catalog does not exist: {config.lakehouse_catalog_name}")
        print("   Create it manually in GCP Console first, then re-run.")
        return

    lake_catalog.ensure_namespace()

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
    print("Note: Run 'uv run lake enrich-metadata' to add table/column descriptions")


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
        uv run lake setup-catalog --catalog-name marketing-lakehouse --full --dry-run

        # Verify catalog and create namespace
        uv run lake setup-catalog --catalog-name marketing-lakehouse --full

        # Verify catalog only (no namespace)
        uv run lake setup-catalog --catalog-name marketing-lakehouse
    """
    config = Config()

    # Apply catalog name if provided
    if catalog_name:
        config.lakehouse_catalog_name = catalog_name

    lake_catalog = LakehouseCatalogManager(config)

    # First verify catalog exists (user must create manually)
    result = lake_catalog.ensure_catalog(dry_run=dry_run)
    if not result.get("catalog_exists", False):
        print("❌ Catalog does not exist. Create it manually first.")
        return

    if full:
        # Create namespace
        lake_catalog.ensure_namespace(dry_run=dry_run)


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
        uv run lake enrich-metadata

        # You can use the automated google insights as a starting point by running and then copy-paste in to YAML
        # Enrich specific tables with manual files
        uv run lake enrich-metadata \\
          --table-names wpp-dataproducts-lakehouse.marketing.audience,wpp-dataproducts-lakehouse.marketing.campaigns \\
          --metadata-files audience.yaml,campaigns.yaml

        # Mode 2: Google insights only (no manual files needed)
        # Enrich specific tables with pure Google insights
        uv run lake enrich-metadata \\
          --table-names wpp-dataproducts-lakehouse.marketing.campaigns \\
          --google-insights

        # Enrich all tables with pure Google insights
        uv run lake enrich-metadata --google-insights

        # Preview changes without applying (dry-run mode)
        uv run lake enrich-metadata --dry-run
        uv run lake enrich-metadata --table-names campaigns --google-insights --dry-run

        # Create YAML metadata templates for manual descriptions
        uv run lake create-templates
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
        uv run lake create-templates
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
        uv run lake manage-glossary --dry-run

        # Create glossary from default template
        uv run lake manage-glossary --action create

        # Create from a custom file
        uv run lake manage-glossary --action create --input my_glossary.yaml

        # Reset and recreate
        uv run lake manage-glossary --action create --reset

        # Validate existing glossary
        uv run lake manage-glossary --action validate

        # Link terms to BigQuery assets
        uv run lake manage-glossary --action apply
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
    output: str = typer.Option("dataset_insights.json", "--output", "-o", help="Output file path for insights results"),
):
    """Create and run Dataplex dataset-level insights scans for AI-generated metadata.

    Dataset-level insights analyze an entire BigQuery dataset to produce:
    - AI-generated dataset description
    - Relationship graph (how tables connect)
    - Cross-table SQL sample queries
    - Discovered primary/foreign key relationships

    Examples:
        # Create and run scan (default behavior)
        uv run lake dataset-insights

        # Preview scan without executing
        uv run lake dataset-insights --dry-run

        # Get latest results
        uv run lake dataset-insights --results

        # Explicitly run scan
        uv run lake dataset-insights --run

        # Write results to a custom file
        uv run lake dataset-insights --results -o my_insights.json
    """
    config = Config()
    mgr = DatasetInsightsManager(config)

    if results:
        insights = mgr.get_results(timeout=timeout)
        with open(output, "w") as f:
            json.dump(insights, f, indent=2)
        print(f"\n📄 Insights written to {output}")
    else:
        scan_id = mgr.create_scan(dry_run=dry_run, timeout=timeout)
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
        uv run lake quality --check-rules

        # Sync rules without running scans
        uv run lake quality --sync-only

        # Sync rules and run scans (default behavior)
        uv run lake quality

        # Preview what would be synced
        uv run lake quality --sync-only --dry-run

        # Run specific tables only
        uv run lake quality --table-names campaigns,transactions

        # View results of previous runs
        uv run lake quality --results
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
def list_related_entries(
    term: str = typer.Option(..., "--term", help="Glossary term to search for (e.g., 'advertiser')"),
    glossary: str = typer.Option(None, "--glossary", help="Glossary ID or display name (default: first glossary found)"),
):
    """Find catalog entries whose schema contains a column matching a glossary term.

    Given a glossary term (e.g. 'advertiser'), returns all data entries that
    contain a matching column with Resource Name, Column Name, Project, and
    Fully Qualified Name.

    Examples:
        # Search for all entries with a column matching 'advertiser'
        uv run lake list-related-entries --term advertiser

        # Specify a glossary
        uv run lake list-related-entries --term brand \\
          --glossary marketing-business-glossary
    """
    config = Config()
    mgr = RelatedEntriesManager(config)
    mgr.list_related_entries(term_name=term, glossary=glossary)


@app.command()
def scan_for_related_entries(
    catalog: str = typer.Option(..., "--catalog", help="BigLake catalog name to scan"),
    namespace: str = typer.Option(None, "--namespace", help="Optional namespace filter within the catalog"),
    glossary: str = typer.Option(None, "--glossary", help="Glossary ID or display name (default: first glossary found)"),
    output: str = typer.Option(None, "--output", "-o", help="Write proposals to a YAML file for curation and later apply"),
    fuzzy_score_threshold: int = typer.Option(0, "--fuzzy-score-threshold", help="Filter out fuzzy proposals with a score below this threshold"),
    project: str = typer.Option(None, "--project", help="Override the Google Cloud project (default: derived from glossary resource path)"),
    location: str = typer.Option(None, "--location", help="Override the location (default: derived from glossary resource path)"),
):
    """Compare a BigLake catalog against a glossary to find matching and unmatched terms.

    Scans all table columns in the BigLake catalog and matches them against
    glossary terms using exact, synonym, and fuzzy semantic matching.

    Output includes:
    - Phase A: terms with exact column matches (already matched)
    - Phase B: fuzzy semantic proposals for unmatched terms

    When --output is provided, Phase B proposals are written to a YAML file
    that can be curated (rows removed or commented out) and then applied
    with ``apply-related-entries``.

    Examples:
        # Scan default catalog against default glossary
        uv run lake scan-for-related-entries \\
          --catalog wpp-dataproducts-lakehouse-warehouse

        # Scan with namespace filter
        uv run lake scan-for-related-entries \\
          --catalog wpp-dataproducts-lakehouse-warehouse \\
          --namespace marketing

        # Specify glossary explicitly
        uv run lake scan-for-related-entries \\
          --catalog wpp-dataproducts-lakehouse-warehouse \\
          --glossary marketing-business-glossary

        # Export proposals to YAML for curation
        uv run lake scan-for-related-entries \\
          --catalog wpp-dataproducts-lakehouse-warehouse \\
          --namespace marketing \\
          --output proposals.yaml \\
          --fuzzy-score-threshold 10
    """
    config = Config()
    mgr = RelatedEntriesManager(config)
    exact, fuzzy = mgr.scan_for_related_entries(
        catalog_name=catalog, namespace=namespace, glossary=glossary, fuzzy_score_threshold=fuzzy_score_threshold
    )

    if output:
        # Resolve glossary ID for the export metadata, and pull the
        # project/location out of the glossary resource path so the YAML
        # is self-describing (avoids writing a silent fallback like
        # "my-gcp-project" into the file).
        glossary_info = mgr._discover_glossary(glossary)
        glossary_name = glossary_info["name"]
        parts = glossary_name.split("/")
        # name is shaped: projects/{p}/locations/{l}/glossaries/{id}
        discovered_project = parts[1] if len(parts) > 1 and parts[0] == "projects" else None
        discovered_location = parts[3] if len(parts) > 3 and parts[2] == "locations" else None

        glossary_id = glossary_name.rsplit("/", 1)[-1]
        glossary_project = project or discovered_project or config.project_id
        glossary_location = location or discovered_location or config.location

        mgr.export_proposals_yaml(
            exact_matches=exact,
            fuzzy_proposals=fuzzy,
            output_path=output,
            catalog_name=catalog,
            namespace=namespace,
            glossary_id=glossary_id,
            glossary_project=glossary_project,
            glossary_location=glossary_location,
        )


@app.command()
def apply_related_entries(
    input: str = typer.Option(..., "--input", help="Path to curated proposals YAML/JSON file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and preview; do not mutate"),
    glossary: str = typer.Option(None, "--glossary", help="Override glossary ID from the file"),
    project: str = typer.Option(None, "--project", help="Override the Google Cloud project"),
    location: str = typer.Option(None, "--location", help="Override the location (default: from file or us-east1)"),
):
    """Apply curated related-entry proposals from a YAML file.

    Reads a proposals file (produced by ``scan-for-related-entries --output``),
    validates each proposal, and creates related-entry links in Dataplex
    Catalog via ``gcloud alpha dataplex entry-links create`` (link type
    ``entryLinkTypes/definition``). Each link connects a glossary-term entry
    to a BigLake table entry.

    The link is always created in the ``@biglake`` entry-group (the SOURCE
    entry's group, which the API requires for a ``definition`` link), and
    the references are ordered BigLake-SOURCE first, term-TARGET second.

    The command is idempotent: existing relations (gcloud returns
    ``ALREADY_EXISTS``) are skipped with an informational message rather
    than duplicated.

    Examples:
        # Preview changes
        uv run lake apply-related-entries \\
          --input proposals.yaml --dry-run

        # Execute
        uv run lake apply-related-entries \\
          --input proposals.yaml

        # Override glossary
        uv run lake apply-related-entries \\
          --input proposals.yaml --glossary my-glossary
    """
    config = Config()
    mgr = RelatedEntriesManager(config)
    mgr.apply_proposals(
        input_path=input,
        dry_run=dry_run,
        glossary_override=glossary,
        project_override=project,
        location_override=location,
    )


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
    lake_catalog = LakehouseCatalogManager(config)
    try:
        lake_catalog.delete_namespace()
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
