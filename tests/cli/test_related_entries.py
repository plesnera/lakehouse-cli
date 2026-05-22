"""CLI tests for list-related-entries and scan-for-related-entries commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ingestion.cli import app


runner = CliRunner()


class TestListRelatedEntries:
    """list-related-entries CLI command."""

    @patch("ingestion.cli.RelatedEntriesManager")
    def test_calls_manager_with_term(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        instance.list_related_entries.return_value = []
        result = runner.invoke(app, ["list-related-entries", "--term", "advertiser"])
        assert result.exit_code == 0
        instance.list_related_entries.assert_called_once_with(
            term_name="advertiser", glossary=None
        )

    @patch("ingestion.cli.RelatedEntriesManager")
    def test_calls_manager_with_glossary(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        instance.list_related_entries.return_value = []
        result = runner.invoke(
            app,
            [
                "list-related-entries",
                "--term", "brand",
                "--glossary", "marketing-business-glossary",
            ],
        )
        assert result.exit_code == 0
        instance.list_related_entries.assert_called_once_with(
            term_name="brand", glossary="marketing-business-glossary"
        )

    def test_missing_term_option_fails(self):
        result = runner.invoke(app, ["list-related-entries"])
        assert result.exit_code != 0


class TestScanForRelatedEntries:
    """scan-for-related-entries CLI command."""

    @patch("ingestion.cli.RelatedEntriesManager")
    def test_calls_manager_with_catalog(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        instance.scan_for_related_entries.return_value = ([], [])
        result = runner.invoke(
            app,
            ["scan-for-related-entries", "--catalog", "my-catalog"],
        )
        assert result.exit_code == 0
        instance.scan_for_related_entries.assert_called_once_with(
            catalog_name="my-catalog", namespace=None, glossary=None
        )

    @patch("ingestion.cli.RelatedEntriesManager")
    def test_calls_manager_with_all_options(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        instance.scan_for_related_entries.return_value = ([], [])
        result = runner.invoke(
            app,
            [
                "scan-for-related-entries",
                "--catalog", "my-catalog",
                "--namespace", "marketing",
                "--glossary", "marketing-business-glossary",
            ],
        )
        assert result.exit_code == 0
        instance.scan_for_related_entries.assert_called_once_with(
            catalog_name="my-catalog",
            namespace="marketing",
            glossary="marketing-business-glossary",
        )

    def test_missing_catalog_option_fails(self):
        result = runner.invoke(app, ["scan-for-related-entries"])
        assert result.exit_code != 0

    @patch("ingestion.cli.RelatedEntriesManager")
    def test_namespace_optional(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        instance.scan_for_related_entries.return_value = ([], [])
        result = runner.invoke(
            app,
            ["scan-for-related-entries", "--catalog", "c"],
        )
        assert result.exit_code == 0
        call_kwargs = instance.scan_for_related_entries.call_args
        assert call_kwargs[1]["namespace"] is None or call_kwargs[0][1] is None
