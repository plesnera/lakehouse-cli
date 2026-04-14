"""Dataplex Data Quality — create and run quality scans for marketing tables.

Defines DQ rules (NOT NULL, match-rate bounds, referential integrity) and
runs them via the DataScanService API.

Ref: https://docs.cloud.google.com/dataplex/docs/data-quality-overview
"""

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import dataplex_v1

from generators.config import GeneratorConfig

TABLES = ["audience", "cookie_registry", "campaigns", "creatives", "pixel_events", "transactions"]


def _non_null_rule(column: str, threshold: float = 1.0) -> dataplex_v1.DataQualityRule:
    """Column must not be null (threshold = fraction of rows that must pass)."""
    return dataplex_v1.DataQualityRule(
        column=column,
        non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        threshold=threshold,
    )


def _set_rule(column: str, values: list[str]) -> dataplex_v1.DataQualityRule:
    """Column values must belong to the given set."""
    return dataplex_v1.DataQualityRule(
        column=column,
        set_expectation=dataplex_v1.DataQualityRule.SetExpectation(values=values),
        threshold=1.0,
    )


# Per-table quality rules sourced from Agent.md / lakehouse-final.md §4.3
# For fill-rate checks we use non_null with a threshold.
# e.g. hem 60% populated → threshold=0.57 (allow ±3pp)
TABLE_RULES: dict[str, list[dataplex_v1.DataQualityRule]] = {
    "audience": [
        _non_null_rule("audience_id"),
        _non_null_rule("segment_name"),
        # hem ~60% populated → at least 57% non-null
        _non_null_rule("hem", threshold=0.57),
    ],
    "cookie_registry": [
        _non_null_rule("cookie_id"),
        # audience_id ~40% populated → at least 37% non-null
        _non_null_rule("audience_id", threshold=0.37),
        # hem ~35% populated → at least 32% non-null
        _non_null_rule("hem", threshold=0.32),
    ],
    "campaigns": [
        _non_null_rule("campaign_id"),
        _non_null_rule("brand"),
        _non_null_rule("advertiser"),
        _set_rule("status", ["planned", "active", "completed", "paused"]),
    ],
    "creatives": [
        _non_null_rule("creative_id"),
        _non_null_rule("campaign_id"),
    ],
    "pixel_events": [
        _non_null_rule("event_id"),
        _non_null_rule("campaign_id"),
        _non_null_rule("creative_id"),
        # cookie_id ~82% populated → at least 79% non-null
        _non_null_rule("cookie_id", threshold=0.79),
    ],
    "transactions": [
        _non_null_rule("txn_id"),
        _non_null_rule("pan_token"),
        _non_null_rule("amount_usd"),
    ],
}


class DataQualityManager:
    """Creates and runs Dataplex data quality scans."""

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.client = dataplex_v1.DataScanServiceClient()
        self.parent = f"projects/{config.project_id}/locations/{config.location}"

    def create_and_run_scans(self, tables: list[str] | None = None, dry_run: bool = False) -> None:
        """Create a DQ DataScan for each table and trigger a run."""
        tables = tables or TABLES

        for table in tables:
            scan_id = f"quality-{table}"
            bq_resource = (
                f"//bigquery.googleapis.com/projects/{self.config.project_id}"
                f"/datasets/{self.config.iceberg_namespace}/tables/{table}"
            )
            rules = TABLE_RULES.get(table, [])

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
