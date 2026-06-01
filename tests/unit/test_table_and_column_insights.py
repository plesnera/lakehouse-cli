"""Unit tests for HybridMetadataEnricher in ingestion/table_and_column_insights.py."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from ingestion.config import Config
from ingestion.table_and_column_insights import HybridMetadataEnricher


class TestDiscoverManualMetadata:
    """Regression tests for Issue #10 — enrich-metadata ignores manual YAML files."""

    @patch("ingestion.table_and_column_insights.bigquery.Client")
    def test_generate_descriptions_discovers_yaml_by_table_id(
        self, mock_client_class
    ):
        """
        When generate_descriptions() runs in manual mode, it should discover
        metadata files whose *internal* table_id matches a table in the dataset,
        even if the filename does not exactly match {table_id}.yaml.
        """
        # Arrange: mock BigQuery client
        mock_client = mock_client_class.return_value
        mock_table = MagicMock()
        mock_table.table_id = "audience"
        mock_client.list_tables.return_value = [mock_table]

        mock_bq_table = MagicMock()
        mock_bq_table.schema = [
            MagicMock(name="user_id", field_type="STRING", mode="NULLABLE", description=None, fields=[]),
        ]
        mock_client.get_table.return_value = mock_bq_table

        # Create a temporary metadata directory with a file named
        # audience_profile.yaml whose table_id is "audience"
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata_dir = os.path.join(tmpdir, "metadata")
            os.makedirs(metadata_dir, exist_ok=True)

            yaml_path = os.path.join(metadata_dir, "audience_profile.yaml")
            with open(yaml_path, "w", encoding="utf-8") as f:
                f.write(
                    "table_id: audience\n"
                    "description: >\n"
                    "  Audience profile table.\n"
                    "columns:\n"
                    "  - name: user_id\n"
                    "    description: Unique user identifier.\n"
                )

            # Patch _update_table_metadata so we can assert on calls
            with patch.object(
                HybridMetadataEnricher, "_update_table_metadata"
            ) as mock_update:
                config = MagicMock(spec=Config)
                config.project_id = "test-project"
                config.iceberg_namespace = "test_dataset"
                enricher = HybridMetadataEnricher(config)
                enricher.metadata_dir = metadata_dir

                enricher.generate_descriptions(dry_run=False)

                # Assert _update_table_metadata was called with the discovered description
                mock_update.assert_called_once()
                call_args = mock_update.call_args
                assert call_args[0][0] == "test-project.test_dataset.audience"
                assert call_args[0][1] == "Audience profile table."
                assert call_args[0][2] == {
                    "user_id": "Unique user identifier."
                }

    @patch("ingestion.table_and_column_insights.bigquery.Client")
    def test_generate_descriptions_for_tables_passes_use_google_insights_false(
        self, mock_client_class
    ):
        """
        generate_descriptions_for_tables() must explicitly disable Google Insights
        so that manual YAML files are used.
        """
        mock_client = mock_client_class.return_value
        mock_bq_table = MagicMock()
        mock_bq_table.schema = []
        mock_client.get_table.return_value = mock_bq_table

        with tempfile.TemporaryDirectory() as tmpdir:
            metadata_dir = os.path.join(tmpdir, "metadata")
            os.makedirs(metadata_dir, exist_ok=True)

            yaml_path = os.path.join(metadata_dir, "audience.yaml")
            with open(yaml_path, "w", encoding="utf-8") as f:
                f.write("table_id: audience\ndescription: Audience table\n")

            with patch.object(
                HybridMetadataEnricher, "_generate_descriptions_core"
            ) as mock_core:
                config = MagicMock(spec=Config)
                config.project_id = "test-project"
                config.iceberg_namespace = "test_dataset"
                enricher = HybridMetadataEnricher(config)
                enricher.metadata_dir = metadata_dir

                enricher.generate_descriptions_for_tables(
                    ["audience"], dry_run=False
                )

                mock_core.assert_called_once()
                _, kwargs = mock_core.call_args
                assert kwargs["use_google_insights"] is False
