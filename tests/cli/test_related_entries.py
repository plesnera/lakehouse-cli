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

    @patch("ingestion.cli.RelatedEntriesManager")
    def test_output_flag_triggers_export(self, mock_mgr_class):
        """When --output is provided, export_proposals_yaml is called."""
        instance = mock_mgr_class.return_value
        instance.scan_for_related_entries.return_value = ([], [])
        instance._discover_glossary.return_value = {
            "name": "projects/p/locations/l/glossaries/my-glossary",
            "displayName": "My Glossary",
        }
        result = runner.invoke(
            app,
            [
                "scan-for-related-entries",
                "--catalog", "c",
                "--output", "/tmp/test_proposals.yaml",
            ],
        )
        assert result.exit_code == 0
        instance.export_proposals_yaml.assert_called_once()
        call_kwargs = instance.export_proposals_yaml.call_args
        assert call_kwargs[1]["output_path"] == "/tmp/test_proposals.yaml"
        assert call_kwargs[1]["catalog_name"] == "c"
        assert call_kwargs[1]["glossary_id"] == "my-glossary"

    @patch("ingestion.cli.RelatedEntriesManager")
    def test_no_output_flag_skips_export(self, mock_mgr_class):
        """Without --output, export_proposals_yaml is NOT called."""
        instance = mock_mgr_class.return_value
        instance.scan_for_related_entries.return_value = ([], [])
        result = runner.invoke(
            app,
            ["scan-for-related-entries", "--catalog", "c"],
        )
        assert result.exit_code == 0
        instance.export_proposals_yaml.assert_not_called()


class TestApplyRelatedEntries:
    """apply-related-entries CLI command."""

    @patch("ingestion.cli.RelatedEntriesManager")
    def test_calls_apply_proposals(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        instance.apply_proposals.return_value = []
        result = runner.invoke(
            app,
            ["apply-related-entries", "--input", "proposals.yaml"],
        )
        assert result.exit_code == 0
        instance.apply_proposals.assert_called_once_with(
            input_path="proposals.yaml",
            dry_run=False,
            glossary_override=None,
            project_override=None,
            location_override=None,
        )

    @patch("ingestion.cli.RelatedEntriesManager")
    def test_dry_run_flag(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        instance.apply_proposals.return_value = []
        result = runner.invoke(
            app,
            ["apply-related-entries", "--input", "p.yaml", "--dry-run"],
        )
        assert result.exit_code == 0
        call_kwargs = instance.apply_proposals.call_args
        assert call_kwargs[1]["dry_run"] is True

    @patch("ingestion.cli.RelatedEntriesManager")
    def test_override_flags(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        instance.apply_proposals.return_value = []
        result = runner.invoke(
            app,
            [
                "apply-related-entries",
                "--input", "p.yaml",
                "--glossary", "g",
                "--project", "proj",
                "--location", "eu-west1",
            ],
        )
        assert result.exit_code == 0
        instance.apply_proposals.assert_called_once_with(
            input_path="p.yaml",
            dry_run=False,
            glossary_override="g",
            project_override="proj",
            location_override="eu-west1",
        )

    def test_missing_input_option_fails(self):
        result = runner.invoke(app, ["apply-related-entries"])
        assert result.exit_code != 0
