"""CLI tests for register-table command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ingestion.cli import app


runner = CliRunner()


class TestRegisterTableCommand:
    """register-table CLI command — register external Iceberg tables."""

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_register_single_table(self, mock_lakehouse_class):
        lakehouse_instance = mock_lakehouse_class.return_value
        lakehouse_instance.ensure_catalog.return_value = {"catalog_exists": True}

        result = runner.invoke(
            app,
            [
                "register-table",
                "--table-names", "my_table",
                "--metadata-locations", "gs://bucket/my_table/metadata.json",
                "--catalog-name", "test-catalog",
            ],
        )
        assert result.exit_code == 0

        lakehouse_instance.ensure_catalog.assert_called_once_with(dry_run=False)
        lakehouse_instance.ensure_namespace.assert_called_once_with(dry_run=False)
        lakehouse_instance.register_external_tables.assert_called_once_with(
            tables={"my_table": "gs://bucket/my_table/metadata.json"},
            dry_run=False,
        )

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_register_multiple_tables(self, mock_lakehouse_class):
        lakehouse_instance = mock_lakehouse_class.return_value
        lakehouse_instance.ensure_catalog.return_value = {"catalog_exists": True}

        result = runner.invoke(
            app,
            [
                "register-table",
                "--table-names", "t1,t2",
                "--metadata-locations", "gs://b/t1/metadata.json,gs://b/t2/metadata.json",
            ],
        )
        assert result.exit_code == 0

        lakehouse_instance.register_external_tables.assert_called_once_with(
            tables={"t1": "gs://b/t1/metadata.json", "t2": "gs://b/t2/metadata.json"},
            dry_run=False,
        )

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_dry_run(self, mock_lakehouse_class):
        lakehouse_instance = mock_lakehouse_class.return_value
        lakehouse_instance.ensure_catalog.return_value = {"catalog_exists": True}

        result = runner.invoke(
            app,
            [
                "register-table",
                "--table-names", "my_table",
                "--metadata-locations", "gs://bucket/my_table/metadata.json",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0

        lakehouse_instance.ensure_catalog.assert_called_once_with(dry_run=True)
        lakehouse_instance.ensure_namespace.assert_called_once_with(dry_run=True)
        lakehouse_instance.register_external_tables.assert_called_once_with(
            tables={"my_table": "gs://bucket/my_table/metadata.json"},
            dry_run=True,
        )

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_mismatched_counts_error(self, mock_lakehouse_class):
        result = runner.invoke(
            app,
            [
                "register-table",
                "--table-names", "t1,t2",
                "--metadata-locations", "gs://b/t1/metadata.json",
            ],
        )
        assert result.exit_code == 0
        assert "does not match" in result.output
        mock_lakehouse_class.return_value.register_external_tables.assert_not_called()

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_catalog_missing(self, mock_lakehouse_class):
        lakehouse_instance = mock_lakehouse_class.return_value
        lakehouse_instance.ensure_catalog.return_value = {"catalog_exists": False}

        result = runner.invoke(
            app,
            [
                "register-table",
                "--table-names", "my_table",
                "--metadata-locations", "gs://bucket/my_table/metadata.json",
            ],
        )
        assert result.exit_code == 0
        assert "does not exist" in result.output
        lakehouse_instance.register_external_tables.assert_not_called()

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_overrides_config(self, mock_lakehouse_class):
        lakehouse_instance = mock_lakehouse_class.return_value
        lakehouse_instance.ensure_catalog.return_value = {"catalog_exists": True}

        result = runner.invoke(
            app,
            [
                "register-table",
                "--table-names", "my_table",
                "--metadata-locations", "gs://bucket/my_table/metadata.json",
                "--catalog-name", "custom-catalog",
                "--namespace", "custom_ns",
                "--data-project", "custom-project",
                "--iceberg-warehouse", "gs://custom-warehouse",
            ],
        )
        assert result.exit_code == 0

        call_config = mock_lakehouse_class.call_args[0][0]
        assert call_config.lakehouse_catalog_name == "custom-catalog"
        assert call_config.iceberg_namespace == "custom_ns"
        assert call_config.data_project_id == "custom-project"
        assert call_config.iceberg_warehouse == "gs://custom-warehouse"
