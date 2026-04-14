# Lakehouse Content — TODO

Gap analysis of Agent.md goals vs current codebase.  
The primary objective is **enabling Google Cloud services for a demo** using synthetic marketing data. Data generation is supporting infrastructure, not the end goal.

Status: ✅ Done | ⚠️ Partial | ❌ Not started

References:
- `Agent.md` — requirements (source of truth)
- `lakehouse-final.md` — implementation design (D1–D4 schemas, catalog topology, tag template spec, validation checks)

---

## 1 — Google Cloud Service Enablement (Primary Goal)

Agent.md lists 10 GCP services to demonstrate. Current codebase only covers ~3 of them. The missing services represent the largest gap.

### 1.1 Knowledge Catalog (Dataplex) ⚠️
The unified metadata repository — semantic map of the data estate.

**What exists:**
- [x] Entry group `marketing-lakehouse` creation (`catalog.py`)
- [x] Per-table entry creation (`catalog.py`)
- [x] Business Glossary markdown with correct synonym pairs (`business_glossaries/glossary.md`)
- [x] Glossary manager: create/validate/reset/apply workflow (`glossary_manager.py`)
- [x] Synonym and related-term link creation
- [x] Definition links (term → BigQuery table)

**What's missing:**
- [ ] `catalog.py register_entries()` doesn't attach display names or descriptions — the `descriptions` dict on line 33 is defined but never used. Populate entries per `lakehouse-final.md` §2.3.
- [ ] `tag_writer.py apply_tags()` is a no-op. Must apply the `marketing_table_metadata` aspect with per-table field values (business_owner, data_domain, pii_class, refresh_cadence, row_count_approx, marketing_usecases) as specified in `lakehouse-final.md` §2.2 and §2.3.
- [ ] Business Glossary is missing several terms listed in `lakehouse-final.md` §2.1: Audience Segment, Impression, Conversion, ROAS, LTV. Currently only has the synonym-pair terms (cookie_id, hashed_email, brand, country_code, lat, lon).

### 1.2 BigLake Unified Storage ⚠️
Open-format Iceberg data with unified security.

**What exists:**
- [x] `iceberg_writer.py` — writes tables via pyiceberg with local SQL catalog
- [x] `bq_external.py` — registers BigLake external tables in BigQuery

**What's missing:**
- [ ] Partition column naming mismatch: code uses `partition_date` / `event_date`, `lakehouse-final.md` schema specifies `_partition_date`. Align to the design doc name.
- [ ] `bq_external.py` does not set `file_set_spec_type` or any BigLake-specific options for the Iceberg table registration — verify the external config is complete for the BigLake Iceberg integration.

### 1.3 Automated Data Insights Generation ⚠️
Generates natural language summaries and column descriptions.

**What exists:**
- [x] `bq_metadata_hybrid.py` — hybrid and Google-insights-only enrichment modes
- [x] CLI `enrich-metadata` command with `--google-insights` and `--metadata-files` flags

**What's broken / missing:**
- [ ] `_generate_hybrid_descriptions()` (line 243) is incomplete — loads manual descriptions but has no return statement; implicitly returns `None`. Calling `generate_descriptions()` will crash.
- [ ] Lines 302–326 in `_generate_hybrid_descriptions_with_file()` are dead code after an earlier return. Remove.
- [ ] Current "Google insights" mode is heuristic pattern-matching on column names, not actual Dataplex API integration. Consider whether this should call the real Dataplex `GenerateDataInsights` / table-level insights API, or whether the pattern-based approach is sufficient for the demo.

### 1.4 Automated Profiling of Data ❌
Scans data for statistical distributions and anomalies — "grounding" context for agents.

- [ ] No utility exists. Create `ingestion/data_profiling.py` (or extend CLI) to trigger Dataplex data profiling scans via the `DataScanService` API.
- [ ] Add CLI command: `uv run python -m ingestion.cli profile` to create and run a DataScan for each table.
- [ ] Store or display profiling results to demonstrate the service.

Ref: https://docs.cloud.google.com/dataplex/docs/data-profiling-overview

### 1.5 Dataplex Data Quality ❌
Automated quality checks ensuring agents use "Gold-standard" data.

- [ ] No utility exists. Create `ingestion/data_quality.py` to define and run Dataplex Data Quality rules via the `DataScanService` API.
- [ ] Define quality rules that validate the synthetic data (e.g. `pan_token IS NOT NULL`, match-rate bounds, FK referential integrity checks from `lakehouse-final.md` §4.3).
- [ ] Add CLI command: `uv run python -m ingestion.cli quality` to create, run, and report quality scan results.

Ref: https://docs.cloud.google.com/dataplex/docs/data-quality-overview

### 1.6 BigQuery Vector Search ❌
Semantic similarity searches and RAG at scale.

- [ ] No utility or example SQL exists. Create `ingestion/vector_search.py` or a SQL script to:
  - Create a remote model connection to a text-embedding model (e.g. `textembedding-gecko`)
  - Generate embeddings on relevant text columns (e.g. `segment_name`, `interests`, `creative_name`, `theme_tags`)
  - Store embeddings in a BQ table
  - Demonstrate a `VECTOR_SEARCH` query (e.g. "find audience segments similar to 'eco-conscious millennials'")
