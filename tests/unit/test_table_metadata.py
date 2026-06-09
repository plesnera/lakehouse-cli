"""Unit tests for table_metadata parsing functions."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lake_cli.table_metadata import (
    parse_table_metadata,
    load_all_table_metadata,
    _parse_dq_rule_line,
    TableMeta,
    ColumnMeta,
    RuleMeta,
)


class TestParseDQRuleLine:
    """_parse_dq_rule_line() converts markdown rule lines to RuleMeta."""

    def test_non_null_rule(self):
        rule = _parse_dq_rule_line("- audience_id: non_null")
        assert rule is not None
        assert rule.column == "audience_id"
        assert rule.rule_type == "non_null"
        assert rule.threshold == 1.0

    def test_non_null_with_custom_threshold(self):
        rule = _parse_dq_rule_line("- hem: non_null threshold=0.57")
        assert rule.threshold == 0.57

    def test_set_rule(self):
        rule = _parse_dq_rule_line("- status: set values=planned,active,completed,paused")
        assert rule.rule_type == "set"
        assert rule.values == ["planned", "active", "completed", "paused"]

    def test_regex_rule(self):
        rule = _parse_dq_rule_line("- email: regex pattern=[a-z]+@[a-z]+\\.[a-z]+")
        assert rule.rule_type == "regex"
        assert rule.pattern == "[a-z]+@[a-z]+\\.[a-z]+"

    def test_range_rule(self):
        rule = _parse_dq_rule_line("- age: range min=0 max=120")
        assert rule.rule_type == "range"
        assert rule.min_value == "0"
        assert rule.max_value == "120"

    def test_range_rule_with_strict_bounds(self):
        rule = _parse_dq_rule_line("- lat: range min=-90 max=90 strict_min=true strict_max=true")
        assert rule.strict_min_enabled is True
        assert rule.strict_max_enabled is True

    def test_rule_with_custom_dimension(self):
        rule = _parse_dq_rule_line("- lat: range dimension=VALIDITY min=-90 max=90")
        assert rule.dimension == "VALIDITY"

    def test_invalid_line_returns_none(self):
        assert _parse_dq_rule_line("not a rule line") is None
        assert _parse_dq_rule_line("") is None


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, sort_keys=False))


class TestParseTableMetadata:
    """parse_table_metadata() correctly converts YAML to TableMeta."""

    def test_parses_display_name(self, tmp_path: Path):
        path = tmp_path / "audience.yaml"
        _write_yaml(path, {
            "table_id": "audience",
            "display_name": "Audience Table",
            "description": "Description of audience.",
        })
        result = parse_table_metadata(str(path))
        assert result.display_name == "Audience Table"
        assert result.table_id == "audience"

    def test_parses_description(self, tmp_path: Path):
        path = tmp_path / "campaigns.yaml"
        _write_yaml(path, {
            "table_id": "campaigns",
            "display_name": "Campaigns",
            "description": "Marketing campaign data.",
        })
        result = parse_table_metadata(str(path))
        assert result.description == "Marketing campaign data."

    def test_parses_tags(self, tmp_path: Path):
        path = tmp_path / "test.yaml"
        _write_yaml(path, {
            "display_name": "Test Table",
            "tags": {
                "business_owner": "Marketing",
                "data_domain": "audience",
                "pii_class": "pseudonymous",
            },
        })
        result = parse_table_metadata(str(path))
        assert result.tags["business_owner"] == "Marketing"
        assert result.tags["data_domain"] == "audience"
        assert result.tags["pii_class"] == "pseudonymous"

    def test_parses_columns(self, tmp_path: Path):
        path = tmp_path / "test.yaml"
        _write_yaml(path, {
            "display_name": "Test Table",
            "columns": [
                {"name": "audience_id", "description": "Primary key."},
                {"name": "created_at", "description": "Timestamp of creation."},
            ],
        })
        result = parse_table_metadata(str(path))
        assert "audience_id" in result.columns
        assert result.columns["audience_id"].description == "Primary key."
        assert result.columns["created_at"].description == "Timestamp of creation."

    def test_parses_synonym_columns(self, tmp_path: Path):
        path = tmp_path / "test.yaml"
        _write_yaml(path, {
            "display_name": "Test Table",
            "columns": [
                {"name": "lat", "description": "Centroid latitude."},
                {"name": "location_lat", "description": "Synonym for lat.", "synonym_of": "lat"},
            ],
        })
        result = parse_table_metadata(str(path))
        assert result.columns["location_lat"].synonym_of == "lat"

    def test_parses_dq_rules(self, tmp_path: Path):
        path = tmp_path / "test.yaml"
        _write_yaml(path, {
            "display_name": "Test Table",
            "data_quality_rules": [
                {"column": "audience_id", "rule_type": "non_null"},
                {"column": "status", "rule_type": "set", "values": ["planned", "active", "completed", "paused"]},
            ],
        })
        result = parse_table_metadata(str(path))
        assert len(result.dq_rules) == 2
        assert result.dq_rules[0].column == "audience_id"
        assert result.dq_rules[0].rule_type == "non_null"
        assert result.dq_rules[1].column == "status"
        assert result.dq_rules[1].rule_type == "set"

    def test_synonym_map_property(self, tmp_path: Path):
        path = tmp_path / "test.yaml"
        _write_yaml(path, {
            "display_name": "Test Table",
            "columns": [
                {"name": "lat", "description": "Centroid latitude."},
                {"name": "location_lat", "description": "Synonym for lat.", "synonym_of": "lat"},
                {"name": "lon", "description": "Centroid longitude."},
            ],
        })
        result = parse_table_metadata(str(path))
        assert result.synonym_map == {"location_lat": "lat"}

    def test_tag_row_count_property(self, tmp_path: Path):
        path = tmp_path / "test.yaml"
        _write_yaml(path, {
            "display_name": "Test Table",
            "tags": {"row_count_approx": 8000},
        })
        result = parse_table_metadata(str(path))
        assert result.tag_row_count == 8000.0

    def test_tag_row_count_missing(self, tmp_path: Path):
        path = tmp_path / "test.yaml"
        _write_yaml(path, {"display_name": "Test Table"})
        result = parse_table_metadata(str(path))
        assert result.tag_row_count == 0.0


class TestLoadAllTableMetadata:
    """load_all_table_metadata() loads and parses all .yaml files in a directory."""

    def test_loads_all_yaml_files(self, tmp_path: Path):
        _write_yaml(tmp_path / "audience.yaml", {
            "display_name": "Audience",
            "tags": {"data_domain": "audience"},
        })
        _write_yaml(tmp_path / "campaigns.yaml", {
            "display_name": "Campaigns",
            "tags": {"data_domain": "campaigns"},
        })
        _write_yaml(tmp_path / "README.yaml", {"display_name": "Not a table"})

        result = load_all_table_metadata(str(tmp_path))
        assert "audience" in result
        assert "campaigns" in result
        assert "README" in result  # all .yaml files are loaded

    def test_returns_empty_dict_for_empty_dir(self, tmp_path: Path):
        result = load_all_table_metadata(str(tmp_path))
        assert result == {}

    def test_returns_empty_dict_for_nonexistent_dir(self):
        result = load_all_table_metadata("/nonexistent/path")
        assert result == {}
