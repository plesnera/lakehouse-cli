"""
Agentic Maintainer Reference — Lakehouse CLI
============================================
This file is a living reference for AI agents (and human maintainers) working on
the lakehouse-cli codebase.  It captures architectural intent, sharp edges, and
maintenance rules that are not obvious from the code alone.

If you are reading this, you are probably about to modify ingestion/cli.py,
ingestion/table_and_column_insights.py, or ingestion/glossary_manager.py.
Read the "Critical Code Paths" and "Agent Maintenance Rules" sections first.
"""

# ──────────────────────────────────────────────────────────────────────────────
# 1. Module Purpose & Architecture
# ──────────────────────────────────────────────────────────────────────────────
"""
The CLI is a thin Typer wrapper around a set of GCP-orchestration managers.
The entry point is ingestion.cli:app (see pyproject.toml [project.scripts]).

Key abstractions
----------------
• Config (ingestion/config.py)
    – Pydantic BaseModel that resolves project_id from gcloud or env var.
    – Supports cross-project scenarios (data_project_id vs catalog_project_id).
    – TABLES = ["audience", "cookie_registry", "campaigns", "creatives",
                "pixel_events", "transactions"] is the single source of truth
      for the six marketing tables.

• HybridMetadataEnricher (ingestion/table_and_column_insights.py)
    – Enriches BigQuery table/column descriptions from TWO mutually-exclusive
      sources: manual YAML files OR Google Dataplex insights.
    – NEVER combines both in the same run.  The design principle is clean
      separation (see module docstring).

• BusinessGlossaryManager (ingestion/glossary_manager.py)
    – Dataplex Glossary REST API client.  Upserts glossaries, categories,
      terms, synonym links, and related-term links.

• LakehouseCatalogManager, DataplexManager, CatalogManager, TagWriter,
  GlossaryWriter, DataProfilingManager, DataQualityManager,
  DatasetInsightsManager, VectorSearchManager, BQMLGeminiManager,
  ContinuousQueryManager, RelatedEntriesManager
    – GCP resource managers used by the catalog pipeline and other commands.

Command → method mapping
------------------------
catalog                   → _run_catalog(config)  (orchestrates 5 managers in sequence)
setup-catalog             → LakehouseCatalogManager.ensure_catalog / ensure_namespace
enrich-metadata           → HybridMetadataEnricher.* (see §3)
create-templates          → HybridMetadataEnricher.create_all_templates +
                            BusinessGlossaryManager.generate_template_files
manage-glossary           → BusinessGlossaryManager.*
profile / quality / ...   → DataProfilingManager / DataQualityManager / etc.
"""

# ──────────────────────────────────────────────────────────────────────────────
# 2. Command Reference (enrich-metadata)
# ──────────────────────────────────────────────────────────────────────────────
"""
The enrich-metadata command is the most commonly modified surface and has the
most subtle behaviour.

CLI flags
---------
--table-names <csv>       → Process only these tables (default: all tables in dataset)
--metadata-files <csv>    → Explicit YAML files to use (must match table-names order)
--google-insights         → Use Dataplex DATA_DOCUMENTATION scans instead of YAML
--dry-run                 → Preview changes without applying

Call graph (no --table-names, no --google-insights)
----------------------------------------------------
  cli.enrich_metadata()
    └─ enricher.generate_descriptions(timeout=300, dry_run=dry_run)
         └─ _generate_descriptions_core(tables, dry_run=dry_run)

Call graph (with --google-insights)
------------------------------------
  cli.enrich_metadata()
    ├─ enricher.generate_descriptions_with_google_insights(...)
    │     └─ _generate_descriptions_core(..., use_google_insights=True, ...)
    └─ enricher.generate_descriptions_for_tables_with_google_insights(...)
          └─ _generate_descriptions_core(..., use_google_insights=True, ...)

Call graph (with --table-names + --metadata-files)
---------------------------------------------------
  cli.enrich_metadata()
    └─ enricher.generate_descriptions_for_tables_with_files(
           tables_to_enrich, metadata_files_list, ..., use_google_insights=False)

"""