- [ ] Add CLI command or documented SQL snippets to set this up.

Ref: https://cloud.google.com/bigquery/docs/vector-search-intro

### 1.7 BigQuery ML — Remote Models & Gemini ❌
Invoke Gemini models directly within SQL to process unstructured text or generate embeddings.

- [ ] No utility exists. Create example SQL or a utility that:
  - Creates a remote model connection to Gemini via `CREATE MODEL ... REMOTE`
  - Demonstrates `ML.GENERATE_TEXT` on synthetic data (e.g. summarise campaign performance, classify creative themes)
  - Demonstrates `ML.GENERATE_EMBEDDING` for vector search integration
- [ ] Add to CLI or provide documented SQL scripts.

Ref: https://cloud.google.com/bigquery/docs/generate-text-tutorial

### 1.8 BigQuery Continuous Queries ❌
Event-driven ingestion and real-time processing.

- [ ] No utility exists. Create an example continuous query definition that demonstrates:
  - A `CREATE TABLE ... AS SELECT ... OPTIONS(continuous=true)` pattern
  - Reacting to new rows in `pixel_events` (e.g. real-time CTR aggregation or anomaly flagging)
- [ ] Even if streaming generation is out of scope, a continuous query on the batch data can demo the capability.

Ref: https://cloud.google.com/bigquery/docs/continuous-queries

### 1.9 Dataform for Agentic Pipelines ❌
SQL-based transformations that agents can programmatically update.

- [ ] No Dataform definitions exist. Create `dataform/` directory with:
  - `dataform.json` — project configuration targeting `wpp-dataproducts-lakehouse`
  - SQLX transformation files implementing the derived metrics from `lakehouse-final.md` §1.6 (CTR, ROAS, LTV, etc.)
  - At minimum: a staging model, an aggregated campaign performance model, and an LTV model
- [ ] Register the Dataform repository in the GCP project.
- [ ] Optionally add CLI integration: `uv run python -m ingestion.cli dataform`

Ref: https://cloud.google.com/dataform/docs/overview

### 1.10 BigQuery Data Engineering Agent ❌
AI-powered service that builds and self-heals data pipelines via natural language.

- [ ] No utility or documentation. This is a GCP-managed service, so the main task is:
  - Document how to enable the Data Engineering Agent on the `marketing` dataset
  - Provide example natural-language prompts that work with the synthetic data
  - Ensure the catalog metadata (descriptions, tags, glossary) is rich enough for the agent to discover and use
- [ ] Can be delivered as documentation + verified setup rather than code.

Ref: https://cloud.google.com/bigquery/docs/data-engineering-agent-pipelines

---

## 2 — Dataplex Catalog Metadata Content (D2)

These are content gaps within the catalog/metadata subsystem (separate from the structural code issues in §1.1).

### 2.1 Metadata Description Files
Of 6 tables, only `audience.md` has real content. The rest are empty templates.

- [x] `metadata_descriptions/audience.md` — filled (but missing `location_lat`/`location_lon` synonym columns)
- [ ] `metadata_descriptions/campaigns.md` — 4 of 14 columns filled; rest are placeholders
- [ ] `metadata_descriptions/cookie_registry.md` — all placeholders
- [ ] `metadata_descriptions/creatives.md` — all placeholders
- [ ] `metadata_descriptions/pixel_events.md` — all placeholders
- [ ] `metadata_descriptions/transactions.md` — all placeholders
- [ ] `metadata_descriptions/audience_profile.md` — orphan file (no matching table). Remove.

Populate using the column descriptions from `lakehouse-final.md` §2.3 per-table entries.

### 2.2 `audience.md` Completeness
- [ ] Add `location_lat` and `location_lon` columns with synonym annotations matching `lakehouse-final.md`.
- [ ] Add `panel_weight` and `created_at` descriptions.

---

## 3 — Data Generators (D3)

The generator architecture is complete. Remaining work is config alignment and data fidelity.

### 3.1 Scale Parameters
Config defaults in `generators/config.py` are dev-scale, not production.

| Parameter | Current | Required (Agent.md) |
|-----------|---------|---------------------|
| `n_audience_participants` | 100 | 8 000 |
| `n_audience_segments` | 10 | ~500 |
| `n_cookies` | 1 000 | 80 000 |
| `n_campaigns` | 10 | ~200 |
| `n_creatives_per_campaign` | 2 | ~5 (→ ~1 000 total) |
| `n_pixel_events` | 5 000 | 2 000 000 |
| `n_transactions` | 1 000 | 500 000 |

- [ ] Add a `--full-scale` / `--dev` CLI flag to toggle between dev and production configs. Keep dev defaults for fast iteration; production defaults for demo.

### 3.2 Fictional Brands
Agent.md specifies: **Lucky Cola**, **Force Automotive**, **AEKI Living**.  
Code uses: AeroCorp, BioGlow, CloudScale, DynaMotive, EcoPure.

- [ ] Update brand lists in `campaigns.py`, `transactions.py`, and `audience.py _generate_affinity()`.

