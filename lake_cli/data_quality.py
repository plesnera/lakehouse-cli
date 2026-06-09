"""Dataplex Data Quality — create, sync, and run quality scans for marketing tables.

Defines DQ rules (NOT NULL, match-rate bounds, referential integrity) in YAML metadata files
and manages them via the DataScanService API with proper rule comparison and synchronization.

Ref: https://docs.cloud.google.com/dataplex/docs/data-quality-overview
"""

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import dataplex_v1
from lake_cli.config import Config, TABLES
from lake_cli.table_metadata import METADATA_DIR, load_all_table_metadata, RuleMeta


def _rule_from_meta(meta: RuleMeta) -> dataplex_v1.DataQualityRule:
    """Convert a RuleMeta to a dataplex DataQualityRule."""
    kwargs = dict(
        name=(f"{meta.rule_type}-{meta.column}").replace("_","-") ,
        column=meta.column,
        dimension=meta.dimension,
        threshold=meta.threshold,
    )
    if meta.rule_type == "non_null":
        kwargs["non_null_expectation"] = dataplex_v1.DataQualityRule.NonNullExpectation()
    elif meta.rule_type == "set":
        kwargs["set_expectation"] = dataplex_v1.DataQualityRule.SetExpectation(values=meta.values)
    elif meta.rule_type == "regex":
        kwargs["regex_expectation"] = dataplex_v1.DataQualityRule.RegexExpectation(regex=meta.pattern)
    elif meta.rule_type == "range":
        kwargs["range_expectation"] = dataplex_v1.DataQualityRule.RangeExpectation(
            min_value=meta.min_value,
            max_value=meta.max_value,
            strict_min_enabled=meta.strict_min_enabled,
            strict_max_enabled=meta.strict_max_enabled,
        )
    return dataplex_v1.DataQualityRule(**kwargs)


def _rule_to_dict(rule: dataplex_v1.DataQualityRule) -> dict:
    """Convert a DataQualityRule to a comparable dictionary."""
    result = {
        "name": rule.name,
        "column": rule.column,
        "dimension": rule.dimension,
        "threshold": rule.threshold,
    }

    # Use proto-level HasField to detect which expectation is set
    # (proto-plus wrappers are falsy even when explicitly set)
    pb = rule._pb
    if pb.HasField("non_null_expectation"):
        result["rule_type"] = "non_null"
    elif pb.HasField("set_expectation"):
        result["rule_type"] = "set"
        result["values"] = sorted(rule.set_expectation.values)
    elif pb.HasField("regex_expectation"):
        result["rule_type"] = "regex"
        result["pattern"] = rule.regex_expectation.regex
    elif pb.HasField("range_expectation"):
        result["rule_type"] = "range"
        result["min_value"] = rule.range_expectation.min_value
        result["max_value"] = rule.range_expectation.max_value
        result["strict_min"] = rule.range_expectation.strict_min_enabled
        result["strict_max"] = rule.range_expectation.strict_max_enabled

    return result


def _rules_equal(rule1: dataplex_v1.DataQualityRule, rule2: dataplex_v1.DataQualityRule) -> bool:
    """Compare two DataQualityRules for equality."""
    return _rule_to_dict(rule1) == _rule_to_dict(rule2)


def _compare_rule_lists(
    markdown_rules: list[dataplex_v1.DataQualityRule],
    active_rules: list[dataplex_v1.DataQualityRule]
) -> tuple[list[dataplex_v1.DataQualityRule], list[dataplex_v1.DataQualityRule], list[dataplex_v1.DataQualityRule]]:
    """Compare markdown rules with active rules.

    Returns:
        Tuple of (rules_to_add, rules_to_remove, rules_changed)
    """
    # Index rules by name+column for comparison
    markdown_by_key = {f"{r.name}:{r.column}": r for r in markdown_rules}
    active_by_key = {f"{r.name}:{r.column}": r for r in active_rules}

    rules_to_add = []
    rules_to_remove = []
    rules_changed = []

    # Find rules to add or that changed
    for key, md_rule in markdown_by_key.items():
        if key not in active_by_key:
            rules_to_add.append(md_rule)
        elif not _rules_equal(md_rule, active_by_key[key]):
            rules_changed.append(md_rule)

    # Find rules to remove
    for key, active_rule in active_by_key.items():
        if key not in markdown_by_key:
            rules_to_remove.append(active_rule)

    return rules_to_add, rules_to_remove, rules_changed


def load_dq_rules_from_md(metadata_dir: str = METADATA_DIR) -> dict[str, list[dataplex_v1.DataQualityRule]]:
    """Load DQ rules from markdown files, return {table_id: [DataQualityRule, ...]}."""
    all_meta = load_all_table_metadata(metadata_dir)
    rules: dict[str, list[dataplex_v1.DataQualityRule]] = {}
    for table_id, meta in all_meta.items():
        rules[table_id] = [_rule_from_meta(rule) for rule in meta.dq_rules]
    return rules


