"""CLI tests for setup-catalog command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ingestion.cli import app


runner = CliRunner()


class TestSetupCatalogCommand:
    """setup-catalog CLI command — manage Lakehouse REST Catalog."""

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_calls_ensure_catalog_only_by_default(self, mock_lakehouse_class):
        lakehouse_instance = mock_lakehouse_class.return_value

        result = runner.invoke(app, ["setup-catalog", "--catalog-name", "test-catalog"])
        assert result.exit_code == 0

        lakehouse_instance.ensure_catalog.assert_called_once_with(dry_run=False)
        lakehouse_instance.ensure_namespace.assert_not_called()
        lakehouse_instance.register_tables.assert_not_called()

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_full_flag_creates_catalog_namespace_and_tables(self, mock_lakehouse_class):
        lakehouse_instance = mock_lakehouse_class.return_value

        result = runner.invoke(
            app, ["setup-catalog", "--catalog-name", "test-catalog", "--full"]
        )
        assert result.exit_code == 0

        lakehouse_instance.ensure_catalog.assert_called_once_with(dry_run=False)
        lakehouse_instance.ensure_namespace.assert_called_once_with(dry_run=False)
        lakehouse_instance.register_tables.assert_called_once_with(dry_run=False)

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_dry_run_previews_without_executing(self, mock_lakehouse_class):
        lakehouse_instance = mock_lakehouse_class.return_value

        result = runner.invoke(
            app, ["setup-catalog", "--catalog-name", "test-catalog", "--full", "--dry-run"]
        )
        assert result.exit_code == 0

        lakehouse_instance.ensure_catalog.assert_called_once_with(dry_run=True)
        lakehouse_instance.ensure_namespace.assert_called_once_with(dry_run=True)
        lakehouse_instance.register_tables.assert_called_once_with(dry_run=True)

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_uses_provided_catalog_name(self, mock_lakehouse_class):
        result = runner.invoke(
            app, ["setup-catalog", "--catalog-name", "my-custom-catalog"]
        )
        assert result.exit_code == 0

        call_config = mock_lakehouse_class.call_args[0][0]
        assert call_config.lakehouse_catalog_name == "my-custom-catalog"
