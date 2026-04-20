"""CLI tests for manage-glossary and create-templates commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ingestion.cli import app


runner = CliRunner()


class TestManageGlossary:
    """manage-glossary CLI command."""

    @patch("ingestion.cli.BusinessGlossaryManager")
    def test_create_calls_create_glossary_from_markdown(self, mock_gm_class):
        instance = mock_gm_class.return_value
        result = runner.invoke(app, ["manage-glossary", "--action", "create"])
        assert result.exit_code == 0
        instance.create_glossary_from_markdown.assert_called_once_with(
            input_path=None, dry_run=False
        )

    @patch("ingestion.cli.BusinessGlossaryManager")
    def test_create_with_input_path(self, mock_gm_class):
        instance = mock_gm_class.return_value
        result = runner.invoke(
            app, ["manage-glossary", "--action", "create", "--input", "custom.md"]
        )
        assert result.exit_code == 0
        instance.create_glossary_from_markdown.assert_called_once_with(
            input_path="custom.md", dry_run=False
        )

    @patch("ingestion.cli.BusinessGlossaryManager")
    def test_create_with_dry_run(self, mock_gm_class):
        instance = mock_gm_class.return_value
        result = runner.invoke(
            app, ["manage-glossary", "--action", "create", "--dry-run"]
        )
        assert result.exit_code == 0
        instance.create_glossary_from_markdown.assert_called_once_with(
            input_path=None, dry_run=True
        )

    @patch("ingestion.cli.BusinessGlossaryManager")
    def test_validate_calls_validate_glossary(self, mock_gm_class):
        instance = mock_gm_class.return_value
        result = runner.invoke(app, ["manage-glossary", "--action", "validate"])
        assert result.exit_code == 0
        instance.validate_glossary.assert_called_once_with(input_path=None)

    @patch("ingestion.cli.BusinessGlossaryManager")
    def test_apply_calls_apply_glossary_to_assets(self, mock_gm_class):
        instance = mock_gm_class.return_value
        result = runner.invoke(app, ["manage-glossary", "--action", "apply"])
        assert result.exit_code == 0
        instance.apply_glossary_to_assets.assert_called_once_with(input_path=None)

    @patch("ingestion.cli.BusinessGlossaryManager")
    def test_reset_calls_reset_glossary(self, mock_gm_class):
        instance = mock_gm_class.return_value
        result = runner.invoke(app, ["manage-glossary", "--action", "reset"])
        assert result.exit_code == 0
        instance.reset_glossary.assert_called_once_with(input_path=None)

    @patch("ingestion.cli.BusinessGlossaryManager")
    def test_unknown_action_shows_error(self, mock_gm_class):
        result = runner.invoke(app, ["manage-glossary", "--action", "unknown"])
        assert result.exit_code == 0
        assert "Unknown action" in result.stdout

    @patch("ingestion.cli.BusinessGlossaryManager")
    def test_reset_flag_triggers_reset_first(self, mock_gm_class):
        instance = mock_gm_class.return_value
        result = runner.invoke(
            app, ["manage-glossary", "--action", "create", "--reset"]
        )
        assert result.exit_code == 0
        instance.reset_glossary.assert_called_once_with(input_path=None)


class TestCreateTemplates:
    """create-templates CLI command."""

    @patch("ingestion.cli.BusinessGlossaryManager")
    @patch("ingestion.cli.HybridMetadataEnricher")
    def test_calls_both_managers(self, mock_enricher_class, mock_gm_class):
        enricher_instance = mock_enricher_class.return_value
        gm_instance = mock_gm_class.return_value

        result = runner.invoke(app, ["create-templates"])

        assert result.exit_code == 0
        enricher_instance.create_all_templates.assert_called_once()
        gm_instance.generate_template_files.assert_called_once()