# ──────────────────────────────────────────────────────────────────────────────
# 3. Critical Code Paths & Known Pitfalls
# ──────────────────────────────────────────────────────────────────────────────
"""
A. _generate_descriptions_core default parameter trap
-------------------------------------------------------
File: ingestion/table_and_column_insights.py
Line: 51-52

def _generate_descriptions_core(
    self, table_names: List[str], metadata_files: Optional[List[str]] = None,
    use_google_insights: bool = True, dry_run: bool = False
):

The default for use_google_insights is True.
This means every caller that forgets to pass use_google_insights=False
will silently trigger Google Insights and IGNORE manual YAML files.

Known affected callers (as of last audit):
  • generate_descriptions(self, ...)
      line 106-109  → does NOT pass use_google_insights=False
  • generate_descriptions_for_tables(self, ...)
      line 111-113  → does NOT pass use_google_insights=False

Fix pattern: always pass use_google_insights=False from the manual-only
public methods.

B. Strict filename matching in manual mode
------------------------------------------
File: ingestion/table_and_column_insights.py
Method: _load_manual_descriptions

When metadata_file is None, the code looks for:
    metadata/{table_id}.yaml

It does NOT scan the metadata/ directory to discover YAML files whose
internal table_id field matches the table.  This means a file named
audience_profile.yaml (with table_id: audience inside) is silently skipped.

Fix pattern (used by generate_descriptions):
    import glob, yaml
    yaml_mapping = {}
    for yaml_file in glob.glob(os.path.join(self.metadata_dir, "*.yaml")):
        data = yaml.safe_load(f)
        if data and isinstance(data, dict) and "table_id" in data:
            yaml_mapping[data["table_id"]] = yaml_file
    metadata_files = [yaml_mapping.get(table_id) for table_id in tables]

C. generate_descriptions_for_tables_with_files does its own loop
------------------------------------------------------------------
File: ingestion/table_and_column_insights.py
Lines: 124-184

This method duplicates the logic from _generate_descriptions_core
(table-ref resolution, mode branching, dry-run handling, exception catching).
Any fix to _generate_descriptions_core must be mirrored here, or better,
this method should be refactored to delegate fully to _generate_descriptions_core.

D. generate_descriptions_for_tables_with_files accepts use_google_insights=True
--------------------------------------------------------------------------------
Despite being called from the CLI with use_google_insights=False, the parameter
signature still allows True.  If an internal caller passes True, it will use
Google insights and ignore the explicit metadata_files.  This is a foot-gun.

"""

# ──────────────────────────────────────────────────────────────────────────────
# 4. Configuration & Environment
# ──────────────────────────────────────────────────────────────────────────────
"""
Config resolution order (ingestion/config.py)
---------------------------------------------
1. Explicit CLI flags (--data-project, --catalog-project, etc.)
2. gcloud config get-value project  (subprocess, 5s timeout)
3. GOOGLE_CLOUD_PROJECT env var
4. If none of the above yields a project, `Config.get_current_gcloud_project`
   returns `None` and the field validation in pydantic raises — there is no
   silent literal fallback. Set GOOGLE_CLOUD_PROJECT or run
   `gcloud config set project` before invoking the CLI.

Required external state
-------------------------
• gcloud authenticated (for project resolution and API auth)
• metadata/ directory exists (created on-the-fly by os.makedirs)
• metadata/glossary.yaml exists for manage-glossary
• BigQuery tables must already exist (the tool does NOT create data)
• Dataplex Lakehouse REST catalog must be created MANUALLY before setup-catalog

Directory layout expected at runtime
-------------------------------------
<repo_root>/
├── metadata/
│   ├── audience.yaml
│   ├── campaigns.yaml
│   ├── ...
│   └── glossary.yaml
├── ingestion/
│   ├── cli.py
│   ├── config.py
│   ├── table_and_column_insights.py
│   └── ...
└── tests/
    └── cli/
        ├── test_enrich.py
        └── test_glossary.py
"""

# ──────────────────────────────────────────────────────────────────────────────
# 5. Testing & Verification
# ──────────────────────────────────────────────────────────────────────────────
"""
Run the test suite
------------------
    uv run pytest tests/cli/test_enrich.py -v
    uv run pytest tests/cli/test_glossary.py -v

Key assertions in test_enrich.py
--------------------------------
• test_no_args_calls_generate_descriptions
  → verifies that "enrich-metadata" with no flags calls
    instance.generate_descriptions()  (not the google-insights variant)

• test_dry_run_passed_through
  → verifies that --dry-run is forwarded to generate_descriptions(timeout=300,
    dry_run=True)

• test_specific_tables_with_metadata_files
  → verifies generate_descriptions_for_tables_with_files is called with the
    exact table and metadata-file lists, and use_google_insights=False

Important: these tests mock HybridMetadataEnricher entirely.  They do NOT
exercise _generate_descriptions_core logic.  When fixing a bug inside the
enricher class, add unit tests that instantiate the real class and assert on
internal state (or at minimum assert on the arguments passed to
_generate_descriptions_core).

Adding a regression test
--------------------------
1. Add a YAML fixture under tests/fixtures/metadata/  (if it does not exist,
   create it).
2. Patch bigquery.Client to return mock tables.
3. Call the public method that was buggy.
4. Assert _generate_descriptions_core was called with the expected
   use_google_insights value and the correct metadata_files mapping.
"""

