"""CLI tests for reset command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ingestion.cli import app


runner = CliRunner()


class TestResetCommand:
    """reset CLI command — teardown all generated resources."""

    @patch("google.cloud.bigquery.Client")
    @patch("ingestion.cli.BusinessGlossaryManager")
    def test_without_confirm_shows_warning(self, mock_gm_class, mock_bq_client):
        result = runner.invoke(app, ["reset"])
        assert result.exit_code == 0
        assert "will delete" in result.stdout
        assert "--confirm" in result.stdout
        # No BQ client methods called
        mock_bq_client.return_value.delete_table.assert_not_called()

    @patch("google.cloud.bigquery.Client")
    @patch("ingestion.cli.BusinessGlossaryManager")
    def test_with_confirm_deletes_everything(self, mock_gm_class, mock_bq_client):
        bq_instance = mock_bq_client.return_value
        gm_instance = mock_gm_class.return_value

        result = runner.invoke(app, ["reset", "--confirm"])
        assert result.exit_code == 0
        assert "Reset complete" in result.stdout

        # BQ tables deleted for all TABLES
        assert bq_instance.delete_table.call_count >= 6

        # Glossary reset called
        gm_instance.reset_glossary.assert_called_once()

    @patch("google.cloud.bigquery.Client")
    @patch("ingestion.cli.BusinessGlossaryManager")
    @patch("google.cloud.dataplex_v1.CatalogServiceClient")
    def test_with_confirm_deletes_catalog_entries(
        self, mock_catalog_class, mock_gm_class, mock_bq_client
    ):
        catalog_instance = mock_catalog_class.return_value

        result = runner.invoke(app, ["reset", "--confirm"])
        assert result.exit_code == 0

        # Catalog entries deleted for all TABLES
        assert catalog_instance.delete_entry.call_count >= 6

    @patch("os.path.exists", return_value=False)
    @patch("google.cloud.bigquery.Client")
    @patch("ingestion.cli.BusinessGlossaryManager")
    @patch("google.cloud.dataplex_v1.CatalogServiceClient")
    def test_no_iceberg_catalog_file_no_error(
        self, mock_catalog_class, mock_gm_class, mock_bq_client, mock_exists
    ):
        result = runner.invoke(app, ["reset", "--confirm"])
        assert result.exit_code == 0