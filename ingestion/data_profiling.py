"""Dataplex Data Profiling — create and run profile scans for marketing tables.

Uses the DataScanService API to trigger statistical profiling scans that
identify distributions, null counts, and anomalies in the synthetic data.

Ref: https://docs.cloud.google.com/dataplex/docs/data-profiling-overview
"""

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import dataplex_v1
import time

from ingestion.config import Config, TABLES


class DataProfilingManager:
    """Creates and runs Dataplex data profile scans."""

    def __init__(self, config: Config):
        self.config = config
        self.client = dataplex_v1.DataScanServiceClient()
        self.parent = f"projects/{config.project_id}/locations/{config.location}"
        self._ensure_results_dataset()

    def _ensure_results_dataset(self) -> None:
        """Create the profile-results dataset if it doesn't exist."""
        from google.cloud import bigquery
        bq = bigquery.Client(project=self.config.project_id)
        dataset_id = f"{self.config.iceberg_namespace}_profile_results"
        try:
            bq.get_dataset(dataset_id)
        except Exception:
            dataset = bigquery.Dataset(f"{self.config.project_id}.{dataset_id}")
            dataset.location = self.config.location
            bq.create_dataset(dataset)
            print(f"  ✅ Created BigQuery dataset: {dataset_id} in {self.config.location}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_and_run_scans(self, tables: list[str] | None = None, dry_run: bool = False) -> None:
        """Create a data-profile DataScan for each table and trigger a run."""
        tables = tables or TABLES

        for table in tables:
            scan_id = f"profile-{table.replace('_', '-')}-{int(time.time())}"
            bq_resource = (
                f"//bigquery.googleapis.com/projects/{self.config.project_id}"
                f"/datasets/{self.config.iceberg_namespace}/tables/{table}"
            )

            if dry_run:
                print(f"  [dry-run] Would create profile scan: {scan_id} → {bq_resource}")
                continue

            # 1. Create the DataScan (idempotent)
            scan_name = self._ensure_scan(scan_id, bq_resource, table)

            # 2. Run it
            self._run_scan(scan_name)

    def get_results(self, tables: list[str] | None = None) -> None:
        """Print the latest profile scan results for each table."""
        tables = tables or TABLES

        for table in tables:
            scan_name = f"{self.parent}/dataScans/profile-{table}"
            try:
                scan = self.client.get_data_scan(
                    request=dataplex_v1.GetDataScanRequest(
                        name=scan_name,
                        view=dataplex_v1.GetDataScanRequest.DataScanView.FULL,
                    )
                )
                result = scan.data_profile_result
                if result and result.row_count:
                    print(f"  ✅ {table}: {result.row_count} rows profiled, "
                          f"{len(result.profile.fields)} columns")
                else:
                    print(f"  ⏳ {table}: scan exists but no results yet")
            except NotFound:
                print(f"  ❌ {table}: no profile scan found")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_scan(self, scan_id: str, bq_resource: str, table: str) -> str:
        """Create a profile DataScan if it doesn't already exist."""
        scan_name = f"{self.parent}/dataScans/{scan_id}"

        try:
            self.client.get_data_scan(
                request=dataplex_v1.GetDataScanRequest(name=scan_name)
            )
            print(f"  ℹ️  Profile scan exists: {scan_id}")
            return scan_name
        except NotFound:
            pass

        results_table = (
            f"//bigquery.googleapis.com/projects/{self.config.project_id}"
            f"/datasets/{self.config.iceberg_namespace}_profile_results/tables/{table}_profile"
        )
        bigquery_export = dataplex_v1.DataProfileSpec.PostScanActions.BigQueryExport(
            results_table=results_table,
        )
        post_scan_actions = dataplex_v1.DataProfileSpec.PostScanActions(
            bigquery_export=bigquery_export,
        )

        data_scan = dataplex_v1.DataScan(
            display_name=f"Profile — {table}",
            description=f"Automated data profile scan for the {table} marketing table.",
            data=dataplex_v1.DataSource(resource=bq_resource),
            data_profile_spec=dataplex_v1.DataProfileSpec(
                post_scan_actions=post_scan_actions,
            ),
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
            print(f"  ✅ Created profile scan: {scan_id}")
            return result.name
        except AlreadyExists:
            print(f"  ℹ️  Profile scan already exists: {scan_id}")
            return scan_name

    def _run_scan(self, scan_name: str) -> None:
        """Trigger a run of the given DataScan."""
        try:
            self.client.run_data_scan(
                request=dataplex_v1.RunDataScanRequest(name=scan_name)
            )
            print(f"  🚀 Triggered run for: {scan_name.split('/')[-1]}")
        except Exception as e:
            print(f"  ⚠️  Failed to run {scan_name.split('/')[-1]}: {e}")
