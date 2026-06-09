"""CLI tests for dataset-insights command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lake_cli.cli import app


runner = CliRunner()


class TestDatasetInsightsCommand:
    """dataset-insights CLI command — manages Dataplex dataset-level insights scans."""

    @patch("lake_cli.cli.DatasetInsightsManager")
    def test_no_flags_creates_and_runs_scan(self, mock_mgr_class):
        """Default behavior: create and run scan."""
        instance = mock_mgr_class.return_value
        instance.create_scan.return_value = "dataset-insights-test"
        instance.run_scan.return_value = True

        result = runner.invoke(app, ["dataset-insights"])

        assert result.exit_code == 0
        instance.create_scan.assert_called_once_with(dry_run=False, timeout=600)
        instance.run_scan.assert_called_once()

    @patch("lake_cli.cli.DatasetInsightsManager")
    def test_dry_run_only_previews(self, mock_mgr_class):
        """--dry-run shows preview without creating scan."""
        instance = mock_mgr_class.return_value
        instance.create_scan.return_value = "dataset-insights-test"

        result = runner.invoke(app, ["dataset-insights", "--dry-run"])

        assert result.exit_code == 0
        instance.create_scan.assert_called_once_with(dry_run=True, timeout=600)
        instance.run_scan.assert_not_called()

    @patch("lake_cli.cli.DatasetInsightsManager")
    def test_results_gets_latest_results(self, mock_mgr_class):
        """--results retrieves and displays latest results."""
        instance = mock_mgr_class.return_value
        instance.get_results.return_value = {
            "status": "success",
            "description": "Marketing dataset containing audience, campaign, and transaction data",
            "relationship_graph": {"nodes": [], "edges": []},
            "sample_queries": ["SELECT * FROM audience JOIN transactions USING (cookie_id)"],
            "primary_keys": [],
            "foreign_keys": []
        }

        result = runner.invoke(app, ["dataset-insights", "--results"])

        assert result.exit_code == 0
        instance.get_results.assert_called_once()

    @patch("lake_cli.cli.DatasetInsightsManager")
    def test_run_flag_explicitly_triggers_scan(self, mock_mgr_class):
        """--run explicitly triggers scan creation and execution."""
        instance = mock_mgr_class.return_value
        instance.create_scan.return_value = "dataset-insights-test"
        instance.run_scan.return_value = True

        result = runner.invoke(app, ["dataset-insights", "--run"])

        assert result.exit_code == 0
        instance.create_scan.assert_called_once_with(dry_run=False, timeout=600)
        instance.run_scan.assert_called_once()

    @patch("lake_cli.cli.DatasetInsightsManager")
    def test_results_with_timeout(self, mock_mgr_class):
        """--results passes timeout to get_results."""
        instance = mock_mgr_class.return_value
        instance.get_results.return_value = {"status": "success"}

        result = runner.invoke(app, ["dataset-insights", "--results", "--timeout", "300"])

        assert result.exit_code == 0
        instance.get_results.assert_called_once_with(timeout=300)

    @patch("lake_cli.cli.DatasetInsightsManager")
    def test_create_scan_failure_handled(self, mock_mgr_class):
        """Create scan failure is handled gracefully."""
        instance = mock_mgr_class.return_value
        instance.create_scan.return_value = None

        result = runner.invoke(app, ["dataset-insights", "--run"])

        assert result.exit_code == 0
        instance.create_scan.assert_called_once_with(dry_run=False, timeout=600)
        # Should not try to run if creation failed
        instance.run_scan.assert_not_called()

    @patch("lake_cli.cli.DatasetInsightsManager")
    def test_timeout_passed_to_create_scan(self, mock_mgr_class):
        """--timeout is passed to create_scan when not using --results."""
        instance = mock_mgr_class.return_value
        instance.create_scan.return_value = "dataset-insights-test"
        instance.run_scan.return_value = True

        result = runner.invoke(app, ["dataset-insights", "--timeout", "300"])

        assert result.exit_code == 0
        instance.create_scan.assert_called_once_with(dry_run=False, timeout=300)
        instance.run_scan.assert_called_once()
