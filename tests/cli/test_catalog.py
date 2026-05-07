"""CLI tests for catalog and ingest commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ingestion.cli import app


runner = CliRunner()


class TestCatalogCommand:
    """catalog CLI command — registers Iceberg tables in BigQuery and Dataplex."""

    @patch("ingestion.cli._run_catalog")
    def test_calls_run_catalog_with_default_config(self, mock_run_catalog):
        result = runner.invoke(app, ["catalog"])
        assert result.exit_code == 0
        mock_run_catalog.assert_called_once()
        # Config passed should have all defaults
        call_config = mock_run_catalog.call_args[0][0]
        assert call_config.data_project_id is not None
        assert call_config.catalog_project_id is not None

    @patch("ingestion.cli._run_catalog")
    def test_overrides_data_project(self, mock_run_catalog):
        result = runner.invoke(
            app, ["catalog", "--data-project", "my-data-project"]
        )
        assert result.exit_code == 0
        call_config = mock_run_catalog.call_args[0][0]
        assert call_config.data_project_id == "my-data-project"

    @patch("ingestion.cli._run_catalog")
    def test_overrides_catalog_project(self, mock_run_catalog):
        result = runner.invoke(
            app, ["catalog", "--catalog-project", "my-catalog-project"]
        )
        assert result.exit_code == 0
        call_config = mock_run_catalog.call_args[0][0]
        assert call_config.catalog_project_id == "my-catalog-project"

    @patch("ingestion.cli._run_catalog")
    def test_overrides_iceberg_warehouse(self, mock_run_catalog):
        result = runner.invoke(
            app, ["catalog", "--iceberg-warehouse", "gs://my-bucket/iceberg"]
        )
        assert result.exit_code == 0
        call_config = mock_run_catalog.call_args[0][0]
        assert call_config.iceberg_warehouse == "gs://my-bucket/iceberg"

    @patch("ingestion.cli._run_catalog")
    def test_overrides_biglake_connection(self, mock_run_catalog):
        result = runner.invoke(
            app,
            [
                "catalog",
                "--biglake-connection",
                "projects/p/locations/l/connections/c",
            ],
        )
        assert result.exit_code == 0
        call_config = mock_run_catalog.call_args[0][0]
        assert call_config.biglake_connection == "projects/p/locations/l/connections/c"

    @patch("ingestion.cli._run_catalog")
    def test_all_overrides_together(self, mock_run_catalog):
        result = runner.invoke(
            app,
            [
                "catalog",
                "--data-project", "dp",
                "--catalog-project", "cp",
                "--iceberg-warehouse", "gs://b/iceberg",
                "--biglake-connection", "projects/p/locations/l/connections/c",
            ],
        )
        assert result.exit_code == 0
        call_config = mock_run_catalog.call_args[0][0]
        assert call_config.data_project_id == "dp"
        assert call_config.catalog_project_id == "cp"
        assert call_config.iceberg_warehouse == "gs://b/iceberg"
        assert call_config.biglake_connection == "projects/p/locations/l/connections/c"

    @patch("ingestion.cli._run_catalog")
    def test_overrides_catalog_name(self, mock_run_catalog):
        result = runner.invoke(
            app, ["catalog", "--catalog-name", "my-catalog"]
        )
        assert result.exit_code == 0
        call_config = mock_run_catalog.call_args[0][0]
        assert call_config.lakehouse_catalog_name == "my-catalog"


class TestRunCatalogLogic:
    """_run_catalog internal logic — validation and early exits."""

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_bails_when_catalog_name_empty(self, mock_lakehouse_class):
        from ingestion.cli import _run_catalog
        from generators.config import GeneratorConfig

        config = GeneratorConfig(lakehouse_catalog_name="")
        _run_catalog(config)
        mock_lakehouse_class.assert_not_called()

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_bails_when_catalog_does_not_exist(self, mock_lakehouse_class):
        from ingestion.cli import _run_catalog
        from generators.config import GeneratorConfig

        lakehouse_instance = mock_lakehouse_class.return_value
        lakehouse_instance.ensure_catalog.return_value = {"catalog_exists": False}

        config = GeneratorConfig(lakehouse_catalog_name="missing-catalog")
        _run_catalog(config)

        lakehouse_instance.ensure_namespace.assert_not_called()
        lakehouse_instance.register_tables.assert_not_called()

    @patch("ingestion.cli.LakehouseCatalogManager")
    def test_runs_full_pipeline_when_catalog_exists(self, mock_lakehouse_class):
        from ingestion.cli import _run_catalog
        from generators.config import GeneratorConfig

        lakehouse_instance = mock_lakehouse_class.return_value
        lakehouse_instance.ensure_catalog.return_value = {"catalog_exists": True}

        config = GeneratorConfig(lakehouse_catalog_name="existing-catalog")
        _run_catalog(config)

        lakehouse_instance.ensure_namespace.assert_called_once()
        lakehouse_instance.register_tables.assert_called_once()


class TestIngestCommand:
    """ingest CLI command — full streamed ingestion."""

    @patch("ingestion.cli.IcebergWriter")
    @patch("ingestion.cli.Orchestrator")
    @patch("ingestion.cli._run_catalog")
    def test_generates_writes_and_catalogs(self, mock_run, mock_orch_class, mock_writer_class):
        orch_instance = mock_orch_class.return_value
        writer_instance = mock_writer_class.return_value

        result = runner.invoke(app, ["ingest"])
        assert result.exit_code == 0

        mock_orch_class.assert_called_once()
        mock_writer_class.assert_called_once()
        writer_instance.write_stream.assert_called_once()
        mock_run.assert_called_once()

    @patch("ingestion.cli.IcebergWriter")
    @patch("ingestion.cli.Orchestrator")
    @patch("ingestion.cli._run_catalog")
    def test_passes_project_overrides(self, mock_run, mock_orch_class, mock_writer_class):
        result = runner.invoke(
            app,
            [
                "ingest",
                "--data-project", "dp",
                "--catalog-project", "cp",
                "--iceberg-warehouse", "gs://b/iceberg",
                "--biglake-connection", "projects/p/locations/l/connections/c",
            ],
        )
        assert result.exit_code == 0

        orch_config = mock_orch_class.call_args[0][0]
        assert orch_config.data_project_id == "dp"
        assert orch_config.catalog_project_id == "cp"
        assert orch_config.iceberg_warehouse == "gs://b/iceberg"

    @patch("ingestion.cli.IcebergWriter")
    @patch("ingestion.cli.Orchestrator")
    @patch("ingestion.cli._run_catalog")
    def test_success_message_printed(self, mock_run, mock_orch_class, mock_writer_class):
        result = runner.invoke(app, ["ingest"])
        assert "Ingestion complete" in result.stdout

    @patch("ingestion.cli.IcebergWriter")
    @patch("ingestion.cli.Orchestrator")
    @patch("ingestion.cli._run_catalog")
    def test_overrides_catalog_name(self, mock_run, mock_orch_class, mock_writer_class):
        result = runner.invoke(
            app, ["ingest", "--catalog-name", "my-ingest-catalog"]
        )
        assert result.exit_code == 0
        orch_config = mock_orch_class.call_args[0][0]
        assert orch_config.lakehouse_catalog_name == "my-ingest-catalog"
        # _run_catalog receives the same config object
        run_config = mock_run.call_args[0][0]
        assert run_config.lakehouse_catalog_name == "my-ingest-catalog"