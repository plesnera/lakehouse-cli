"""CLI tests for profile command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ingestion.cli import app


runner = CliRunner()


class TestProfileCommand:
    """profile CLI command — create and run Dataplex data profile scans."""

    @patch("ingestion.cli.DataProfilingManager")
    def test_no_flags_creates_and_runs_scans(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["profile"])
        assert result.exit_code == 0
        instance.create_and_run_scans.assert_called_once_with(dry_run=False)

    @patch("ingestion.cli.DataProfilingManager")
    def test_dry_run_passed_to_manager(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["profile", "--dry-run"])
        assert result.exit_code == 0
        instance.create_and_run_scans.assert_called_once_with(dry_run=True)

    @patch("ingestion.cli.DataProfilingManager")
    def test_results_calls_get_results(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["profile", "--results"])
        assert result.exit_code == 0
        instance.get_results.assert_called_once()
        instance.create_and_run_scans.assert_not_called()