### 3.3 Event Type Coverage
`lakehouse-final.md` §1.2 pixel_events schema lists: impression, click, video_start, **video_q1, video_q2, video_q3**, video_complete, engagement.  
Generator only produces: impression, click, video_start, video_complete, engagement.

- [ ] Add video quartile events (video_q1, video_q2, video_q3) to `pixel_events.py` event type distribution. These are needed for the VTR metric calculation.

### 3.4 Partition Column Name
`lakehouse-final.md` specifies `_partition_date`; code uses `partition_date` (no leading underscore).

- [ ] Align naming — either update code or design doc. The underscore prefix is the Iceberg convention.

### 3.5 Per-Market Cookie/HEM Variation
Agent.md says "UK −5pp, Japan −10pp on **all** cookie/hem join rates", but only transaction rates are varied. `lakehouse-final.md` §1.4 clarifies variation is applied to txn rates only.

- [ ] Confirm whether per-market variation should apply to cookie_registry rates too, or just transactions (as lakehouse-final.md specifies). Currently only transactions vary.

### 3.6 Missing `__init__.py`
- [ ] Add `generators/__init__.py` and `ingestion/__init__.py` for packaging and IDE support.

---

## 4 — Ingestion & CLI Utilities (D4)

### 4.1 Missing `reset` Command
Agent.md requires a `reset` command. `lakehouse-final.md` specifies: `cli.py reset --confirm` (tears down all resources).

- [ ] Implement `reset` CLI command that deletes: Iceberg tables, BQ external tables, Dataplex entries/tags, glossary resources, and optionally GCS data.

### 4.2 Broken `bq_metadata_hybrid.py`
- [ ] Fix `_generate_hybrid_descriptions()` — missing return statement at line 258.
- [ ] Remove dead code at lines 302–326.

### 4.3 GCP Validation (`validate` without `--local`)
`lakehouse-final.md` §4.3 defines comprehensive GCP validation checks that don't exist.

- [ ] Implement GCP-mode validation covering:
  - Row counts via `SELECT COUNT(*) FROM {table}` vs config
  - Pixel events within campaign date windows
  - Match-rate checks per market (within ±3pp)
  - No orphan `creative_id` values in pixel_events
  - Synonym column equality checks
  - Iceberg snapshot validity via pyiceberg
  - All catalog entries registered (Dataplex API check)
  - All tag templates applied (Dataplex API check)
  - Business Glossary terms and synonym links visible

### 4.4 Local Validation Gaps
Existing `validate --local` checks some rates but not all.

- [ ] Add checks for:
  - `audience.hem` fill rate (60%)
  - `cookie_registry.hem` fill rate (35%)
  - `transactions.cookie_id` and `transactions.hem` per-market rates
  - Synonym column equality for `campaigns.brand == campaigns.advertiser`
  - Synonym column equality for `audience.lat == audience.location_lat`
  - Row count for creatives (should equal `n_campaigns × n_creatives_per_campaign`)

---

## 5 — Data Model Design Document (D1)

`lakehouse-final.md` effectively IS the design document. The gap is formal recognition.

- [ ] Verify `lakehouse-final.md` covers all required content from Agent.md D1 (schemas, fill rates, synonym strategy). If so, reference it as the design doc.
- [ ] Fix the `lakehouse-tasks-claude.md` reference in Agent.md — it points to a non-existent file.

---

## 6 — Cross-Cutting / Quality

- [ ] **No automated tests.** Add at minimum:
  - Unit tests for generators (schema validation, match-rate checks, deterministic output with fixed seed)
  - Unit test for glossary markdown parser
  - Integration test for local generate → validate round-trip
- [ ] **README.md has duplicate section numbering** — two §2 and two §5 headings.
- [ ] **End-to-end GCP run** — perform a full `ingest` and verify all acceptance criteria from Agent.md D3 and D4.
- [ ] **Document GCP pre-requisites** — the 6 infrastructure items from Agent.md §Infrastructure Pre-requisites should be checkable/automatable, not just listed.

---

## Priority Order

Recommended execution sequence based on demo impact:

1. **Fix broken code** (§4.2, §1.3 broken methods) — unblocks everything
2. **Catalog entries + tag application** (§1.1) — core demo feature, already partially built
3. **Metadata description files** (§2.1) — enables Data Insights service
4. **Data Quality rules** (§1.5) — high demo value, uses existing data
5. **Data Profiling** (§1.4) — high demo value, uses existing data
6. **Vector Search + Embeddings** (§1.6) — flagship AI feature
7. **BQML / Gemini integration** (§1.7) — flagship AI feature
8. **Dataform transformations** (§1.9) — derived metrics layer
9. **Generator config fixes** (§3.1–3.4) — scale, brands, event types
10. **Continuous Queries** (§1.8) — nice-to-have
11. **Data Engineering Agent docs** (§1.10) — documentation only
12. **`reset` CLI command** (§4.1) — operational convenience
13. **Tests** (§6) — hardening
- [ ] **README.md has duplicate section numbering** — two sections labelled "### 2." and two labelled "### 5." Fix heading numbers for clarity.
