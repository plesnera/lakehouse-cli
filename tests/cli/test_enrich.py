"""CLI tests for enrich-metadata and create-templates commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ingestion.cli import app


runner = CliRunner()


class TestEnrichMetadata:
    """enrich-metadata CLI command."""

    @patch("ingestion.cli.HybridMetadataEnricher")
    def test_no_args_calls_generate_descriptions(self, mock_enricher_class):
        instance = mock_enricher_class.return_value
        result = runner.invoke(app, ["enrich-metadata"])
        assert result.exit_code == 0
        instance.generate_descriptions.assert_called_once()

    @patch("ingestion.cli.HybridMetadataEnricher")
    def test_google_insights_flag(self, mock_enricher_class):
        instance = mock_enricher_class.return_value
        result = runner.invoke(app, ["enrich-metadata", "--google-insights"])
        assert result.exit_code == 0
        instance.generate_descriptions_with_google_insights.assert_called_once()

    @patch("ingestion.cli.HybridMetadataEnricher")
    def test_specific_tables_with_google_insights(self, mock_enricher_class):
        instance = mock_enricher_class.return_value
        result = runner.invoke(
            app,
            [
                "enrich-metadata",
                "--table-names", "campaigns,transactions",
                "--google-insights",
            ],
        )
        assert result.exit_code == 0
        instance.generate_descriptions_for_tables_with_google_insights.assert_called_once()
        call_args = instance.generate_descriptions_for_tables_with_google_insights.call_args
        assert call_args[0][0] == ["campaigns", "transactions"]

    @patch("ingestion.cli.HybridMetadataEnricher")
    def test_specific_tables_with_metadata_files(self, mock_enricher_class):
        instance = mock_enricher_class.return_value
        result = runner.invoke(
            app,
            [
                "enrich-metadata",
                "--table-names", "audience,campaigns",
                "--metadata-files", "audience.md,campaigns.md",
            ],
        )
        assert result.exit_code == 0
        instance.generate_descriptions_for_tables_with_files.assert_called_once()
        call_args = instance.generate_descriptions_for_tables_with_files.call_args
        assert call_args[0][0] == ["audience", "campaigns"]
        assert call_args[0][1] == ["audience.md", "campaigns.md"]

    @patch("ingestion.cli.HybridMetadataEnricher")
    def test_table_count_mismatch_error(self, mock_enricher_class):
        result = runner.invoke(
            app,
            [
                "enrich-metadata",
                "--table-names", "a,b,c",
                "--metadata-files", "a.md,b.md",
            ],
        )
        assert result.exit_code == 0
        assert "does not match" in result.stdout

    @patch("ingestion.cli.HybridMetadataEnricher")
    def test_table_names_without_files_or_google_insights_error(self, mock_enricher_class):
        result = runner.invoke(
            app,
            [
                "enrich-metadata",
                "--table-names", "audience",
            ],
        )
        assert result.exit_code == 0
        assert "must provide metadata files" in result.stdout

    @patch("ingestion.cli.HybridMetadataEnricher")
    def test_dry_run_passed_through(self, mock_enricher_class):
        instance = mock_enricher_class.return_value
        result = runner.invoke(app, ["enrich-metadata", "--dry-run"])
        assert result.exit_code == 0
        instance.generate_descriptions.assert_called_once_with(timeout=300, dry_run=True)

    @patch("ingestion.cli.HybridMetadataEnricher")
    def test_all_tables_google_insights(self, mock_enricher_class):
        instance = mock_enricher_class.return_value
        result = runner.invoke(app, ["enrich-metadata", "--google-insights"])
        assert result.exit_code == 0
        instance.generate_descriptions_with_google_insights.assert_called_once_with(
            timeout=300, dry_run=False
        )