"""Unit tests for ingestion.related_entries helpers and matching logic."""

from __future__ import annotations

import pytest

from ingestion.related_entries import (
    ApplyResult,
    ExactMatch,
    FuzzyProposal,
    RelatedEntriesManager,
    _extract_entry_group_from_name,
    _extract_entry_id_from_name,
    _extract_project_from_resource,
    _extract_synonym_target,
    extract_column_names_from_entry,
    normalize_name,
    score_column,
    tokenize_description,
)


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------

class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("Advertiser") == "advertiser"

    def test_hyphens_to_underscores(self):
        assert normalize_name("country-code") == "country_code"

    def test_mixed(self):
        assert normalize_name("Hashed-Email") == "hashed_email"

    def test_already_normalized(self):
        assert normalize_name("cookie_id") == "cookie_id"

    def test_strips_whitespace(self):
        assert normalize_name("  brand  ") == "brand"

    def test_empty(self):
        assert normalize_name("") == ""


# ---------------------------------------------------------------------------
# _extract_project_from_resource
# ---------------------------------------------------------------------------

class TestExtractProjectFromResource:
    def test_bigquery_resource(self):
        resource = "bigquery.googleapis.com/projects/my-project/datasets/ds/tables/t"
        assert _extract_project_from_resource(resource) == "my-project"

    def test_biglake_resource(self):
        resource = "biglake.googleapis.com/projects/lakehouse-proj/catalogs/c/namespaces/n/tables/t"
        assert _extract_project_from_resource(resource) == "lakehouse-proj"

    def test_no_project(self):
        assert _extract_project_from_resource("some-random-string") == ""


# ---------------------------------------------------------------------------
# _extract_entry_group_from_name / _extract_entry_id_from_name
# ---------------------------------------------------------------------------

class TestExtractEntryParts:
    ENTRY_NAME = (
        "projects/123/locations/us-east1/entryGroups/@bigquery/entries/"
        "bigquery.googleapis.com/projects/p/datasets/d/tables/t"
    )

    def test_entry_group(self):
        assert _extract_entry_group_from_name(self.ENTRY_NAME) == "@bigquery"

    def test_entry_id(self):
        expected = "bigquery.googleapis.com/projects/p/datasets/d/tables/t"
        assert _extract_entry_id_from_name(self.ENTRY_NAME) == expected

    def test_no_entry_group(self):
        assert _extract_entry_group_from_name("no-match") == ""

    def test_no_entry_id(self):
        assert _extract_entry_id_from_name("no-match") == ""


# ---------------------------------------------------------------------------
# extract_column_names_from_entry
# ---------------------------------------------------------------------------

class TestExtractColumnNames:
    def test_extracts_fields(self):
        entry = {
            "aspects": {
                "proj.us-east1.schema": {
                    "data": {
                        "fields": [
                            {"name": "campaign_id"},
                            {"name": "brand"},
                            {"name": "advertiser"},
                        ]
                    }
                }
            }
        }
        cols = extract_column_names_from_entry(entry)
        assert cols == ["campaign_id", "brand", "advertiser"]

    def test_multiple_aspects(self):
        entry = {
            "aspects": {
                "aspect1": {"data": {"fields": [{"name": "col_a"}]}},
                "aspect2": {"data": {"fields": [{"name": "col_b"}]}},
            }
        }
        assert extract_column_names_from_entry(entry) == ["col_a", "col_b"]

    def test_no_aspects(self):
        assert extract_column_names_from_entry({}) == []
        assert extract_column_names_from_entry({"aspects": None}) == []

    def test_empty_fields(self):
        entry = {"aspects": {"a": {"data": {"fields": []}}}}
        assert extract_column_names_from_entry(entry) == []

    def test_skips_empty_names(self):
        entry = {
            "aspects": {
                "a": {"data": {"fields": [{"name": ""}, {"name": "valid"}]}}
            }
        }
        assert extract_column_names_from_entry(entry) == ["valid"]


