#!/usr/bin/env python3
"""
Pure Metadata Enrichment System

This module implements a clean separation between two approaches to metadata enrichment:
1. Manual markdown-based descriptions (human expertise)
2. Google Table Insights (automated statistical analysis)

The system supports two distinct modes:
- Google Insights Mode: Uses ONLY automated Google Table Insights
- Markdown Mode: Uses ONLY manual descriptions from markdown files

These approaches are NOT combined - ensuring clean separation and compliance with
Google Dataplex metadata enrichment standards.
"""

import time
import os
import json
from typing import Dict, List, Optional, Tuple
from google.cloud import bigquery
from google.cloud import dataplex_v1
from google.api_core.exceptions import NotFound, GoogleAPICallError
from lake_cli.config import Config



class HybridMetadataEnricher:
    """
    Enriches BigQuery tables with pure metadata using either manual descriptions OR Google Table Insights.

    This class supports two distinct approaches to metadata enrichment:
    - Google Insights Mode: Uses ONLY automated Google Table Insights
    - Markdown Mode: Uses ONLY manual descriptions from markdown files

    These approaches are NOT combined - ensuring clean separation and compliance with
    Google Dataplex metadata enrichment standards.
    https://docs.cloud.google.com/bigquery/docs/generate-table-insights

    """

    def __init__(self, config: Config):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset_id = f"{config.project_id}.{config.iceberg_namespace}"
        self.metadata_dir = "metadata"

        # Ensure metadata directory exists
        os.makedirs(self.metadata_dir, exist_ok=True)

    def _generate_descriptions_core(self, table_names: List[str], metadata_files: Optional[List[str]] = None,
                                   use_google_insights: bool = True, dry_run: bool = False):
        """
        Core method for generating descriptions with flexible behavior.

        Args:
            table_names: List of table names to process
            metadata_files: Optional list of metadata file paths
            use_google_insights: Whether to combine with Google insights
            dry_run: If True, preview changes without applying them
        """
        if dry_run:
            mode_desc = "previewing" if dry_run else "applying"
            insights_desc = "with Google insights" if use_google_insights else "manual only"
            print(f"👁️  {mode_desc} metadata enrichment for {len(table_names)} tables ({insights_desc})...")
        else:
            print(f"Starting metadata enrichment for {len(table_names)} tables...")

        for table_name, metadata_file in zip(table_names, metadata_files or [None]*len(table_names)):
            # Support both full format (project.dataset.table) and short format (table)
            if '.' in table_name and table_name.count('.') >= 2:
                table_ref = table_name
            else:
                table_ref = f"{self.dataset_id}.{table_name}"

            print(f"Processing table: {table_ref}" +
                  (f" with metadata: {metadata_file}" if metadata_file else ""))

            try:
                table_obj = self.client.get_table(table_ref)

                # Generate descriptions based on mode
                if use_google_insights:
                    # Use pure Google Insights approach
                    table_description, column_descriptions = self._generate_table_insights(table_ref)
                else:
                    # Use pure manual markdown approach
                    table_description, column_descriptions = self._load_manual_descriptions(table_ref, metadata_file)

                if dry_run:
                    self._preview_metadata_changes(table_ref, table_description, column_descriptions)
                else:
                    self._update_table_metadata(table_ref, table_description, column_descriptions)
                    print(f"✅ Enriched metadata for: {table_ref}")

            except NotFound:
                print(f"⚠️  Table not found: {table_ref}")
            except Exception as e:
                print(f"⚠️  Failed to enrich {table_ref}: {e}")

        if dry_run:
            print("\n👁️  Dry-run complete. No changes were applied.")
        else:
            print("Metadata enrichment complete!")

    def generate_descriptions(self, timeout: int = 300, dry_run: bool = False):
        """Generate descriptions for all tables in the dataset using manual YAML files."""
        tables = [table.table_id for table in self.client.list_tables(self.dataset_id)]
        yaml_mapping = self._build_table_id_mapping()
        metadata_files = [yaml_mapping.get(t) for t in tables]
        self._generate_descriptions_core(tables, metadata_files=metadata_files, use_google_insights=False, dry_run=dry_run)

    def generate_descriptions_for_tables(self, table_names: List[str], timeout: int = 300, dry_run: bool = False):
        """Generate descriptions for specific tables using default manual YAML files."""
        yaml_mapping = self._build_table_id_mapping()
        metadata_files = [yaml_mapping.get(t) for t in table_names]
        self._generate_descriptions_core(table_names, metadata_files=metadata_files, use_google_insights=False, dry_run=dry_run)

    def generate_descriptions_for_tables_with_google_insights(self, table_names: List[str], timeout: int = 300, dry_run: bool = False):
        """Generate descriptions using ONLY Google-style automated insights (no manual files)."""
        self._generate_descriptions_core(table_names, use_google_insights=True, dry_run=dry_run)

    def generate_descriptions_with_google_insights(self, timeout: int = 300, dry_run: bool = False):
        """Generate descriptions for ALL tables using ONLY Google-style automated insights."""
        tables = [table.table_id for table in self.client.list_tables(self.dataset_id)]
        self._generate_descriptions_core(tables, use_google_insights=True, dry_run=dry_run)

    def generate_descriptions_for_tables_with_files(self, table_names: List[str], metadata_files: List[str], timeout: int = 300, dry_run: bool = False, use_google_insights: bool = True):
        """
        Generate hybrid descriptions for specific tables using explicit metadata files.

        Args:
            table_names: List of table names in format project.dataset.table or just table_name
            metadata_files: List of metadata file paths to use
            timeout: Maximum time to wait for operations (seconds)
            dry_run: If True, preview changes without applying them
            use_google_insights: If True, combine with Google insights (hybrid mode)
        """
        if dry_run:
            print(f"👁️  Previewing manual metadata enrichment for {len(table_names)} tables (dry-run mode)...")
        else:
            print(f"Starting manual metadata enrichment for {len(table_names)} tables...")

        for table_name, metadata_file in zip(table_names, metadata_files):
            # Support both full format (project.dataset.table) and short format (table)
            if '.' in table_name and table_name.count('.') >= 2:
                # Full format: project.dataset.table
                table_ref = table_name

            else:
                # Short format: table_name only
                table_ref = f"{self.dataset_id}.{table_name}"

            print(f"Processing table: {table_ref} with metadata: {metadata_file}")

            try:
                # Get current table info
                table_obj = self.client.get_table(table_ref)

                # Generate descriptions based on mode
                if use_google_insights:
                    # Use pure Google Insights approach
                    table_description, column_descriptions = self._generate_table_insights(table_ref)
                else:
                    # Use pure manual markdown approach
                    table_description, column_descriptions = self._load_manual_descriptions(table_ref, metadata_file)

                if dry_run:
                    # Preview changes
                    self._preview_metadata_changes(table_ref, table_description, column_descriptions)
                else:
                    # Update table with descriptions
                    self._update_table_metadata(
                        table_ref,
                        table_description,
                        column_descriptions
                    )
                    print(f"✅ Enriched metadata for: {table_ref}")

            except NotFound:
                print(f"⚠️  Table not found: {table_ref}")
            except Exception as e:
                print(f"⚠️  Failed to enrich {table_ref}: {e}")

        if dry_run:
            print("\n👁️  Dry-run complete. No changes were applied.")
        else:
            print("Manual metadata enrichment complete!")



    def _load_manual_descriptions(self, table_ref: str, metadata_file: str = None) -> Tuple[str, Dict[str, str]]:
        """
        Load manual descriptions from YAML metadata file.

        Args:
            table_ref: Full table reference (project.dataset.table) or just table name
            metadata_file: Optional explicit file path (overrides default)

        Returns:
            Tuple of (table_description, column_descriptions_dict)
        """
        import yaml

        # Extract table name from full reference
        if '.' in table_ref and table_ref.count('.') >= 2:
            # Full format: project.dataset.table -> extract table name
            table_id = table_ref.split('.')[-1]

        else:
            # Short format: just table name
            table_id = table_ref


        if metadata_file:
            # Use explicit file path
            metadata_file_path = metadata_file
            if not os.path.isabs(metadata_file):
                # If relative path, try both current directory and metadata directory
                metadata_file_path = os.path.join(os.getcwd(), metadata_file)
                if not os.path.exists(metadata_file_path):
                    # Try in metadata directory
                    metadata_file_path = os.path.join(self.metadata_dir, metadata_file)


        else:
            # Use default location
            metadata_file_path = os.path.join(self.metadata_dir, f"{table_id}.yaml")

        # Default empty descriptions
        table_description = ""
        column_descriptions = {}

        if os.path.exists(metadata_file_path):
            try:
                with open(metadata_file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)

                table_description = data.get("description", "").strip()

                # Extract column descriptions from structured YAML
                for col_data in (data.get("columns") or []):
                    col_name = col_data.get("name", "")
                    col_desc = col_data.get("description", "")
                    if col_name:
                        column_descriptions[col_name] = col_desc

            except Exception as e:
                print(f"⚠️  Failed to parse manual descriptions for {table_id}: {e}")
        else:
            print(f"ℹ️  No manual descriptions found for {table_id}. Using insights only.")

        return table_description, column_descriptions

    def _generate_table_insights(self, table_ref: str) -> Tuple[str, Dict[str, str]]:
        """
        Fire a one-time DATA_DOCUMENTATION scan and immediately publish the results
        to BigQuery. The scan runs asynchronously on Google's side — we do not wait
        for completion.

        Implements Option B (One-time scan) from the Dataplex REST documentation:
        https://cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations.dataScans

        Steps:
        1. Create and trigger a one-time DATA_DOCUMENTATION scan (single API call)
        2. Publish results to BigQuery by setting the required labels on the table.
           Dataplex will populate the published results once the scan completes.

        Args:
            table_ref: Full table reference (project.dataset.table)

        Returns:
            Empty tuple — results are published directly to BigQuery by Dataplex.
        """
        import requests
        import google.auth
        from google.auth.transport.requests import Request

        try:
            table_obj = self.client.get_table(table_ref)

            project_id = self.dataset_id.split('.')[0]
            dataset_name = self.dataset_id.split('.')[1]
            table_name = table_obj.table_id

            # Get dataset location
            dataset_ref = bigquery.DatasetReference(project=project_id, dataset_id=dataset_name)
            dataset_obj = self.client.get_dataset(dataset_ref)
            location = dataset_obj.location

            # One-time scan ID (must be unique per location)
            scan_id = f"insights-{table_name.replace('_', '-')}-{int(time.time())}"
            # TTL: auto-delete scan resource after 1 hour
            ttl_seconds = 3600

            payload = {
                "data": {
                    "resource": f"//bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_name}/tables/{table_name}"
                },
                "type": "DATA_DOCUMENTATION",
                "dataDocumentationSpec": {
                    "generationScopes": "ALL",
                    "catalogPublishingEnabled": True
                },
                "executionSpec": {
                    "trigger": {
                        "one_time": {
                            "ttl_after_scan_completion": {"seconds": ttl_seconds}
                        }
                    }
                }
            }

            credentials, _ = google.auth.default()
            auth_req = Request()
            credentials.refresh(auth_req)
            access_token = credentials.token

            url = (
                f"https://dataplex.googleapis.com/v1/projects/{project_id}"
                f"/locations/{location}/dataScans?dataScanId={scan_id}"
            )
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            print(f"📡 Creating one-time DataScan: {scan_id}")
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                err = response.json().get('error', {}).get('message', response.text)
                print(f"❌ DataScan creation failed ({response.status_code}): {err}")
                return "", {}

            scan_data = response.json()
            datascan_name = scan_data.get(
                'name',
                f"projects/{project_id}/locations/{location}/dataScans/{scan_id}"
            )
            print(f"✅ DataScan created (runs asynchronously): {datascan_name}")

            # Publish results to BigQuery immediately — Dataplex will populate
            # the published table once the scan finishes.
            self._publish_datascan_results(table_ref, scan_id, project_id, location)

            return "", {}

        except NotFound:
            print(f"⚠️  Table not found for insights generation: {table_ref}")
            return "", {}
        except GoogleAPICallError as e:
            print(f"⚠️  Google API error generating insights for {table_ref}: {e}")
            return "", {}
        except Exception as e:
            print(f"⚠️  Failed to generate insights for {table_ref}: {e}")
            return "", {}

    def _publish_datascan_results(
        self,
        table_ref: str,
        scan_id: str,
        project_id: str,
        location: str,
    ) -> None:
        """
        Publish data documentation scan results to BigQuery by attaching labels.

        Per the REST docs, setting these three labels on the table makes Dataplex
        publish the scan results automatically:
          - dataplex-data-documentation-published-scan: <scan_id>
          - dataplex-data-documentation-published-project: <project_id>
          - dataplex-data-documentation-published-location: <location>
        """
        try:
            table = self.client.get_table(table_ref)
            labels = dict(table.labels) if table.labels else {}

            labels['dataplex-data-documentation-published-scan'] = scan_id
            labels['dataplex-data-documentation-published-project'] = project_id
            labels['dataplex-data-documentation-published-location'] = location

            table.labels = labels
            self.client.update_table(table, ['labels'])
            print(f"✅ Published scan results to BigQuery table with labels:")
            print(f"   dataplex-data-documentation-published-scan: {scan_id}")
            print(f"   dataplex-data-documentation-published-project: {project_id}")
            print(f"   dataplex-data-documentation-published-location: {location}")
        except Exception as e:
            print(f"⚠️  Failed to publish results to BigQuery: {e}")


    def _preview_metadata_changes(self, table_ref: str, table_description: str, column_descriptions: dict):
        """
        Preview metadata changes without applying them.

        Args:
            table_ref: Full table reference
            table_description: Description for the table
            column_descriptions: Dictionary of column descriptions
        """
        try:
            table = self.client.get_table(table_ref)

            print(f"\n📋 Preview for table: {table_ref}")
            print(f"\n📝 Table Description:")
            print(f"   {table_description}")

            print(f"\n📊 Column Descriptions:")
            for field in table.schema:
                current_desc = field.description or "(no description)"
                new_desc = column_descriptions.get(field.name, "(no description)")

                if new_desc != current_desc:
                    print(f"   • {field.name}: {new_desc}")
                    if current_desc != "(no description)":
                        print(f"     (was: {current_desc})")
                else:
                    print(f"   • {field.name}: {new_desc} (unchanged)")

        except Exception as e:
            print(f"  ❌ Failed to preview metadata for {table_ref}: {e}")

    def _update_table_metadata(self, table_ref: str, table_description: str, column_descriptions: dict):
        """
        Update table and column descriptions in BigQuery.

        Args:
            table_ref: Full table reference
            table_description: Description for the table
            column_descriptions: Dictionary of column descriptions
        """
        try:
            table = self.client.get_table(table_ref)

            # Update table description
            table.description = table_description

            # Update column descriptions
            updated_schema = []
            for field in table.schema:
                field_description = column_descriptions.get(field.name, field.description)
                updated_field = bigquery.SchemaField(
                    field.name,
                    field.field_type,
                    mode=field.mode,
                    description=field_description,
                    fields=field.fields
                )
                updated_schema.append(updated_field)

            table.schema = updated_schema

            # Apply updates
            self.client.update_table(table, ["description", "schema"])

        except Exception as e:
            print(f"  ❌ Failed to update metadata for {table_ref}: {e}")

    def _build_table_id_mapping(self) -> Dict[str, str]:
        """
        Scan all YAML files in the metadata directory and build a mapping
        of table_id to the file path that already tracks it.

        Returns:
            Dict mapping table_id -> existing file path
        """
        import yaml

        mapping: Dict[str, str] = {}
        if not os.path.isdir(self.metadata_dir):
            return mapping

        for filename in os.listdir(self.metadata_dir):
            if not filename.endswith(('.yaml', '.yml')):
                continue
            filepath = os.path.join(self.metadata_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict) and data.get('table_id'):
                    mapping[data['table_id']] = filepath
            except Exception:
                # Skip files that can't be parsed
                continue
        return mapping

    def create_template_metadata(self, table_id: str, existing_table_ids: Optional[Dict[str, str]] = None):
        """
        Create a template YAML metadata file for manual descriptions.

        Args:
            table_id: Table name
            existing_table_ids: Optional pre-built mapping of table_id -> file path.
                                If None, a fresh mapping is built by scanning the metadata dir.
        """
        if existing_table_ids is None:
            existing_table_ids = self._build_table_id_mapping()

        # Check if this table_id is already tracked by an existing YAML file
        if table_id in existing_table_ids:
            print(f"⚠️  Metadata file already exists for table '{table_id}': {existing_table_ids[table_id]}")
            return

        metadata_file = os.path.join(self.metadata_dir, f"{table_id}.yaml")

        if os.path.exists(metadata_file):
            print(f"⚠️  Metadata file already exists: {metadata_file}")
            return

        try:
            table_ref = f"{self.dataset_id}.{table_id}"
            table_obj = self.client.get_table(table_ref)

            with open(metadata_file, 'w', encoding='utf-8') as f:
                f.write(f"table_id: {table_id}\n")
                f.write(f"display_name: {table_id}\n")
                f.write(f"description: >\n")
                f.write(f"  Describe what this table contains and its purpose.\n\n")
                f.write(f"tags:\n")
                f.write(f"  business_owner: Marketing Data Products\n")
                f.write(f"  data_domain: audience\n")
                f.write(f"  pii_class: none\n")
                f.write(f"  refresh_cadence: daily\n")
                f.write(f"  row_count_approx: 0\n")
                f.write(f"  marketing_usecases: audience_discovery\n\n")
                f.write(f"columns:\n")

                for field in table_obj.schema:
                    column_name = field.name
                    column_type = field.field_type
                    f.write(f"  - name: {column_name}\n")
                    f.write(f"    description: Describe what this column represents.\n")

                f.write(f"\ndata_quality_rules:\n")
                f.write(f"  - column: {table_obj.schema[0].name if table_obj.schema else 'id'}\n")
                f.write(f"    rule_type: non_null\n")

            print(f"✅ Created template metadata file: {metadata_file}")
            print(f"   Edit this file to provide manual descriptions, then run enrichment.")

        except Exception as e:
            print(f"❌ Failed to create template for {table_id}: {e}")

    def create_all_templates(self):
        """
        Create template YAML metadata files for all tables.

        Scans existing YAML files in the metadata directory first to build a
        mapping of table_id -> file path, so tables already tracked under a
        differently-named file (e.g. audience_profile.yaml for table_id 'audience')
        are not duplicated.
        """
        print("Creating metadata templates for all tables...")

        existing_table_ids = self._build_table_id_mapping()

        tables = self.client.list_tables(self.dataset_id)

        for table in tables:
            self.create_template_metadata(table.table_id, existing_table_ids=existing_table_ids)

        print("Template creation complete!")


if __name__ == "__main__":
    config = Config()
    enricher = HybridMetadataEnricher(config)
    enricher.generate_descriptions()
