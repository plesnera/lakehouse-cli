"""Unit tests for data_quality rule conversion and comparison functions."""

from __future__ import annotations

import pytest

from ingestion.data_quality import (
    _rule_from_meta,
    _rule_to_dict,
    _rules_equal,
    _compare_rule_lists,
    RuleMeta,
)
from ingestion.table_metadata import RuleMeta as RuleMetaFromTable
from google.cloud import dataplex_v1


class TestRuleFromMeta:
    """_rule_from_meta() converts RuleMeta to DataQualityRule."""

    def test_non_null_rule(self):
        meta = RuleMetaFromTable(column="audience_id", rule_type="non_null", threshold=1.0)
        rule = _rule_from_meta(meta)
        assert rule.name == "non-null-audience-id"
        assert rule.column == "audience_id"
        assert rule.non_null_expectation is not None

    def test_set_rule(self):
        meta = RuleMetaFromTable(
            column="status",
            rule_type="set",
            threshold=0.95,
            values=["active", "paused", "completed"],
        )
        rule = _rule_from_meta(meta)
        assert rule.set_expectation is not None
        assert rule.set_expectation.values == ["active", "paused", "completed"]

    def test_regex_rule(self):
        meta = RuleMetaFromTable(
            column="email",
            rule_type="regex",
            pattern=r"[a-z]+@[a-z]+\.[a-z]+",
        )
        rule = _rule_from_meta(meta)
        assert rule.regex_expectation is not None
        assert rule.regex_expectation.regex == r"[a-z]+@[a-z]+\.[a-z]+"

    def test_range_rule(self):
        meta = RuleMetaFromTable(
            column="lat",
            rule_type="range",
            min_value="-90",
            max_value="90",
        )
        rule = _rule_from_meta(meta)
        assert rule.range_expectation is not None
        assert rule.range_expectation.min_value == "-90"
        assert rule.range_expectation.max_value == "90"

    def test_dimension_from_meta(self):
        meta = RuleMetaFromTable(column="lat", rule_type="non_null", dimension="VALIDITY")
        rule = _rule_from_meta(meta)
        assert rule.dimension == "VALIDITY"


class TestRuleToDict:
    """_rule_to_dict() converts DataQualityRule to comparable dict."""

    def test_non_null_roundtrip(self):
        rule = dataplex_v1.DataQualityRule(
            name="test-rule",
            column="col1",
            dimension="COMPLETENESS",
            threshold=1.0,
            non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        )
        d = _rule_to_dict(rule)
        assert d["name"] == "test-rule"
        assert d["column"] == "col1"
        assert d["rule_type"] == "non_null"
        assert d["threshold"] == 1.0

    def test_set_roundtrip(self):
        rule = dataplex_v1.DataQualityRule(
            name="status-set",
            column="status",
            dimension="VALIDITY",
            threshold=0.95,
            set_expectation=dataplex_v1.DataQualityRule.SetExpectation(
                values=["active", "paused"]
            ),
        )
        d = _rule_to_dict(rule)
        assert d["rule_type"] == "set"
        assert d["values"] == sorted(["active", "paused"])

    def test_regex_roundtrip(self):
        rule = dataplex_v1.DataQualityRule(
            name="email-regex",
            column="email",
            dimension="VALIDITY",
            threshold=0.9,
            regex_expectation=dataplex_v1.DataQualityRule.RegexExpectation(
                regex=".+@.+"
            ),
        )
        d = _rule_to_dict(rule)
        assert d["rule_type"] == "regex"
        assert d["pattern"] == ".+@.+"

    def test_range_roundtrip(self):
        rule = dataplex_v1.DataQualityRule(
            name="lat-range",
            column="lat",
            dimension="VALIDITY",
            threshold=1.0,
            range_expectation=dataplex_v1.DataQualityRule.RangeExpectation(
                min_value="-90",
                max_value="90",
                strict_min_enabled=True,
                strict_max_enabled=False,
            ),
        )
        d = _rule_to_dict(rule)
        assert d["rule_type"] == "range"
        assert d["min_value"] == "-90"
        assert d["max_value"] == "90"
        assert d["strict_min"] is True
        assert d["strict_max"] is False


class TestRulesEqual:
    """_rules_equal() compares two DataQualityRules."""

    def test_identical_non_null_rules_are_equal(self):
        rule1 = dataplex_v1.DataQualityRule(
            name="test",
            column="col1",
            dimension="COMPLETENESS",
            threshold=1.0,
            non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        )
        rule2 = dataplex_v1.DataQualityRule(
            name="test",
            column="col1",
            dimension="COMPLETENESS",
            threshold=1.0,
            non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        )
        assert _rules_equal(rule1, rule2) is True

    def test_different_names_are_not_equal(self):
        rule1 = dataplex_v1.DataQualityRule(
            name="rule-a",
            column="col1",
            dimension="COMPLETENESS",
            threshold=1.0,
            non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        )
        rule2 = dataplex_v1.DataQualityRule(
            name="rule-b",
            column="col1",
            dimension="COMPLETENESS",
            threshold=1.0,
            non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        )
        assert _rules_equal(rule1, rule2) is False


class TestCompareRuleLists:
    """_compare_rule_lists() diffs markdown rules against active rules."""

    def test_no_rules(self):
        to_add, to_remove, changed = _compare_rule_lists([], [])
        assert to_add == []
        assert to_remove == []
        assert changed == []

    def test_all_new_rules(self):
        new_rule = dataplex_v1.DataQualityRule(
            name="new-rule",
            column="col1",
            dimension="COMPLETENESS",
            threshold=1.0,
            non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        )
        to_add, to_remove, changed = _compare_rule_lists([new_rule], [])
        assert len(to_add) == 1
        assert to_remove == []
        assert changed == []

    def test_all_removed_rules(self):
        old_rule = dataplex_v1.DataQualityRule(
            name="old-rule",
            column="col1",
            dimension="COMPLETENESS",
            threshold=1.0,
            non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        )
        to_add, to_remove, changed = _compare_rule_lists([], [old_rule])
        assert to_add == []
        assert len(to_remove) == 1
        assert changed == []

    def test_changed_rule(self):
        rule_v1 = dataplex_v1.DataQualityRule(
            name="rule",
            column="col1",
            dimension="COMPLETENESS",
            threshold=0.5,
            non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        )
        rule_v2 = dataplex_v1.DataQualityRule(
            name="rule",
            column="col1",
            dimension="COMPLETENESS",
            threshold=1.0,
            non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        )
        to_add, to_remove, changed = _compare_rule_lists([rule_v2], [rule_v1])
        assert to_add == []
        assert to_remove == []
        assert len(changed) == 1

    def test_unchanged_rules(self):
        rule = dataplex_v1.DataQualityRule(
            name="stable-rule",
            column="col1",
            dimension="COMPLETENESS",
            threshold=1.0,
            non_null_expectation=dataplex_v1.DataQualityRule.NonNullExpectation(),
        )
        to_add, to_remove, changed = _compare_rule_lists([rule], [rule])
        assert to_add == []
        assert to_remove == []
        assert changed == []