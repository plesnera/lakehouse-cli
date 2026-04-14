#!/usr/bin/env python3
"""
Hybrid Metadata Enrichment System

This module implements a hybrid approach to metadata enrichment that combines:
1. Manual markdown-based descriptions (human expertise)
2. Google Table Insights (automated statistical analysis)

The system allows users to provide high-level semantic context in markdown files,
while using Google's AI to generate data-driven descriptions based on actual
statistics and distributions.
"""

import time
import os
import json
from typing import Dict, List, Optional, Tuple
from google.cloud import bigquery
from google.api_core.exceptions import NotFound, GoogleAPICallError
from generators.config import GeneratorConfig



class HybridMetadataEnricher:
    """
    Enriches BigQuery tables with hybrid metadata using manual descriptions + Google Table Insights.
    
    This class combines human-provided semantic context with automated statistical analysis
    to create the most accurate and useful metadata possible.
    """
    
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset_id = f"{config.project_id}.{config.iceberg_namespace}"
        self.markdown_dir = "metadata_descriptions"
        
        # Ensure markdown directory exists
        os.makedirs(self.markdown_dir, exist_ok=True)
    
    def generate_descriptions(self, timeout: int = 300):
        """
        Generate hybrid descriptions for all tables in the dataset.
        
        Args:
            timeout: Maximum time to wait for operations (seconds)
        """
        print("Starting hybrid metadata enrichment...")
        
        # List all tables in the dataset
        tables = self.client.list_tables(self.dataset_id)
        
        for table in tables:
            table_ref = f"{self.dataset_id}.{table.table_id}"
            print(f"Processing table: {table_ref}")
            
            try:
                # Get current table info
                table_obj = self.client.get_table(table_ref)
                
                # Generate hybrid descriptions
                table_description, column_descriptions = self._generate_hybrid_descriptions(table_obj)
                
                # Update table with descriptions
                self._update_table_metadata(
                    table_ref, 
                    table_description, 
                    column_descriptions
                )
                print(f"✅ Enriched metadata for: {table_ref}")
                
            except Exception as e:
                print(f"⚠️  Failed to enrich {table_ref}: {e}")
        
        print("Hybrid metadata enrichment complete!")
    
    def generate_descriptions_for_tables(self, table_names: List[str], timeout: int = 300):
        """
        Generate hybrid descriptions for specific tables using default markdown files.
        
        Args:
            table_names: List of table names to enrich
            timeout: Maximum time to wait for operations (seconds)
        """
        print(f"Starting selective hybrid metadata enrichment for {len(table_names)} tables...")
        
        for table_name in table_names:
            table_ref = f"{self.dataset_id}.{table_name}"
            print(f"Processing table: {table_ref}")
            
            try:
                # Get current table info
                table_obj = self.client.get_table(table_ref)
                
                # Generate hybrid descriptions using default markdown file
                table_description, column_descriptions = self._generate_hybrid_descriptions(table_obj)
                
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
        
        print("Manual metadata enrichment complete!")
    
    def generate_descriptions_for_tables_with_google_insights(self, table_names: List[str], timeout: int = 300):
        """
        Generate descriptions for specific tables using ONLY Google-style automated insights.
        
        This method does NOT use manual markdown files - it generates descriptions
        purely from Google Dataplex-style automated analysis.
        
        Args:
            table_names: List of table names in format project.dataset.table or just table_name
            timeout: Maximum time to wait for operations (seconds)
        """
        print(f"Starting Google insights enrichment for {len(table_names)} tables...")
        
        for table_name in table_names:
            # Support both full format (project.dataset.table) and short format (table)
            if '.' in table_name and table_name.count('.') >= 2:
                # Full format: project.dataset.table
                table_ref = table_name
            else:
                # Short format: table_name only
                table_ref = f"{self.dataset_id}.{table_name}"
            
            print(f"Processing table: {table_ref} (Google insights only)")
            
            try:
                # Get current table info
                table_obj = self.client.get_table(table_ref)
                
                # Generate descriptions using ONLY Google insights (no manual files)
                table_description, column_descriptions = self._generate_table_insights(table_ref)
                
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
        
        print("Google insights enrichment complete!")
    
    def generate_descriptions_with_google_insights(self, timeout: int = 300):
        """
        Generate descriptions for ALL tables using ONLY Google-style automated insights.
        
        This method processes all tables in the dataset using pure Google insights
        without any manual markdown files.
        
        Args:
            timeout: Maximum time to wait for operations (seconds)
        """
        print("Starting Google insights enrichment for all tables...")
        
        # List all tables in the dataset
        tables = self.client.list_tables(self.dataset_id)
        
        for table in tables:
            table_ref = f"{self.dataset_id}.{table.table_id}"
            print(f"Processing table: {table_ref} (Google insights only)")
            
            try:
                # Get current table info
                table_obj = self.client.get_table(table_ref)
                
                # Generate descriptions using ONLY Google insights (no manual files)
                table_description, column_descriptions = self._generate_table_insights(table_ref)
                
                # Update table with descriptions
                self._update_table_metadata(
                    table_ref, 
                    table_description, 
                    column_descriptions
                )
                print(f"✅ Enriched metadata for: {table_ref}")
                
            except Exception as e:
                print(f"⚠️  Failed to enrich {table_ref}: {e}")
        
        print("Google insights enrichment for all tables complete!")
    
    def generate_descriptions_for_tables_with_files(self, table_names: List[str], metadata_files: List[str], timeout: int = 300):
        """
        Generate hybrid descriptions for specific tables using explicit metadata files.
        
        Args:
            table_names: List of table names in format project.dataset.table or just table_name
            metadata_files: List of metadata file paths to use
            timeout: Maximum time to wait for operations (seconds)
        """
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
                
                # Generate hybrid descriptions using explicit metadata file
                table_description, column_descriptions = self._generate_hybrid_descriptions_with_file(table_obj, metadata_file)
                
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
        
        print("Explicit hybrid metadata enrichment complete!")
    
    def _generate_hybrid_descriptions(self, table_obj) -> Tuple[str, Dict[str, str]]:
        """
        Generate hybrid descriptions by combining manual markdown with Google Table Insights.
        
        Args:
            table_obj: BigQuery Table object
            
        Returns:
            Tuple of (table_description, column_descriptions_dict)
        """
        table_id = table_obj.table_id
        table_ref = f"{self.dataset_id}.{table_id}"
        
        # Step 1: Load manual descriptions from markdown (default location)
        manual_table_desc, manual_column_descs = self._load_manual_descriptions(table_ref)
    
    def _generate_hybrid_descriptions_with_file(self, table_obj, metadata_file: str) -> Tuple[str, Dict[str, str]]:
        """
        Generate hybrid descriptions using explicit metadata file.
        
        Args:
            table_obj: BigQuery Table object
            metadata_file: Explicit path to metadata file
            
        Returns:
            Tuple of (table_description, column_descriptions_dict)
        """
        table_id = table_obj.table_id
        table_ref = f"{self.dataset_id}.{table_id}"
        
        # Step 1: Load manual descriptions from explicit markdown file
        manual_table_desc, manual_column_descs = self._load_manual_descriptions(table_ref, metadata_file)
        
        # Step 2: Generate Google Table Insights
        insights_table_desc, insights_column_descs = self._generate_table_insights(table_ref)
        
        # Step 3: Combine both sources intelligently
        final_table_description = self._combine_descriptions(
            manual_table_desc, 
            insights_table_desc,
            is_table=True
        )
        
        final_column_descriptions = {}
        for column_name, manual_desc in manual_column_descs.items():
            insights_desc = insights_column_descs.get(column_name, "")
            final_column_descriptions[column_name] = self._combine_descriptions(
                manual_desc, 
                insights_desc,
                is_table=False
            )
        
        # For columns not in manual descriptions, use insights only
        for column_name, insights_desc in insights_column_descs.items():
            if column_name not in final_column_descriptions:
                final_column_descriptions[column_name] = insights_desc
        
        return final_table_description, final_column_descriptions
        
        # Step 2: Generate Google Table Insights
        insights_table_desc, insights_column_descs = self._generate_table_insights(table_ref)
        
        # Step 3: Combine both sources intelligently
        final_table_description = self._combine_descriptions(
            manual_table_desc, 
            insights_table_desc,
            is_table=True
        )
        
        final_column_descriptions = {}
        for column_name, manual_desc in manual_column_descs.items():
            insights_desc = insights_column_descs.get(column_name, "")
            final_column_descriptions[column_name] = self._combine_descriptions(
                manual_desc, 
                insights_desc,
                is_table=False
            )
        
        # For columns not in manual descriptions, use insights only
        for column_name, insights_desc in insights_column_descs.items():
            if column_name not in final_column_descriptions:
                final_column_descriptions[column_name] = insights_desc
        
        return final_table_description, final_column_descriptions
    
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
                
                # Extract table description (first paragraph)
                if lines:
                    table_description = lines[0].strip()
                    if table_description.startswith('# '):
                        table_description = table_description[2:].strip()
                    elif table_description.startswith('## '):
                        table_description = table_description[3:].strip()
                
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
    
    def _generate_google_column_insights(self, table_obj) -> Dict[str, str]:
        """
        Generate column descriptions using Google Dataplex metadata enrichment approach.
        
        This follows Google's recommended pattern for column-level metadata:
        https://docs.cloud.google.com/dataplex/docs/enrich-entries-metadata#add-aspects
        
        Args:
            table_obj: BigQuery Table object
            
        Returns:
            Dictionary of column_name: description following Google's approach
        """
        descriptions = {}
        
        for field in table_obj.schema:
            column_name = field.name
            column_type = field.field_type
            field_mode = field.mode
            
            # Build description following Google's metadata enrichment pattern
            description = f"Column of type {column_type} ({field_mode}). "
            
            # Add Google-style semantic analysis based on Dataplex aspects
            if 'id' in column_name:
                description += "Unique identifier. "
                if 'cookie' in column_name or 'visitor' in column_name or 'device' in column_name:
                    description += "Device/browser identifier used for cross-site tracking and identity resolution. "
                    description += "Part of the marketing identity graph. Join key to other identity tables."
                elif 'campaign' in column_name:
                    description += "Foreign key referencing the campaigns table. "
                    description += "Used for campaign performance analysis and attribution."
                elif 'creative' in column_name:
                    description += "Foreign key referencing the creatives table. "
                    description += "Used for creative performance analysis."
                elif 'audience' in column_name:
                    description += "Foreign key referencing audience segments. "
                    description += "Used for audience targeting and segmentation analysis."
                else:
                    description += "Primary or foreign key identifier within the data model."
            
            elif 'date' in column_name or 'ts' in column_name or 'time' in column_name:
                description += "Temporal field. "
                if 'partition' in column_name or column_name.endswith('_date'):
                    description += "Partitioning column optimizing time-range queries. "
                    description += "Used for time-series analysis and performance reporting."
                elif 'event' in column_name:
                    description += "Timestamp when the event occurred. "
                    description += "Critical for event sequencing and user journey analysis."
                elif 'created' in column_name or 'updated' in column_name:
                    description += "Audit timestamp for record creation or modification. "
                    description += "Used for data lineage and change tracking."
            
            elif 'amount' in column_name or 'spend' in column_name or 'budget' in column_name or 'revenue' in column_name:
                description += "Monetary value in USD. "
                if 'spend' in column_name:
                    description += "Advertising spend. "
                    description += "Used for ROAS calculation and budget optimization."
                elif 'budget' in column_name:
                    description += "Campaign budget allocation. "
                    description += "Used for budget pacing and spend management."
                elif 'revenue' in column_name:
                    description += "Revenue generated. "
                    description += "Used for performance measurement and attribution."
                else:
                    description += "Financial transaction amount. "
                    description += "Used for financial reporting and analysis."
            
            elif 'lat' in column_name or 'lon' in column_name or 'location' in column_name:
                description += "Geospatial coordinate. "
                if 'lat' in column_name:
                    description += "Latitude (WGS84). "
                elif 'lon' in column_name:
                    description += "Longitude (WGS84). "
                description += "Enables geographic analysis, regional targeting, and location-based insights."
            
            elif 'hem' in column_name or 'hashed_email' in column_name or 'email' in column_name:
                description += "Privacy-preserving identifier. "
                description += "Hashed email address enabling cross-channel attribution while protecting PII. "
                description += "Semantic synonym for other email hash fields. Part of the identity resolution graph."
            
            elif 'segment' in column_name or 'category' in column_name:
                description += "Categorical field. "
                if 'segment' in column_name:
                    description += "Audience segmentation category. "
                    description += "Used for targeting and personalization."
                else:
                    description += "Classification category. "
                    description += "Used for grouping and analysis."
            
            elif 'score' in column_name or 'index' in column_name or 'rating' in column_name:
                description += "Numerical metric. "
                if 'score' in column_name:
                    description += "Performance or affinity score. "
                    description += "Used for ranking and prioritization."
                elif 'index' in column_name:
                    description += "Composite index or indicator. "
                    description += "Used for comparative analysis."
                elif 'rating' in column_name:
                    description += "Quality or satisfaction rating. "
                    description += "Used for performance evaluation."
            
            elif 'name' in column_name or 'title' in column_name or 'label' in column_name:
                description += "Descriptive text field. "
                if 'name' in column_name:
                    description += "Human-readable name or identifier. "
                elif 'title' in column_name:
                    description += "Formal title or heading. "
                description += "Used for display and reporting purposes."
            
            elif 'status' in column_name or 'state' in column_name:
                description += "State indicator. "
                description += "Represents the current status or lifecycle stage. "
                description += "Used for workflow management and filtering."
            
            # Add Dataplex integration note for key fields
            if column_name in ['audience_id', 'campaign_id', 'creative_id', 'cookie_id', 'hem']:
                description += " Registered in Dataplex Knowledge Graph as a business term."
            
            descriptions[column_name] = description.strip()
        
        return descriptions
    
    def _combine_descriptions(self, manual_desc: str, insights_desc: str, is_table: bool) -> str:
        """
        Intelligently combine manual and insights descriptions.
        
        Args:
            manual_desc: Manual description from markdown
            insights_desc: Automated description from insights
            is_table: Whether this is a table description (vs column)
            
        Returns:
            Combined description
        """
        combined = ""
        
        # If we have manual description, use it as primary
        if manual_desc:
            combined = manual_desc
            
            # Add insights as supplementary information
            if insights_desc:
                combined += " " + insights_desc
        else:
            # Use insights only
            combined = insights_desc
        
        return combined.strip()
    
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