# ---------------------------------------------------------------------------
# _extract_synonym_target
# ---------------------------------------------------------------------------

class TestExtractSynonymTarget:
    def test_matches_synonym_for(self):
        assert _extract_synonym_target("Synonym for brand") == "brand"

    def test_case_insensitive_start(self):
        assert _extract_synonym_target("synonym for country_code") == "country_code"

    def test_with_trailing_text(self):
        assert _extract_synonym_target("Synonym for lat. Some extra text.") == "lat"

    def test_no_synonym(self):
        assert _extract_synonym_target("Unique identifier for a browser") is None

    def test_empty(self):
        assert _extract_synonym_target("") is None

    def test_hyphenated_target(self):
        assert _extract_synonym_target("Synonym for country-code") == "country-code"


# ---------------------------------------------------------------------------
# tokenize_description
# ---------------------------------------------------------------------------

class TestTokenizeDescription:
    def test_filters_stop_words(self):
        tokens = tokenize_description("The value is used for attribution")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "for" not in tokens
        assert "value" in tokens
        assert "attribution" in tokens

    def test_lowercase(self):
        tokens = tokenize_description("SUM of Amount_USD per PAN_TOKEN")
        assert "sum" in tokens
        assert "amount_usd" in tokens
        assert "pan_token" in tokens

    def test_single_char_filtered(self):
        tokens = tokenize_description("A b cc dd")
        assert "cc" in tokens
        assert "dd" in tokens

    def test_empty(self):
        assert tokenize_description("") == []

    def test_only_stop_words(self):
        assert tokenize_description("the a an is of") == []


# ---------------------------------------------------------------------------
# score_column
# ---------------------------------------------------------------------------

class TestScoreColumn:
    def test_exact_match(self):
        score, matched = score_column("amount_usd", "transactions", ["amount_usd"])
        assert score == 10
        assert matched == ["exact:amount_usd"]

    def test_substring_match(self):
        score, matched = score_column("amount_usd", "transactions", ["amount"])
        assert score == 5
        assert matched == ["substr:amount"]

    def test_table_match(self):
        score, matched = score_column("event_id", "pixel_events", ["pixel"])
        assert score == 3
        assert matched == ["table:pixel"]

    def test_multiple_keywords(self):
        score, matched = score_column("amount_usd", "transactions", ["amount", "usd"])
        # "amount" is substring of "amount_usd" => +5
        # "usd" is substring of "amount_usd" => +5
        assert score == 10
        assert len(matched) == 2

    def test_no_match(self):
        score, matched = score_column("campaign_id", "campaigns", ["pixel", "event"])
        assert score == 0
        assert matched == []

    def test_exact_takes_precedence_over_substr(self):
        # If keyword == column_name exactly, it's +10, not +5
        score, matched = score_column("brand", "campaigns", ["brand"])
        assert score == 10
        assert matched == ["exact:brand"]

    def test_combined_column_and_table(self):
        score, matched = score_column("event_type", "pixel_events", ["event", "pixel"])
        # "event" is substring of "event_type" => +5
        # "pixel" is substring of "pixel_events" => +3
        assert score == 8
        assert len(matched) == 2


# ---------------------------------------------------------------------------
# Phase A matching
# ---------------------------------------------------------------------------

