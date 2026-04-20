"""Unit tests for table_metadata parsing functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from ingestion.table_metadata import (
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


class TestParseTableMetadata:
    """parse_table_metadata() correctly converts markdown to TableMeta."""

    def test_parses_display_name(self, tmp_path: Path):
        path = tmp_path / "audience.md"
        path.write_text("# Audience Table\n\nDescription of audience.")
        result = parse_table_metadata(str(path))
        assert result.display_name == "Audience Table"
        assert result.table_id == "audience"

    def test_parses_description(self, tmp_path: Path):
        path = tmp_path / "campaigns.md"
        path.write_text("# Campaigns\n\nMarketing campaign data.")
        result = parse_table_metadata(str(path))
        assert result.description == "Marketing campaign data."

    def test_parses_tags(self, tmp_path: Path):
        path = tmp_path / "test.md"
        path.write_text(
            "# Test Table\n\n"
            "## Tags\n"
            "- business_owner: Marketing\n"
            "- data_domain: audience\n"
            "- pii_class: pseudonymous\n"
        )
        result = parse_table_metadata(str(path))
        assert result.tags["business_owner"] == "Marketing"
        assert result.tags["data_domain"] == "audience"
        assert result.tags["pii_class"] == "pseudonymous"

    def test_parses_columns(self, tmp_path: Path):
        path = tmp_path / "test.md"
        path.write_text(
            "# Test Table\n\n"
            "## Columns\n"
            "- audience_id: Primary key.\n"
            "- created_at: Timestamp of creation.\n"
        )
        result = parse_table_metadata(str(path))
        assert "audience_id" in result.columns
        assert result.columns["audience_id"].description == "Primary key."
        assert result.columns["created_at"].description == "Timestamp of creation."

    def test_parses_synonym_columns(self, tmp_path: Path):
        path = tmp_path / "test.md"
        path.write_text(
            "# Test Table\n\n"
            "## Columns\n"
            "- lat: Centroid latitude.\n"
            "- location_lat: Synonym for lat.\n"
            "  - Synonym Of: lat\n"
        )
        result = parse_table_metadata(str(path))
        assert result.columns["location_lat"].synonym_of == "lat"

    def test_parses_dq_rules(self, tmp_path: Path):
        path = tmp_path / "test.md"
        path.write_text(
            "# Test Table\n\n"
            "## Data Quality Rules\n"
            "- audience_id: non_null\n"
            "- status: set values=planned,active,completed,paused\n"
        )
        result = parse_table_metadata(str(path))
        assert len(result.dq_rules) == 2
        assert result.dq_rules[0].column == "audience_id"
        assert result.dq_rules[0].rule_type == "non_null"
        assert result.dq_rules[1].column == "status"
        assert result.dq_rules[1].rule_type == "set"

    def test_synonym_map_property(self, tmp_path: Path):
        path = tmp_path / "test.md"
        path.write_text(
            "# Test Table\n\n"
            "## Columns\n"
            "- lat: Centroid latitude.\n"
            "- location_lat: Synonym for lat.\n"
            "  - Synonym Of: lat\n"
            "- lon: Centroid longitude.\n"
        )
        result = parse_table_metadata(str(path))
        assert result.synonym_map == {"location_lat": "lat"}

    def test_tag_row_count_property(self, tmp_path: Path):
        path = tmp_path / "test.md"
        path.write_text(
            "# Test Table\n\n"
            "## Tags\n"
            "- row_count_approx: 8000\n"
        )
        result = parse_table_metadata(str(path))
        assert result.tag_row_count == 8000.0

    def test_tag_row_count_missing(self, tmp_path: Path):
        path = tmp_path / "test.md"
        path.write_text("# Test Table\n")
        result = parse_table_metadata(str(path))
        assert result.tag_row_count == 0.0


class TestLoadAllTableMetadata:
    """load_all_table_metadata() loads and parses all .md files in a directory."""

    def test_loads_all_md_files(self, tmp_path: Path):
        (tmp_path / "audience.md").write_text("# Audience\n\n## Tags\n- data_domain: audience\n")
        (tmp_path / "campaigns.md").write_text("# Campaigns\n\n## Tags\n- data_domain: campaigns\n")
        (tmp_path / "README.md").write_text("Not a table file.")

        result = load_all_table_metadata(str(tmp_path))
        assert "audience" in result
        assert "campaigns" in result
        assert "README" in result  # all .md files are loaded

    def test_returns_empty_dict_for_empty_dir(self, tmp_path: Path):
        result = load_all_table_metadata(str(tmp_path))
        assert result == {}

    def test_returns_empty_dict_for_nonexistent_dir(self):
        result = load_all_table_metadata("/nonexistent/path")
        assert result == {}