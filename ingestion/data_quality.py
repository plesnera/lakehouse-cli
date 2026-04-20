"""Dataplex Data Quality — create and run quality scans for marketing tables.

Defines DQ rules (NOT NULL, match-rate bounds, referential integrity) and
runs them via the DataScanService API.

Ref: https://docs.cloud.google.com/dataplex/docs/data-quality-overview
"""

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import dataplex_v1
import time
from generators.config import GeneratorConfig
from ingestion.table_metadata import METADATA_DIR, load_all_table_metadata, RuleMeta

TABLES = ["audience", "cookie_registry", "campaigns", "creatives", "pixel_events", "transactions"]


def _rule_from_meta(meta: RuleMeta) -> dataplex_v1.DataQualityRule:
    """Convert a RuleMeta to a dataplex DataQualityRule."""
    kwargs = dict(
        name=f"{meta.rule_type}_{meta.column}",
        column=meta.column,
        dimension=meta.dimension,
        threshold=meta.threshold,
    )
    if meta.rule_type == "non_null":
        kwargs["non_null_expectation"] = dataplex_v1.DataQualityRule.NonNullExpectation()
    elif meta.rule_type == "set":
        kwargs["set_expectation"] = dataplex_v1.DataQualityRule.SetExpectation(values=meta.values)
    elif meta.rule_type == "regex":
        kwargs["regex_expectation"] = dataplex_v1.DataQualityRule.RegexExpectation(pattern=meta.pattern)
    elif meta.rule_type == "range":
        kwargs["range_expectation"] = dataplex_v1.DataQualityRule.RangeExpectation(
            min_value=meta.min_value,
            max_value=meta.max_value,
            strict_min=meta.strict_min_enabled,
            strict_max=meta.strict_max_enabled,
        )
    return dataplex_v1.DataQualityRule(**kwargs)


def load_dq_rules_from_md(metadata_dir: str = METADATA_DIR) -> dict[str, list[dataplex_v1.DataQualityRule]]:
    """Load DQ rules from markdown files, return {table_id: [DataQualityRule, ...]}."""
    all_meta = load_all_table_metadata(metadata_dir)
    rules: dict[str, list[dataplex_v1.DataQualityRule]] = {}
    for table_id, meta in all_meta.items():
        rules[table_id] = [_rule_from_meta(rule) for rule in meta.dq_rules]
    return rules


class DataQualityManager:
    """Creates and runs Dataplex data quality scans."""

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.client = dataplex_v1.DataScanServiceClient()
        self.parent = f"projects/{config.project_id}/locations/{config.location}"

    def create_and_run_scans(self, tables: list[str] | None = None, dry_run: bool = False) -> None:
        """Create a DQ DataScan for each table and trigger a run."""
        tables = tables or TABLES
        dq_rules = load_dq_rules_from_md()

        for table in tables:
            scan_id = f"quality-{table.replace('_', '-')}-{int(time.time())}"
            bq_resource = (
                f"//bigquery.googleapis.com/projects/{self.config.project_id}"
                f"/datasets/{self.config.iceberg_namespace}/tables/{table}"
            )
            rules = dq_rules.get(table, [])

            if dry_run:
                print(f"  [dry-run] Would create quality scan: {scan_id} ({len(rules)} rules)")
                continue

            scan_name = self._ensure_scan(scan_id, bq_resource, table, rules)
            self._run_scan(scan_name)

    def get_results(self, tables: list[str] | None = None) -> None:
        """Print the latest quality scan results."""
        tables = tables or TABLES

        for table in tables:
            scan_name = f"{self.parent}/dataScans/quality-{table}"
            try:
                scan = self.client.get_data_scan(
                    request=dataplex_v1.GetDataScanRequest(
                        name=scan_name,
                        view=dataplex_v1.GetDataScanRequest.DataScanView.FULL,
                    )
                )
                result = scan.data_quality_result
                if result:
                    passed = result.passed
                    print(f"  {'✅' if passed else '❌'} {table}: "
                          f"{'PASSED' if passed else 'FAILED'} — "
                          f"{len(result.rules)} rules evaluated")
                else:
                    print(f"  ⏳ {table}: scan exists but no results yet")
            except NotFound:
                print(f"  ❌ {table}: no quality scan found")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_scan(self, scan_id: str, bq_resource: str, table: str,
                     rules: list[dataplex_v1.DataQualityRule]) -> str:
        scan_name = f"{self.parent}/dataScans/{scan_id}"
        try:
            self.client.get_data_scan(
                request=dataplex_v1.GetDataScanRequest(name=scan_name)
            )
            print(f"  ℹ️  Quality scan exists: {scan_id}")
            return scan_name
        except NotFound:
            pass

        data_scan = dataplex_v1.DataScan(
            display_name=f"Quality — {table}",
            description=f"Data quality rules for the {table} marketing table.",
            data=dataplex_v1.DataSource(resource=bq_resource),
            data_quality_spec=dataplex_v1.DataQualitySpec(rules=rules),
            execution_spec=dataplex_v1.DataScan.ExecutionSpec(
                trigger=dataplex_v1.Trigger(
                    on_demand=dataplex_v1.Trigger.OnDemand()
                ),
            ),
        )

        try:
            operation = self.client.create_data_scan(
                request=dataplex_v1.CreateDataScanRequest(
                    parent=self.parent,
                    data_scan_id=scan_id,
                    data_scan=data_scan,
                )
            )
            result = operation.result()
            print(f"  ✅ Created quality scan: {scan_id} ({len(rules)} rules)")
            return result.name
        except AlreadyExists:
            print(f"  ℹ️  Quality scan already exists: {scan_id}")
            return scan_name

    def _run_scan(self, scan_name: str) -> None:
        try:
            self.client.run_data_scan(
                request=dataplex_v1.RunDataScanRequest(name=scan_name)
            )
            print(f"  🚀 Triggered run for: {scan_name.split('/')[-1]}")
        except Exception as e:
            print(f"  ⚠️  Failed to run {scan_name.split('/')[-1]}: {e}")