class TestPhaseAMatching:
    def _make_manager(self):
        from ingestion.config import Config
        config = Config(
            data_project_id="test-project",
            catalog_project_id="test-project",
            location="us-east1",
        )
        return RelatedEntriesManager(config)

    def test_exact_match(self):
        mgr = self._make_manager()
        term_lookup = {
            "brand": {"displayName": "brand", "description": "The brand name", "category": "Campaign"},
        }
        table_schemas = {
            "campaigns": ["campaign_id", "brand", "advertiser"],
            "creatives": ["creative_id", "brand"],
        }
        matches, matched_terms = mgr._phase_a_matching(term_lookup, table_schemas)
        assert len(matches) == 1
        assert matches[0].term_name == "brand"
        assert "campaigns" in matches[0].found_in_tables
        assert "creatives" in matches[0].found_in_tables
        assert "brand" in matched_terms

    def test_synonym_match(self):
        mgr = self._make_manager()
        term_lookup = {
            "country_code": {"displayName": "country_code", "description": "ISO code", "category": "Campaign"},
            "market": {"displayName": "market", "description": "Synonym for country_code", "category": "Campaign"},
        }
        table_schemas = {
            "campaigns": ["campaign_id", "country_code"],
        }
        matches, matched_terms = mgr._phase_a_matching(term_lookup, table_schemas)
        assert len(matches) == 2
        names = {m.term_name for m in matches}
        assert "country_code" in names
        assert "market" in names
        # market should be via synonym
        market_match = next(m for m in matches if m.term_name == "market")
        assert market_match.via_synonym == "country_code"

    def test_no_matches(self):
        mgr = self._make_manager()
        term_lookup = {
            "impression": {"displayName": "impression", "description": "Ad impression", "category": "Metrics"},
        }
        table_schemas = {
            "campaigns": ["campaign_id", "brand"],
        }
        matches, matched_terms = mgr._phase_a_matching(term_lookup, table_schemas)
        assert len(matches) == 0
        assert "impression" not in matched_terms

    def test_case_insensitive(self):
        mgr = self._make_manager()
        term_lookup = {
            "brand": {"displayName": "brand", "description": "", "category": ""},
        }
        table_schemas = {
            "campaigns": ["Brand"],  # uppercase first letter
        }
        matches, matched_terms = mgr._phase_a_matching(term_lookup, table_schemas)
        assert len(matches) == 1
        assert "brand" in matched_terms


# ---------------------------------------------------------------------------
# Phase B matching
# ---------------------------------------------------------------------------

class TestPhaseBMatching:
    def _make_manager(self):
        from ingestion.config import Config
        config = Config(
            data_project_id="test-project",
            catalog_project_id="test-project",
            location="us-east1",
        )
        return RelatedEntriesManager(config)

    def test_fuzzy_match(self):
        mgr = self._make_manager()
        unmatched = {
            "roas": {
                "displayName": "roas",
                "description": "Return On Ad Spend. Calculated as SUM(transaction amount_usd) / actual_spend_usd.",
                "category": "Marketing Metrics",
            },
        }
        table_schemas = {
            "transactions": ["txn_id", "amount_usd", "pan_token"],
            "campaigns": ["campaign_id", "actual_spend_usd"],
        }
        proposals = mgr._phase_b_matching(unmatched, table_schemas)
        assert len(proposals) > 0
        # amount_usd should be proposed
        table_columns = [p.table_column for p in proposals]
        assert "transactions.amount_usd" in table_columns

    def test_no_description(self):
        mgr = self._make_manager()
        unmatched = {
            "empty": {"displayName": "empty", "description": "", "category": ""},
        }
        table_schemas = {"t": ["col"]}
        proposals = mgr._phase_b_matching(unmatched, table_schemas)
        assert proposals == []

    def test_proposals_sorted_by_score(self):
        mgr = self._make_manager()
        unmatched = {
            "ltv": {
                "displayName": "ltv",
                "description": "Lifetime Value calculated as SUM amount_usd per pan_token",
                "category": "Metrics",
            },
        }
        table_schemas = {
            "transactions": ["amount_usd", "pan_token", "txn_id"],
        }
        proposals = mgr._phase_b_matching(unmatched, table_schemas)
        # Should be sorted descending by score
        scores = [p.score for p in proposals]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# export_proposals_yaml / load_proposals_yaml
# ---------------------------------------------------------------------------

