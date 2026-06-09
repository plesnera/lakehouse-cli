"""Regression tests for HybridMetadataEnricher internals.

These tests verify that:
1. generate_descriptions passes use_google_insights=False (not the default True).
2. generate_descriptions_for_tables passes use_google_insights=False.
3. generate_descriptions uses _build_table_id_mapping to resolve custom-named YAML files.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, call

import pytest

from lake_cli.table_and_column_insights import HybridMetadataEnricher


FIXTURES_METADATA = os.path.join(os.path.dirname(__file__), "..", "fixtures", "metadata")


def _make_enricher(metadata_dir: str | None = None) -> HybridMetadataEnricher:
    """Create an enricher with a mocked BigQuery client and Config."""
    config = MagicMock()
    config.project_id = "test-project"
    config.iceberg_namespace = "marketing"

    with patch("lake_cli.table_and_column_insights.bigquery.Client"):
        enricher = HybridMetadataEnricher(config)

    if metadata_dir is not None:
        enricher.metadata_dir = metadata_dir
    return enricher


class TestGenerateDescriptionsDefaultMode:
    """generate_descriptions must use manual YAML, not Google Insights."""

    def test_passes_use_google_insights_false(self):
        enricher = _make_enricher()

        # Mock list_tables to return one table
        mock_table = MagicMock()
        mock_table.table_id = "audience"
        enricher.client.list_tables.return_value = [mock_table]

        with patch.object(enricher, "_generate_descriptions_core") as mock_core, \
             patch.object(enricher, "_build_table_id_mapping", return_value={}):
            enricher.generate_descriptions()

        # The critical assertion: use_google_insights must be False
        mock_core.assert_called_once()
        _, kwargs = mock_core.call_args
        assert kwargs["use_google_insights"] is False

    def test_resolves_custom_named_yaml_via_table_id(self):
        enricher = _make_enricher(metadata_dir=FIXTURES_METADATA)

        mock_table = MagicMock()
        mock_table.table_id = "audience"
        enricher.client.list_tables.return_value = [mock_table]

        with patch.object(enricher, "_generate_descriptions_core") as mock_core:
            enricher.generate_descriptions()

        mock_core.assert_called_once()
        _, kwargs = mock_core.call_args
        metadata_files = kwargs["metadata_files"]
        # Should resolve audience -> audience_profile.yaml via table_id field
        assert len(metadata_files) == 1
        assert metadata_files[0] is not None
        assert "audience_profile.yaml" in metadata_files[0]


class TestGenerateDescriptionsForTablesDefaultMode:
    """generate_descriptions_for_tables must use manual YAML, not Google Insights."""

    def test_passes_use_google_insights_false(self):
        enricher = _make_enricher()

        with patch.object(enricher, "_generate_descriptions_core") as mock_core, \
             patch.object(enricher, "_build_table_id_mapping", return_value={}):
            enricher.generate_descriptions_for_tables(["campaigns"])

        mock_core.assert_called_once()
        _, kwargs = mock_core.call_args
        assert kwargs["use_google_insights"] is False

    def test_resolves_custom_named_yaml_via_table_id(self):
        enricher = _make_enricher(metadata_dir=FIXTURES_METADATA)

        with patch.object(enricher, "_generate_descriptions_core") as mock_core:
            enricher.generate_descriptions_for_tables(["audience"])

        mock_core.assert_called_once()
        _, kwargs = mock_core.call_args
        metadata_files = kwargs["metadata_files"]
        assert len(metadata_files) == 1
        assert metadata_files[0] is not None
        assert "audience_profile.yaml" in metadata_files[0]


class TestBuildTableIdMapping:
    """_build_table_id_mapping must scan YAML files and key by table_id."""

    def test_maps_custom_filename_to_table_id(self):
        enricher = _make_enricher(metadata_dir=FIXTURES_METADATA)
        mapping = enricher._build_table_id_mapping()
        assert "audience" in mapping
        assert "audience_profile.yaml" in mapping["audience"]

    def test_empty_dir_returns_empty_mapping(self, tmp_path):
        enricher = _make_enricher(metadata_dir=str(tmp_path))
        mapping = enricher._build_table_id_mapping()
        assert mapping == {}
