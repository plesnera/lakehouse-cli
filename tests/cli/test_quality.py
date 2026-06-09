"""CLI tests for quality command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lake_cli.cli import app


runner = CliRunner()


class TestQualityCommand:
    """quality CLI command — manages Dataplex data quality scans."""

    @patch("lake_cli.cli.DataQualityManager")
    def test_no_flags_defaults_to_run(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["quality"])
        assert result.exit_code == 0
        instance.create_and_run_scans.assert_called_once()

    @patch("lake_cli.cli.DataQualityManager")
    def test_dry_run_passed_to_create_and_run(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["quality", "--dry-run"])
        assert result.exit_code == 0
        instance.create_and_run_scans.assert_called_once_with(None, dry_run=True)

    @patch("lake_cli.cli.DataQualityManager")
    def test_results_calls_get_results(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["quality", "--results"])
        assert result.exit_code == 0
        instance.get_results.assert_called_once()

    @patch("lake_cli.cli.DataQualityManager")
    def test_results_with_table_filter(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(
            app, ["quality", "--results", "--table-names", "audience,campaigns"]
        )
        assert result.exit_code == 0
        instance.get_results.assert_called_once_with(["audience", "campaigns"])

    @patch("lake_cli.cli.DataQualityManager")
    def test_check_rules_calls_check_rules_method(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["quality", "--check-rules"])
        assert result.exit_code == 0
        instance.check_rules.assert_called_once()

    @patch("lake_cli.cli.DataQualityManager")
    def test_check_rules_with_table_filter(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(
            app, ["quality", "--check-rules", "--table-names", "campaigns"]
        )
        assert result.exit_code == 0
        instance.check_rules.assert_called_once_with(["campaigns"])

    @patch("lake_cli.cli.DataQualityManager")
    def test_sync_only_calls_sync_only(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["quality", "--sync-only"])
        assert result.exit_code == 0
        instance.sync_only.assert_called_once()

    @patch("lake_cli.cli.DataQualityManager")
    def test_sync_only_with_dry_run(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["quality", "--sync-only", "--dry-run"])
        assert result.exit_code == 0
        instance.sync_only.assert_called_once_with(None, dry_run=True)

    @patch("lake_cli.cli.DataQualityManager")
    def test_sync_only_with_table_filter(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(
            app, ["quality", "--sync-only", "--table-names", "audience,transactions"]
        )
        assert result.exit_code == 0
        instance.sync_only.assert_called_once_with(["audience", "transactions"], dry_run=False)

    @patch("lake_cli.cli.DataQualityManager")
    def test_run_flag_explicit(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["quality", "--run"])
        assert result.exit_code == 0
        instance.create_and_run_scans.assert_called_once()

    @patch("lake_cli.cli.DataQualityManager")
    def test_multiple_tables_comma_separated(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(
            app, ["quality", "--table-names", "audience,campaigns,transactions"]
        )
        assert result.exit_code == 0
        # create_and_run_scans is called (default run behavior)
        instance.create_and_run_scans.assert_called_once()
        call_tables = instance.create_and_run_scans.call_args[0][0]
        assert call_tables == ["audience", "campaigns", "transactions"]