# ──────────────────────────────────────────────────────────────────────────────
# 6. Dependencies & Imports
# ──────────────────────────────────────────────────────────────────────────────
"""
Core external libraries
------------------------
• typer              — CLI framework (all commands are @app.command())
• google-cloud-bigquery, google-cloud-dataplex  — GCP SDK
• pydantic>=2.0      — Config model
• pyyaml             — YAML parsing (glossary + metadata files)
• requests           — Direct REST calls for Dataplex scans

Internal import graph (simplified)
-----------------------------------
ingestion.cli  imports  Config, HybridMetadataEnricher, BusinessGlossaryManager,
                        LakehouseCatalogManager, DataplexManager, CatalogManager,
                        TagWriter, GlossaryWriter, DataProfilingManager,
                        DataQualityManager, DatasetInsightsManager,
                        VectorSearchManager, BQMLGeminiManager,
                        ContinuousQueryManager, RelatedEntriesManager

No other module depends on ingestion.cli (it is the top-level orchestrator).
"""

# ──────────────────────────────────────────────────────────────────────────────
# 7. Agent Maintenance Rules
# ──────────────────────────────────────────────────────────────────────────────
"""
When modifying this codebase, follow these rules to avoid regressions:

1. Prefer editing existing functions over creating new helpers.
   The codebase intentionally avoids small one-off abstractions.
   If you need to add logic, put it in the existing method that needs it.

2. When you change _generate_descriptions_core, check ALL callers:
   • generate_descriptions
   • generate_descriptions_for_tables
   • generate_descriptions_for_tables_with_google_insights
   • generate_descriptions_with_google_insights
   • generate_descriptions_for_tables_with_files

3. NEVER change the default of use_google_insights=True without updating
   every caller that expects manual mode.  The safe pattern is to pass
   use_google_insights=False explicitly from the manual-only entry points.

4. If you touch metadata-file resolution logic, verify BOTH paths:
   A. explicit --metadata-files (CLI → generate_descriptions_for_tables_with_files)
   B. default discovery (CLI → generate_descriptions)

5. Keep test_enrich.py in sync.  The CLI tests assert on which method is called,
   but they do not test the enricher's internal behaviour.  Add real unit tests
   for logic changes inside table_and_column_insights.py.

6. Preserve the clean-separation design principle:
   Manual mode  → ONLY reads YAML files, NEVER calls _generate_table_insights.
   Google mode  → ONLY calls _generate_table_insights, NEVER reads YAML files.
   Do not add a "hybrid" mode that merges both sources in the same run.
"""

# ──────────────────────────────────────────────────────────────────────────────
# 8. Quick Reference: Common Tasks
# ──────────────────────────────────────────────────────────────────────────────
"""
Task: "Fix a bug where manual YAML is ignored"
  → See §3.A (default parameter trap) and §3.B (filename matching).
  → Likely need to pass use_google_insights=False and build a table_id→file map.

Task: "Add a new enrich-metadata flag"
  → Modify ingestion/cli.py enrich_metadata() signature (typer.Option).
  → Forward the flag to the appropriate HybridMetadataEnricher method.
  → Add a test in tests/cli/test_enrich.py that asserts the flag is forwarded.

Task: "Change how Dataplex scans are created"
  → Modify _generate_table_insights in ingestion/table_and_column_insights.py.
  → This method fires a one-time DATA_DOCUMENTATION scan via REST (not gRPC).
  → The scan is asynchronous; results are published to BigQuery via table labels.

Task: "Update the preset table list"
  → Change Config.TABLES in ingestion/config.py.
  → Update any hard-coded references in docs/ or metadata/ templates.
  → Regenerate templates with `uv run python -m ingestion.cli create-templates`.
"""
