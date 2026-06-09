"""CLI tests for vector-search, bqml-setup, and continuous-queries commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lake_cli.cli import app


runner = CliRunner()


class TestVectorSearchCommand:
    """vector-search CLI command."""

    @patch("lake_cli.cli.VectorSearchManager")
    def test_calls_setup(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["vector-search"])
        assert result.exit_code == 0
        instance.setup.assert_called_once_with(dry_run=False)

    @patch("lake_cli.cli.VectorSearchManager")
    def test_dry_run_passed(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["vector-search", "--dry-run"])
        assert result.exit_code == 0
        instance.setup.assert_called_once_with(dry_run=True)


class TestBqmlSetupCommand:
    """bqml-setup CLI command."""

    @patch("lake_cli.cli.BQMLGeminiManager")
    def test_calls_setup(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["bqml-setup"])
        assert result.exit_code == 0
        instance.setup.assert_called_once_with(dry_run=False)

    @patch("lake_cli.cli.BQMLGeminiManager")
    def test_dry_run_passed(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["bqml-setup", "--dry-run"])
        assert result.exit_code == 0
        instance.setup.assert_called_once_with(dry_run=True)


class TestContinuousQueriesCommand:
    """continuous-queries CLI command."""

    @patch("lake_cli.cli.ContinuousQueryManager")
    def test_default_dry_run_true(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["continuous-queries"])
        assert result.exit_code == 0
        instance.setup.assert_called_once_with(dry_run=True)

    @patch("lake_cli.cli.ContinuousQueryManager")
    def test_continuous_queries_defaults_to_dry_run(self, mock_mgr_class):
        instance = mock_mgr_class.return_value
        result = runner.invoke(app, ["continuous-queries"])
        assert result.exit_code == 0
        instance.setup.assert_called_once_with(dry_run=True)