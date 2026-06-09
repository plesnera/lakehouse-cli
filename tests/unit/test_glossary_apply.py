"""Unit tests for glossary_manager apply_glossary_to_assets and _build_dataplex_bq_entry_name."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, ANY

import pytest
import yaml
from pathlib import Path

from lake_cli.config import Config


class TestBuildDataplexBqEntryName:
    """_build_dataplex_bq_entry_name() constructs the native @dataplex entry path."""

    @patch("lake_cli.glossary_manager.dataplex_v1")
    @patch("lake_cli.glossary_manager.BusinessGlossaryManager._get_project_number", return_value="123456789")
    def test_returns_dataplex_entry_group_path(self, _mock_proj_num, _mock_dataplex):
        from lake_cli.glossary_manager import BusinessGlossaryManager

        config = Config(
            catalog_project_id="my-project",
            location="us-east1",
            iceberg_warehouse="gs://my-project-warehouse/iceberg",
        )
        mgr = BusinessGlossaryManager(config)

        result = mgr._build_dataplex_bq_entry_name("audience")

        assert "/entryGroups/@dataplex/entries/" in result
        assert "bigquery.googleapis.com/projects/my-project/datasets/marketing/tables/audience" in result
        assert result == (
            "projects/my-project/locations/us-east1/entryGroups/@dataplex/entries/"
            "bigquery.googleapis.com/projects/my-project/datasets/marketing/tables/audience"
        )

    @patch("lake_cli.glossary_manager.dataplex_v1")
    @patch("lake_cli.glossary_manager.BusinessGlossaryManager._get_project_number", return_value="123456789")
    def test_does_not_reference_custom_entry_group(self, _mock_proj_num, _mock_dataplex):
        from lake_cli.glossary_manager import BusinessGlossaryManager

        config = Config(
            catalog_project_id="my-project",
            location="us-east1",
            iceberg_warehouse="gs://my-project-warehouse/iceberg",
        )
        mgr = BusinessGlossaryManager(config)

        result = mgr._build_dataplex_bq_entry_name("transactions")

        # Must NOT use the custom marketing-lakehouse entry group
        assert "marketing-lakehouse" not in result
        assert "/entryGroups/@dataplex/" in result


class TestApplyGlossaryToAssetsEntryPath:
    """apply_glossary_to_assets() targets native @dataplex entries, not custom entry group."""

    def _write_yaml(self, tmp_path: Path, data: dict) -> str:
        path = tmp_path / "glossary.yaml"
        path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True))
        return str(path)

    @patch("lake_cli.glossary_manager.BusinessGlossaryManager._get_project_number", return_value="123456789")
    @patch("lake_cli.glossary_manager.BusinessGlossaryManager._ensure_glossary_aspect_type")
    @patch("lake_cli.glossary_manager.dataplex_v1")
    def test_entry_path_uses_dataplex_entry_group(
        self, mock_dataplex, mock_ensure_aspect, _mock_proj_num, tmp_path
    ):
        from lake_cli.glossary_manager import BusinessGlossaryManager

        config = Config(
            catalog_project_id="my-project",
            location="us-east1",
            iceberg_warehouse="gs://my-project-warehouse/iceberg",
        )

        glossary_data = {
            "glossary_id": "test-glossary",
            "display_name": "Test Glossary",
            "description": "Test",
            "categories": [
                {
                    "name": "identity",
                    "display_name": "Identity",
                    "description": "Identity terms",
                    "terms": [
                        {
                            "name": "hashed-email",
                            "display_name": "hashed_email",
                            "description": "Email hash.",
                            "tables": ["audience"],
                        }
                    ],
                }
            ],
        }
        glossary_path = self._write_yaml(tmp_path, glossary_data)

        # Mock the catalog client
        mock_catalog_client = MagicMock()
        mock_dataplex.CatalogServiceClient.return_value = mock_catalog_client
        mock_dataplex.BusinessGlossaryServiceClient.return_value = MagicMock()

        # Mock Aspect and Entry so they behave like real protobuf objects
        mock_dataplex.Aspect.return_value = MagicMock()

        mock_entry = MagicMock()
        mock_entry.aspects = {}
        mock_dataplex.Entry.return_value = mock_entry

        mgr = BusinessGlossaryManager(config)
        mgr.catalog_client = mock_catalog_client

        mgr.apply_glossary_to_assets(input_path=glossary_path)

        # Verify the Entry was created with the @dataplex entry path
        call_args = mock_dataplex.Entry.call_args
        entry_name = call_args.kwargs.get("name") or call_args[1].get("name") if call_args[1] else call_args[0][0] if call_args[0] else None
        # Entry() is called with name= kwarg
        assert entry_name is not None, "Entry was not called with a name"
        assert "/entryGroups/@dataplex/entries/" in entry_name
        assert "bigquery.googleapis.com/projects/my-project/datasets/marketing/tables/audience" in entry_name
        assert "marketing-lakehouse" not in entry_name