class TestExportAndLoadProposalsYaml:
    def _make_manager(self):
        from ingestion.config import Config
        config = Config(
            data_project_id="test-project",
            catalog_project_id="test-project",
            location="us-east1",
        )
        return RelatedEntriesManager(config)

    def _sample_proposals(self) -> list:
        return [
            FuzzyProposal(
                term_name="impression",
                category="Marketing Metrics",
                description="A single instance of an ad being served.",
                table_column="pixel_events.event_type",
                score=45,
                rationale="exact:event_type",
            ),
            FuzzyProposal(
                term_name="roas",
                category="Marketing Metrics",
                description="Return On Ad Spend.",
                table_column="transactions.amount_usd",
                score=30,
                rationale="substr:amount",
            ),
        ]

    def test_round_trip(self, tmp_path):
        """Export proposals to YAML, then load them back."""
        mgr = self._make_manager()
        output_file = str(tmp_path / "proposals.yaml")

        mgr.export_proposals_yaml(
            fuzzy_proposals=self._sample_proposals(),
            output_path=output_file,
            catalog_name="my-catalog",
            namespace="marketing",
            glossary_id="marketing-glossary",
        )

        doc = RelatedEntriesManager.load_proposals_yaml(output_file)

        assert doc["scan"]["catalog"] == "my-catalog"
        assert doc["scan"]["namespace"] == "marketing"
        assert doc["scan"]["glossary"] == "marketing-glossary"
        assert doc["scan"]["glossary_location"] == "us-east1"
        assert doc["scan"]["glossary_project"] == "test-project"
        assert "scanned_at" in doc["scan"]

        assert len(doc["proposals"]) == 2
        assert doc["proposals"][0]["glossary_term"] == "impression"
        assert doc["proposals"][0]["table"] == "pixel_events"
        assert doc["proposals"][0]["column"] == "event_type"
        assert doc["proposals"][0]["match_score"] == 45
        assert doc["proposals"][1]["glossary_term"] == "roas"
        assert doc["proposals"][1]["table"] == "transactions"
        assert doc["proposals"][1]["column"] == "amount_usd"

    def test_export_empty_proposals(self, tmp_path):
        mgr = self._make_manager()
        output_file = str(tmp_path / "empty.yaml")
        mgr.export_proposals_yaml(
            fuzzy_proposals=[],
            output_path=output_file,
            catalog_name="c",
            namespace=None,
            glossary_id="g",
        )
        doc = RelatedEntriesManager.load_proposals_yaml(output_file)
        assert doc["proposals"] == []

    def test_load_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            RelatedEntriesManager.load_proposals_yaml("/nonexistent/proposals.yaml")

    def test_load_missing_scan_section(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("proposals: []\n")
        with pytest.raises(ValueError, match="Missing required 'scan'"):
            RelatedEntriesManager.load_proposals_yaml(str(bad))

    def test_load_missing_proposals_list(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("scan:\n  catalog: c\n")
        with pytest.raises(ValueError, match="Missing or invalid 'proposals'"):
            RelatedEntriesManager.load_proposals_yaml(str(bad))

    def test_load_missing_required_field(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "scan:\n  catalog: c\nproposals:\n"
            "  - glossary_term: t\n    table: tbl\n    column: ''\n"
        )
        with pytest.raises(ValueError, match="missing required field 'column'"):
            RelatedEntriesManager.load_proposals_yaml(str(bad))

    def test_load_not_a_mapping(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="Expected a YAML mapping"):
            RelatedEntriesManager.load_proposals_yaml(str(bad))


# ---------------------------------------------------------------------------
# _build_biglake_entry_name / _build_glossary_term_entry_name
# ---------------------------------------------------------------------------

class TestBuildEntryNames:
    def test_biglake_entry_name(self):
        result = RelatedEntriesManager._build_biglake_entry_name(
            project="my-project",
            location="us-east1",
            catalog_name="my-catalog",
            namespace="marketing",
            table="pixel_events",
        )
        assert result == (
            "projects/my-project/locations/us-east1"
            "/entryGroups/@biglake/entries/"
            "biglake.googleapis.com/projects/my-project"
            "/catalogs/my-catalog/namespaces/marketing/tables/pixel_events"
        )

    def test_glossary_term_entry_name(self):
        result = RelatedEntriesManager._build_glossary_term_entry_name(
            project="my-project",
            location="us-east1",
            glossary_id="marketing-glossary",
            term_name="impression",
        )
        assert result == (
            "projects/my-project/locations/us-east1"
            "/entryGroups/@glossary/entries/"
            "glossary.googleapis.com/projects/my-project"
            "/locations/us-east1/glossaries/marketing-glossary/terms/impression"
        )

    def test_glossary_term_entry_name_with_underscores(self):
        result = RelatedEntriesManager._build_glossary_term_entry_name(
            project="p",
            location="us-east1",
            glossary_id="g",
            term_name="country_code",
        )
        # underscores become hyphens in the slug
        assert "/terms/country-code" in result


# ---------------------------------------------------------------------------
# apply_proposals (dry-run)
# ---------------------------------------------------------------------------

class TestApplyProposalsDryRun:
    def _make_manager(self):
        from ingestion.config import Config
        config = Config(
            data_project_id="test-project",
            catalog_project_id="test-project",
            location="us-east1",
        )
        return RelatedEntriesManager(config)

    def _write_proposals(self, tmp_path) -> str:
        import yaml
        doc = {
            "scan": {
                "catalog": "my-catalog",
                "namespace": "marketing",
                "glossary": "marketing-glossary",
                "glossary_location": "us-east1",
                "glossary_project": "test-project",
                "scanned_at": "2026-05-23T14:00:00Z",
            },
            "proposals": [
                {
                    "glossary_term": "impression",
                    "category": "Metrics",
                    "description": "Ad impression",
                    "table": "pixel_events",
                    "column": "event_type",
                    "match_score": 45,
                    "match_rationale": "exact:event_type",
                },
                {
                    "glossary_term": "roas",
                    "category": "Metrics",
                    "description": "Return On Ad Spend",
                    "table": "transactions",
                    "column": "amount_usd",
                    "match_score": 30,
                    "match_rationale": "substr:amount",
                },
            ],
        }
        path = str(tmp_path / "proposals.yaml")
        with open(path, "w") as fh:
            yaml.dump(doc, fh, sort_keys=False)
        return path

    def test_dry_run_no_gcloud_calls(self, tmp_path):
        """Dry-run should not invoke any gcloud commands."""
        mgr = self._make_manager()
        proposals_path = self._write_proposals(tmp_path)

        # Patch _run_gcloud to ensure it is NOT called
        from unittest.mock import patch, MagicMock
        with patch.object(mgr, "_run_gcloud") as mock_gcloud:
            results = mgr.apply_proposals(proposals_path, dry_run=True)

        mock_gcloud.assert_not_called()
        assert len(results) == 2
        assert all(r.status == "dry-run" for r in results)
        assert results[0].glossary_term == "impression"
        assert results[0].table_column == "pixel_events.event_type"
        assert results[1].glossary_term == "roas"

    def test_apply_with_overrides(self, tmp_path):
        """Overrides for glossary/project/location are passed through."""
        mgr = self._make_manager()
        proposals_path = self._write_proposals(tmp_path)

        from unittest.mock import patch
        with patch.object(mgr, "_run_gcloud"):
            results = mgr.apply_proposals(
                proposals_path,
                dry_run=True,
                glossary_override="other-glossary",
                project_override="other-project",
                location_override="eu-west1",
            )

        # Check that overrides appear in the detail string
        assert "other-project" in results[0].detail
        assert "other-glossary" in results[0].detail
        assert "eu-west1" in results[0].detail


# ---------------------------------------------------------------------------
# ApplyResult dataclass
# ---------------------------------------------------------------------------

class TestApplyResult:
    def test_default_detail(self):
        r = ApplyResult(glossary_term="t", table_column="t.c", status="created")
        assert r.detail == ""

    def test_with_detail(self):
        r = ApplyResult(glossary_term="t", table_column="t.c", status="error", detail="oops")
        assert r.detail == "oops"
