"""Shared test fixtures and mock infrastructure."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from generators.config import GeneratorConfig


# ---------------------------------------------------------------------------
# Config fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def test_config() -> GeneratorConfig:
    """A deterministic config for testing — no gcloud calls."""
    return GeneratorConfig(
        seed=42,
        n_audience_participants=100,
        n_audience_segments=10,
        n_cookies=1000,
        n_campaigns=10,
        n_creatives_per_campaign=2,
        n_pixel_events=5000,
        n_transactions=1000,
        data_project_id="test-data-project",
        catalog_project_id="test-catalog-project",
        iceberg_warehouse="gs://test-data-project-warehouse/iceberg",
        iceberg_namespace="marketing",
        location="us-east1",
    )


# ---------------------------------------------------------------------------
# Mock GCP clients
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bigquery_client():
    """MagicMock that behaves like a bigquery.Client."""
    client = MagicMock()
    client.project = "test-catalog-project"
    # Make list_tables return an empty list by default
    client.list_tables.return_value = []
    return client


@pytest.fixture
def mock_dataplex_catalog_client():
    """MagicMock that behaves like a dataplex_v1.CatalogServiceClient."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_dataplex_datascan_client():
    """MagicMock that behaves like a dataplex_v1.DataScanServiceClient."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_dataplex_glossary_client():
    """MagicMock that behaves like a dataplex_v1.BusinessGlossaryServiceClient."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_storage_client():
    """MagicMock that behaves like a storage.Client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_subprocess_run():
    """MagicMock for subprocess.run (gcloud commands)."""
    with patch("subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="123456789", stderr="")
        yield mock


# ---------------------------------------------------------------------------
# Deterministic time fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def frozen_time():
    """Freeze time.time() to a deterministic value."""
    with patch("time.time", return_value=1234567890.0):
        yield


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------

@pytest.fixture
def cli_runner():
    """A typer.testing.CliRunner for invoking the CLI."""
    from typer.testing import CliRunner
    from ingestion.cli import app
    return CliRunner()