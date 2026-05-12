"""Unit tests for LakehouseCatalogManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ingestion.lakehouse_catalog import LakehouseCatalogManager
from generators.config import GeneratorConfig


class TestLakehouseCatalogManager:
    """Unit tests for LakehouseCatalogManager — tests gcloud subprocess calls."""

    @pytest.fixture
    def config(self):
        return GeneratorConfig(
            data_project_id="test-project",
            location="us-east1",
            lakehouse_catalog_name="test-catalog",
            iceberg_namespace="marketing",
            iceberg_warehouse="gs://test-bucket/iceberg",
            subnet_name="dataproc-subnet",
        )

    @pytest.fixture
    def manager(self, config):
        return LakehouseCatalogManager(config)

    # ---- ensure_catalog tests ----

    @patch("subprocess.run")
    def test_ensure_catalog_exists(self, mock_run, manager):
        """Catalog already exists — describe succeeds."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = manager.ensure_catalog(dry_run=False)

        assert result == {"catalog_exists": True}
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[:4] == ["gcloud", "biglake", "iceberg", "catalogs"]
        assert "describe" in call_args

    @patch("subprocess.run")
    def test_ensure_catalog_not_found(self, mock_run, manager):
        """Catalog does not exist — describe returns NOT_FOUND."""
        mock_run.return_value = MagicMock(
            returncode=1, stderr="NOT_FOUND", stdout=""
        )

        result = manager.ensure_catalog(dry_run=False)

        assert result == {"catalog_exists": False}

    @patch("subprocess.run")
    def test_ensure_catalog_permission_denied(self, mock_run, manager):
        """Permission denied on describe — treated as exists."""
        mock_run.return_value = MagicMock(
            returncode=1, stderr="PERMISSION_DENIED", stdout=""
        )

        result = manager.ensure_catalog(dry_run=False)

        assert result == {"catalog_exists": True}

    @patch("subprocess.run")
    def test_ensure_catalog_dry_run(self, mock_run, manager):
        """Dry run — no subprocess calls."""
        result = manager.ensure_catalog(dry_run=True)

        assert result == {"catalog_exists": True}
        mock_run.assert_not_called()

    # ---- delete_catalog tests ----

    @patch("subprocess.run")
    def test_delete_catalog_success(self, mock_run, manager):
        """Catalog deleted successfully."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = manager.delete_catalog(dry_run=False)

        assert result == {"catalog_deleted": True}
        call_args = mock_run.call_args[0][0]
        assert call_args[:4] == ["gcloud", "biglake", "iceberg", "catalogs"]
        assert "delete" in call_args

    @patch("subprocess.run")
    def test_delete_catalog_not_found(self, mock_run, manager):
        """Catalog already deleted."""
        mock_run.return_value = MagicMock(
            returncode=1, stderr="NOT_FOUND: Catalog not found", stdout=""
        )

        result = manager.delete_catalog(dry_run=False)

        assert result == {"catalog_deleted": False}

    @patch("subprocess.run")
    def test_delete_catalog_dry_run(self, mock_run, manager):
        """Dry run — no subprocess calls."""
        result = manager.delete_catalog(dry_run=True)

        assert result == {"catalog_deleted": True}
        mock_run.assert_not_called()

    # ---- ensure_namespace tests ----

    @patch("subprocess.run")
    def test_ensure_namespace_already_exists(self, mock_run, manager):
        """Namespace already exists — idempotent."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = manager.ensure_namespace(dry_run=False)

        assert result == {"namespace_created": False}
        call_args = mock_run.call_args[0][0]
        assert call_args[:4] == ["gcloud", "biglake", "iceberg", "namespaces"]
        assert "describe" in call_args

    @patch("subprocess.run")
    def test_ensure_namespace_creates(self, mock_run, manager):
        """Namespace doesn't exist — describe fails then create succeeds."""
        mock_run.side_effect = [
            MagicMock(returncode=1, stderr="not found", stdout=""),
            MagicMock(returncode=0, stderr="", stdout=""),
        ]

        result = manager.ensure_namespace(dry_run=False)

        assert result == {"namespace_created": True}
        assert mock_run.call_count == 2
        create_args = mock_run.call_args_list[1][0][0]
        assert create_args[:4] == ["gcloud", "biglake", "iceberg", "namespaces"]
        assert "create" in create_args

    @patch("subprocess.run")
    def test_ensure_namespace_dry_run(self, mock_run, manager):
        """Dry run — no subprocess calls."""
        result = manager.ensure_namespace(dry_run=True)

        assert result == {"namespace_created": True}
        mock_run.assert_not_called()

    # ---- delete_namespace tests ----

    @patch("subprocess.run")
    def test_delete_namespace_success(self, mock_run, manager):
        """Namespace deleted successfully."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = manager.delete_namespace(dry_run=False)

        assert result == {"namespace_deleted": True}
        call_args = mock_run.call_args[0][0]
        assert call_args[:4] == ["gcloud", "biglake", "iceberg", "namespaces"]
        assert "delete" in call_args

    @patch("subprocess.run")
    def test_delete_namespace_not_found(self, mock_run, manager):
        """Namespace already deleted."""
        mock_run.return_value = MagicMock(
            returncode=1, stderr="not found", stdout=""
        )

        result = manager.delete_namespace(dry_run=False)

        assert result == {"namespace_deleted": False}

    @patch("subprocess.run")
    def test_delete_namespace_dry_run(self, mock_run, manager):
        """Dry run — no subprocess calls."""
        result = manager.delete_namespace(dry_run=True)

        assert result == {"namespace_deleted": True}
        mock_run.assert_not_called()
