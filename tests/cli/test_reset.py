"""CLI tests for reset command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lake_cli.cli import app


runner = CliRunner()


class TestResetCommand:
    """reset CLI command — teardown all generated resources."""

    @patch("google.cloud.bigquery.Client")
    @patch("lake_cli.cli.BusinessGlossaryManager")
    @patch("lake_cli.cli.LakehouseCatalogManager")
    def test_without_confirm_shows_warning(self, mock_lakehouse_class, mock_gm_class, mock_bq_client):
        result = runner.invoke(app, ["reset"])
        assert result.exit_code == 0
        assert "will delete" in result.stdout
        assert "--confirm" in result.stdout
        # No BQ client methods called
        mock_bq_client.return_value.delete_table.assert_not_called()

    @patch("lake_cli.cli.BusinessGlossaryManager")
    @patch("lake_cli.cli.LakehouseCatalogManager")
    def test_with_confirm_deletes_resources(self, mock_lakehouse_class, mock_gm_class):
        gm_instance = mock_gm_class.return_value
        lakehouse_instance = mock_lakehouse_class.return_value

        result = runner.invoke(app, ["reset", "--confirm"])
        assert result.exit_code == 0
        assert "Reset complete" in result.stdout

        # Lakehouse namespace deleted (catalog itself is manual-only)
        lakehouse_instance.delete_namespace.assert_called_once()

        # Glossary reset called
        gm_instance.reset_glossary.assert_called_once()

    @patch("lake_cli.cli.BusinessGlossaryManager")
    @patch("lake_cli.cli.LakehouseCatalogManager")
    @patch("google.cloud.dataplex_v1.CatalogServiceClient")
    def test_with_confirm_deletes_catalog_entries(
        self, mock_catalog_class, mock_lakehouse_class, mock_gm_class
    ):
        catalog_instance = mock_catalog_class.return_value

        result = runner.invoke(app, ["reset", "--confirm"])
        assert result.exit_code == 0

        # Catalog entries deleted for all TABLES
        assert catalog_instance.delete_entry.call_count >= 6