class DataQualityManager:
    """Creates, syncs, and runs Dataplex data quality scans."""

    def __init__(self, config: Config):
        self.config = config
        self.client = dataplex_v1.DataScanServiceClient()
        self.parent = f"projects/{config.project_id}/locations/{config.location}"
        self._ensure_results_dataset()

    def _ensure_results_dataset(self) -> None:
        """Create the dq-results dataset if it doesn't exist."""
        from google.cloud import bigquery
        bq = bigquery.Client(project=self.config.project_id)
        dataset_id = f"{self.config.iceberg_namespace}_dq_results"
        try:
            bq.get_dataset(dataset_id)
        except Exception:
            dataset = bigquery.Dataset(f"{self.config.project_id}.{dataset_id}")
            dataset.location = self.config.location
            bq.create_dataset(dataset)
            print(f"  ✅ Created BigQuery dataset: {dataset_id} in {self.config.location}")

    def _get_scan_id(self, table: str) -> str:
        """Generate deterministic scan ID for a table (no timestamp)."""
        return f"quality-{table.replace('_', '-')}"

    def _get_scan_name(self, table: str) -> str:
        """Get full scan resource name for a table."""
        scan_id = self._get_scan_id(table)
        return f"{self.parent}/dataScans/{scan_id}"

    def compare_rules(self, table: str) -> dict | None:
        """Compare markdown rules with active Dataplex rules for a table.

        Returns:
            Dict with comparison results, or None if scan doesn't exist.
        """
        scan_name = self._get_scan_name(table)

        try:
            scan = self.client.get_data_scan(
                request=dataplex_v1.GetDataScanRequest(name=scan_name)
            )
        except NotFound:
            return None

        # Load rules from markdown
        dq_rules = load_dq_rules_from_md()
        markdown_rules = dq_rules.get(table, [])

        # Get active rules from scan
        active_rules = list(scan.data_quality_spec.rules) if scan.data_quality_spec else []

        # Compare
        to_add, to_remove, changed = _compare_rule_lists(markdown_rules, active_rules)

        return {
            "scan_exists": True,
            "markdown_count": len(markdown_rules),
            "active_count": len(active_rules),
            "rules_to_add": to_add,
            "rules_to_remove": to_remove,
            "rules_changed": changed,
            "in_sync": len(to_add) == 0 and len(to_remove) == 0 and len(changed) == 0,
        }

    def sync_rules(self, table: str, dry_run: bool = False) -> tuple[str, bool]:
        """Synchronize markdown rules with Dataplex scan for a table.

        Creates scan if it doesn't exist, updates if rules differ.

        Returns:
            Tuple of (scan_name, was_updated)
        """
        scan_id = self._get_scan_id(table)
        scan_name = self._get_scan_name(table)

        # Load rules from markdown
        dq_rules = load_dq_rules_from_md()
        rules = dq_rules.get(table, [])

        if not rules:
            print(f"  ⚠️  No rules defined for {table} in markdown files")
            return scan_name, False

        # Build resource reference
        bq_resource = (
            f"//bigquery.googleapis.com/projects/{self.config.project_id}"
            f"/datasets/{self.config.iceberg_namespace}/tables/{table}"
        )

        # Check if scan exists
        try:
            existing_scan = self.client.get_data_scan(
                request=dataplex_v1.GetDataScanRequest(name=scan_name)
            )
        except NotFound:
            existing_scan = None

        if existing_scan is None:
            # Create new scan
            if dry_run:
                print(f"  [dry-run] Would create scan: {scan_id} ({len(rules)} rules)")
                return scan_name, False

            return self._create_scan(scan_id, scan_name, bq_resource, table, rules)
        else:
            # Scan exists - check if rules need updating
            comparison = self.compare_rules(table)

            if comparison and comparison["in_sync"]:
                print(f"  ℹ️  Scan {scan_id} rules are up to date ({len(rules)} rules)")
                return scan_name, False

            # Update existing scan
            if dry_run:
                print(f"  [dry-run] Would update scan: {scan_id}")
                if comparison:
                    print(f"    + Add {len(comparison['rules_to_add'])} rules")
                    print(f"    - Remove {len(comparison['rules_to_remove'])} rules")
                    print(f"    ~ Change {len(comparison['rules_changed'])} rules")
                return scan_name, False

            return self._update_scan(scan_name, table, rules, comparison)

    def _create_scan(
        self,
        scan_id: str,
        scan_name: str,
        bq_resource: str,
        table: str,
        rules: list[dataplex_v1.DataQualityRule]
    ) -> tuple[str, bool]:
        """Create a new data quality scan."""
        results_table = (
            f"//bigquery.googleapis.com/projects/{self.config.project_id}"
            f"/datasets/{self.config.iceberg_namespace}_dq_results/tables/{table}_dq"
        )
        bigquery_export = dataplex_v1.DataQualitySpec.PostScanActions.BigQueryExport(
            results_table=results_table,
        )
        post_scan_actions = dataplex_v1.DataQualitySpec.PostScanActions(
            bigquery_export=bigquery_export,
        )

        data_scan = dataplex_v1.DataScan(
            display_name=f"Quality — {table}",
            description=f"Data quality rules for the {table} marketing table.",
            data=dataplex_v1.DataSource(resource=bq_resource),
            data_quality_spec=dataplex_v1.DataQualitySpec(
                rules=rules,
                post_scan_actions=post_scan_actions,
                catalog_publishing_enabled=True,
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
            print(f"  ✅ Created scan: {scan_id} ({len(rules)} rules)")
            return result.name, True
        except AlreadyExists:
            print(f"  ℹ️  Scan already exists: {scan_id}")
            return scan_name, False
        except Exception as e:
            print(f"  ❌ Failed to create scan {scan_id}: {e}")
            raise

    def _update_scan(
        self,
        scan_name: str,
        table: str,
        rules: list[dataplex_v1.DataQualityRule],
        comparison: dict | None = None
    ) -> tuple[str, bool]:
        """Update an existing data quality scan with new rules."""
        # Build update mask for data_quality_spec
        update_mask = {"paths": ["data_quality_spec"]}

        # Create updated scan with new rules
        updated_scan = dataplex_v1.DataScan(
            name=scan_name,
            data_quality_spec=dataplex_v1.DataQualitySpec(rules=rules),
        )

        try:
            operation = self.client.update_data_scan(
                request=dataplex_v1.UpdateDataScanRequest(
                    data_scan=updated_scan,
                    update_mask=update_mask,
                )
            )
            result = operation.result()

            if comparison:
                print(f"  ✅ Updated scan: {scan_name.split('/')[-1]}")
                print(f"     + Added {len(comparison['rules_to_add'])} rules")
                print(f"     - Removed {len(comparison['rules_to_remove'])} rules")
                print(f"     ~ Changed {len(comparison['rules_changed'])} rules")
                print(f"     = Total: {len(rules)} rules")
            else:
                print(f"  ✅ Updated scan: {scan_name.split('/')[-1]} ({len(rules)} rules)")

            return result.name, True
        except Exception as e:
            print(f"  ❌ Failed to update scan {scan_name}: {e}")
            raise

    def create_and_run_scans(self, tables: list[str] | None = None, dry_run: bool = False) -> None:
        """Create/update DQ scans and trigger runs for each table."""
        tables = tables or TABLES

        print(f"Syncing data quality scans for {len(tables)} table(s)...")

        for table in tables:
            scan_name, was_updated = self.sync_rules(table, dry_run=dry_run)

            if not dry_run and scan_name:
                self._run_scan(scan_name)

    def check_rules(self, tables: list[str] | None = None) -> dict[str, dict]:
        """Check if markdown rules match active Dataplex rules.

        Returns dict mapping table names to comparison results.
        """
        tables = tables or TABLES
        results = {}

        print(f"Checking data quality rules for {len(tables)} table(s)...")
        print()

        for table in tables:
            comparison = self.compare_rules(table)

            if comparison is None:
                print(f"📋 {table}:")
                print(f"   Status: Scan does not exist")
                print()
                results[table] = {"scan_exists": False}
                continue

            print(f"📋 {table}:")
            print(f"   Markdown rules: {comparison['markdown_count']}")
            print(f"   Active rules: {comparison['active_count']}")

            if comparison["in_sync"]:
                print(f"   Status: ✅ In sync")
            else:
                print(f"   Status: ⚠️  Out of sync")
                if comparison["rules_to_add"]:
                    print(f"   + Add: {len(comparison['rules_to_add'])} rule(s)")
                    for r in comparison["rules_to_add"]:
                        print(f"       - {r.name} on {r.column}")
                if comparison["rules_to_remove"]:
                    print(f"   - Remove: {len(comparison['rules_to_remove'])} rule(s)")
                    for r in comparison["rules_to_remove"]:
                        print(f"       - {r.name} on {r.column}")
                if comparison["rules_changed"]:
                    print(f"   ~ Change: {len(comparison['rules_changed'])} rule(s)")
                    for r in comparison["rules_changed"]:
                        print(f"       - {r.name} on {r.column}")
            print()

            results[table] = comparison

        return results

    def sync_only(self, tables: list[str] | None = None, dry_run: bool = False) -> None:
        """Sync rules without running scans."""
        tables = tables or TABLES

        print(f"Synchronizing data quality rules for {len(tables)} table(s)...")
        print()

        for table in tables:
            self.sync_rules(table, dry_run=dry_run)

    def run_scans(self, tables: list[str] | None = None) -> None:
        """Run existing data quality scans without syncing rules."""
        tables = tables or TABLES

        print(f"Running data quality scans for {len(tables)} table(s)...")

        for table in tables:
            scan_name = self._get_scan_name(table)
            self._run_scan(scan_name)

    def _run_scan(self, scan_name: str) -> None:
        """Trigger a run for an existing scan."""
        try:
            self.client.run_data_scan(
                request=dataplex_v1.RunDataScanRequest(name=scan_name)
            )
            print(f"  🚀 Triggered run for: {scan_name.split('/')[-1]}")
        except Exception as e:
            print(f"  ⚠️  Failed to run {scan_name.split('/')[-1]}: {e}")

    def get_results(self, tables: list[str] | None = None) -> None:
        """Print the latest quality scan results."""
        tables = tables or TABLES

        for table in tables:
            scan_name = self._get_scan_name(table)
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
