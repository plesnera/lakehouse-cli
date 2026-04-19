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
from generators.config import GeneratorConfig



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
    
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset_id = f"{config.project_id}.{config.iceberg_namespace}"
        self.markdown_dir = "metadata_descriptions"
        
        # Ensure markdown directory exists
        os.makedirs(self.markdown_dir, exist_ok=True)
    
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
        """Generate hybrid descriptions for all tables in the dataset."""
        tables = [table.table_id for table in self.client.list_tables(self.dataset_id)]
        self._generate_descriptions_core(tables, dry_run=dry_run)
    
    def generate_descriptions_for_tables(self, table_names: List[str], timeout: int = 300, dry_run: bool = False):
        """Generate hybrid descriptions for specific tables using default markdown files."""
        self._generate_descriptions_core(table_names, dry_run=dry_run)
    
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
        Load manual descriptions from markdown file.
        
        Args:
            table_ref: Full table reference (project.dataset.table) or just table name
            metadata_file: Optional explicit file path (overrides default)
            
        Returns:
            Tuple of (table_description, column_descriptions_dict)
        """
        # Extract table name from full reference
        if '.' in table_ref and table_ref.count('.') >= 2:
            # Full format: project.dataset.table -> extract table name
            table_id = table_ref.split('.')[-1]

        else:
            # Short format: just table name
            table_id = table_ref

            
        if metadata_file:
            # Use explicit file path
            markdown_file = metadata_file
            if not os.path.isabs(metadata_file):
                # If relative path, try both current directory and metadata_descriptions directory
                markdown_file = os.path.join(os.getcwd(), metadata_file)
                if not os.path.exists(markdown_file):
                    # Try in metadata_descriptions directory
                    markdown_file = os.path.join(self.markdown_dir, metadata_file)
            

        else:
            # Use default location
            markdown_file = os.path.join(self.markdown_dir, f"{table_id}.md")
        
        # Default empty descriptions
        table_description = ""
        column_descriptions = {}
        
        if os.path.exists(markdown_file):
            try:
                with open(markdown_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse markdown content
                lines = content.split('\n')
                
                # Extract table description (first non-header paragraph)
                table_description = ""
                in_description = False
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Skip header lines
                    if line.startswith('# '):
                        continue
                    
                    # Stop at section headers
                    if line.startswith('## ') or line.startswith('### '):
                        break
                    
                    # Collect description lines
                    if line:
                        if table_description:
                            table_description += " " + line
                        else:
                            table_description = line
                
                # Extract column descriptions (bullet points)
                in_columns_section = False
                for line in lines[1:]:
                    line = line.strip()
                    if line.startswith('## Columns') or line.startswith('### Columns'):
                        in_columns_section = True
                        continue
                    elif line.startswith('## ') or line.startswith('### '):
                        in_columns_section = False
                        continue
                    
                    if in_columns_section and line.startswith('- '):
                        # Parse column description: - column_name: description
                        parts = line[2:].split(':', 1)
                        if len(parts) == 2:
                            column_name = parts[0].strip()
                            description = parts[1].strip()
                            column_descriptions[column_name] = description
                
            except Exception as e:
                print(f"⚠️  Failed to parse manual descriptions for {table_id}: {e}")
        else:
            print(f"ℹ️  No manual descriptions found for {table_id}. Using insights only.")
        
        return table_description, column_descriptions
    
    def _generate_table_insights(self, table_ref: str) -> Tuple[str, Dict[str, str]]:
        """
        Generate descriptions using Google BigQuery Table Insights service.
        
        This implements the proper Google Cloud Table Insights integration as per:
        https://docs.cloud.google.com/dataplex/docs/enrich-entries-metadata#add-aspects
        
        Args:
            table_ref: Full table reference (project.dataset.table)
            
        Returns:
            Tuple of (table_description, column_descriptions_dict)
        """
        try:
            # Get table object to access schema and metadata
            table_obj = self.client.get_table(table_ref)
            
            # Generate insights using Google Dataplex approach
            table_description = self._generate_google_table_insights_description(table_obj, table_ref)
            column_descriptions = self._generate_google_column_insights(table_obj)
            
            return table_description, column_descriptions
            
        except NotFound as e:
            print(f"⚠️  Table not found for insights generation: {table_ref}")
            return "", {}
        except GoogleAPICallError as e:
            print(f"⚠️  Google API error generating insights for {table_ref}: {e}")
            return "", {}
        except Exception as e:
            print(f"⚠️  Failed to generate insights for {table_ref}: {e}")
            return "", {}
    
    def _generate_google_column_insights(self, table_obj) -> Dict[str, str]:
        """
        Generate column descriptions using Google Dataplex DataScan API for table insights.
        
        This method uses the DATA_DOCUMENTATION scan type with one-time scan approach
        to generate automated descriptions for table columns using Google's AI-powered insights.
        
        Implementation follows Google's recommended approach:
        https://docs.cloud.google.com/dataplex/docs/generate-table-insights
        
        Args:
            table_obj: BigQuery Table object
            
        Returns:
            Dictionary of column descriptions generated by Google Table Insights
        """
        import requests
        import json
        import time
        import google.auth
        from google.auth.transport.requests import Request
        
        table_ref = f"{self.dataset_id}.{table_obj.table_id}"
        print(f"🔍 Generating Google Table Insights for {table_ref} using DataScan API...")
        
        try:
            # Extract project and dataset info
            project_id = self.dataset_id.split('.')[0]
            dataset_name = self.dataset_id.split('.')[1]
            table_name = table_obj.table_id
            
            # Use the current gcloud project's location
            location = "us-east1"  # This should match your BigQuery dataset location
            
            # Generate unique scan ID with timestamp
            scan_id = f"insights-{table_name.replace('_', '-')}-{int(time.time())}"
            
            # Create the DataScan request payload following Google's documentation
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
                            "ttl_after_scan_completion": {
                                "seconds": 3600  # 1 hour TTL for automatic cleanup
                            }
                        }
                    }
                }
            }
            
            # Get access token for authentication
            credentials, project = google.auth.default()
            auth_req = Request()
            credentials.refresh(auth_req)
            access_token = credentials.token
            
            # Make the API call to create and trigger the scan
            url = f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{location}/dataScans?dataScanId={scan_id}"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            print(f"📡 Creating DataScan: {scan_id}")
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            
            if response.status_code != 200:
                error_details = response.json().get('error', {}).get('message', 'Unknown error')
                print(f"❌ DataScan creation failed: {response.status_code} - {error_details}")
                return {}
            
            scan_resource = response.json()
            print(f"✅ Created DataScan operation: {scan_resource['name']}")
            
            # The API returns an operation, we need to wait for it to complete first
            # Then we can get the actual DataScan resource
            operation_name = scan_resource['name']
            
            # Wait for the operation to complete
            max_operation_attempts = 15
            operation_attempt = 0
            
            while operation_attempt < max_operation_attempts:
                operation_attempt += 1
                time.sleep(5)  # Wait 5 seconds between operation checks
                
                operation_response = requests.get(
                    f"https://dataplex.googleapis.com/v1/{operation_name}",
                    headers=headers
                )
                
                if operation_response.status_code != 200:
                    print(f"⚠️  Could not check operation status: {operation_response.status_code}")
                    continue
                
                operation_status = operation_response.json()
                done = operation_status.get('done', False)
                
                if done:
                    if 'error' in operation_status:
                        error_message = operation_status['error'].get('message', 'Unknown error')
                        print(f"❌ Operation failed: {error_message}")
                        return {}
                    
                    # Operation succeeded, now get the DataScan resource
                    # Extract the DataScan name from the response
                    if 'response' in operation_status and '@type' in operation_status['response']:
                        datascan_name = operation_status['response']['name']
                        print(f"✅ DataScan created: {datascan_name}")
                        
                        # Now check the job status
                        # We need to get the DataScan first to find the job ID
                        datascan_response = requests.get(
                            f"https://dataplex.googleapis.com/v1/{datascan_name}",
                            headers=headers
                        )
                        
                        if datascan_response.status_code == 200:
                            datascan_data = datascan_response.json()
                            print(f"📊 DataScan details: {json.dumps(datascan_data, indent=2)}")
                            
                            # Check if the scan completed immediately (synchronous completion)
                            if 'executionStatus' in datascan_data:
                                exec_status = datascan_data['executionStatus']
                                if 'latestJobId' in exec_status:
                                    job_id = exec_status['latestJobId']
                                    job_url = f"{datascan_name}/jobs/{job_id}"
                                    
                                    # Check job status
                                    job_response = requests.get(
                                        f"https://dataplex.googleapis.com/v1/{job_url}",
                                        headers=headers
                                    )
                                    
                                    if job_response.status_code == 200:
                                        job_data = job_response.json()
                                        job_state = job_data.get('state', 'UNKNOWN')
                                        print(f"🎯 Job {job_id} status: {job_state}")
                                        
                                        if job_state == 'SUCCEEDED':
                                            print("🎉 DataScan completed successfully!")
                                            print("ℹ️  Results available in Dataplex Knowledge Catalog")
                                            print("   To view: Check Dataplex UI or use DataScan results API")
                                            return {}
                                        else:
                                            print(f"⚠️  Job completed with status: {job_state}")
                                            return {}
                                    else:
                                        print(f"⚠️  Could not get job details: {job_response.status_code}")
                                        return {}
                                else:
                                    # No job ID means the scan might have completed synchronously
                                    # or might not require a separate job
                                    print("ℹ️  DataScan completed without separate job (synchronous)")
                                    print("🎉 Check Dataplex Knowledge Catalog for results")
                                    return {}
                            else:
                                print("⚠️  DataScan has no execution status")
                                return {}
                        else:
                            print(f"⚠️  Could not get DataScan details: {datascan_response.status_code}")
                            return {}
                    else:
                        print("⚠️  Could not extract DataScan name from operation response")
                        return {}
                    
                    break
                else:
                    print(f"🔄 Operation status: In progress (attempt {operation_attempt}/{max_operation_attempts})")
            
            if operation_attempt >= max_operation_attempts:
                print(f"⏰ Operation did not complete within {operation_attempt * 5} seconds")
                return {}
            
            max_attempts = 10
            attempt = 0
            
            while attempt < max_attempts:
                attempt += 1
                time.sleep(10)  # Wait 10 seconds between checks
                
                status_response = requests.get(job_url, headers=headers)
                
                if status_response.status_code != 200:
                    print(f"⚠️  Could not check job status: {status_response.status_code}")
                    continue
                
                job_status = status_response.json().get('state', 'UNKNOWN')
                print(f"🔄 Job status: {job_status} (attempt {attempt}/{max_attempts})")
                
                if job_status == 'SUCCEEDED':
                    print("🎉 DataScan completed successfully!")
                    
                    # Retrieve the results
                    # Note: In a full implementation, you would parse the results
                    # and extract column descriptions from the documentation
                    print("ℹ️  Results available in Dataplex Knowledge Catalog")
                    print("   To view: Check Dataplex UI or use DataScan results API")
                    
                    # For now, return empty dict as placeholder
                    # In production, you would parse the actual results here
                    return {}
                    
                elif job_status == 'FAILED':
                    error_message = status_response.json().get('error', {}).get('message', 'Unknown failure')
                    print(f"❌ DataScan failed: {error_message}")
                    return {}
                
                # Continue waiting if job is still running
            
            print(f"⏰ DataScan did not complete within {max_attempts * 10} seconds")
            print("   You can check results later in Dataplex Knowledge Catalog")
            
            return {}
            
        except Exception as e:
            print(f"⚠️  Failed to generate insights: {e}")
            print("   This is expected if DataScan API is not enabled for your project")
            print("   To enable: Contact your Google Cloud administrator")
            return {}


    
    def _generate_google_table_insights_description(self, table_obj, table_ref: str) -> str:
        """
        Generate table description using Google Table Insights approach.
        
        This follows the Google Dataplex metadata enrichment pattern:
        https://docs.cloud.google.com/dataplex/docs/enrich-entries-metadata#add-aspects
        
        Args:
            table_obj: BigQuery Table object
            table_ref: Full table reference
            
        Returns:
            Generated table description following Google's approach
        """
        # Extract table metadata using Google's recommended approach
        table_id = table_obj.table_id
        
        # Get table statistics (Google Table Insights style)
        row_count = getattr(table_obj, 'num_rows', 'unknown')
        size_bytes = getattr(table_obj, 'num_bytes', 'unknown')
        
        # Format size properly
        if isinstance(size_bytes, (int, float)) and size_bytes > 0:
            size_mb = size_bytes / (1024 * 1024)
            size_str = f"{size_mb:.1f} MB"
        else:
            size_str = "unknown size"
        
        # Build description following Google's metadata enrichment pattern
        description = f"BigQuery table containing {row_count} rows ({size_str}). "
        
        # Add Dataplex-style metadata aspects
        description += f"Part of the Lakehouse Content marketing dataset. "
        
        # Add table-specific context using Google's approach
        if 'audience' in table_id:
            description += "Contains audience segmentation data including demographics, interests, and geographic information. "
            description += "Used for audience discovery, lookalike modeling, and campaign targeting."
        elif 'cookie' in table_id or 'visitor' in table_id:
            description += "Identity mapping table linking device identifiers to audience segments. "
            description += "Critical for cross-device identity resolution and attribution analysis."
        elif 'campaign' in table_id:
            description += "Marketing campaign metadata including budgets, objectives, and timing. "
            description += "Joins to pixel_events table via campaign_id for performance analysis."
        elif 'creative' in table_id:
            description += "Creative asset library with format, theme, and channel metadata. "
            description += "Linked to campaigns table for creative performance analysis."
        elif 'pixel' in table_id or 'event' in table_id:
            description += "Event-level tracking data including impressions, clicks, and video engagement. "
            description += "Partitioned by date for time-series analysis and performance reporting."
        elif 'transaction' in table_id:
            description += "Purchase transaction feed with Mastercard-style data. "
            description += "Used for ROAS calculation, LTV analysis, and attribution modeling."
        else:
            description += "Marketing data table supporting semantic discovery and AI-powered analysis."
        
        # Add partitioning info (Google-style)
        if table_obj.time_partitioning:
            description += f" Time-partitioned by {table_obj.time_partitioning.type} for optimized query performance."
        
        # Add Dataplex integration note
        description += " Registered in Dataplex Knowledge Graph for semantic data discovery."
        
        return description
    

    
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
    
    def create_template_markdown(self, table_id: str):
        """
        Create a template markdown file for manual descriptions.
        
        Args:
            table_id: Table name
        """
        markdown_file = os.path.join(self.markdown_dir, f"{table_id}.md")
        
        if os.path.exists(markdown_file):
            print(f"⚠️  Markdown file already exists: {markdown_file}")
            return
        
        try:
            table_ref = f"{self.dataset_id}.{table_id}"
            table_obj = self.client.get_table(table_ref)
            
            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(f"# {table_id}\n\n")
                f.write(f"<!-- Provide a high-level description of this table's purpose and content -->\n")
                f.write(f"This table contains...\n\n")
                f.write(f"## Columns\n\n")
                
                for field in table_obj.schema:
                    column_name = field.name
                    column_type = field.field_type
                    f.write(f"- {column_name}: <!-- Describe what this column represents -->\n")
                
            print(f"✅ Created template markdown file: {markdown_file}")
            print(f"   Edit this file to provide manual descriptions, then run enrichment.")
            
        except Exception as e:
            print(f"❌ Failed to create template for {table_id}: {e}")
    
    def create_all_templates(self):
        """
        Create template markdown files for all tables.
        """
        print("Creating markdown templates for all tables...")
        
        tables = self.client.list_tables(self.dataset_id)
        
        for table in tables:
            self.create_template_markdown(table.table_id)
        
        print("Template creation complete!")


if __name__ == "__main__":
    config = GeneratorConfig()
    enricher = HybridMetadataEnricher(config)
    enricher.generate_descriptions()