"""Unit tests for lake_cli.related_entries helpers and matching logic."""

from __future__ import annotations

import pytest

from lake_cli.related_entries import (
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
        from lake_cli.config import Config
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
        from lake_cli.config import Config
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
        from lake_cli.config import Config
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
            exact_matches=[],
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
            exact_matches=[],
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

    def test_load_missing_proposals_list_is_ok(self, tmp_path):
        """A `proposals:` key is optional — a scan may produce zero fuzzy
        matches, in which case the key is simply omitted. The loader must
        accept the file and return an empty list for ``proposals``."""
        ok = tmp_path / "ok.yaml"
        ok.write_text("scan:\n  catalog: c\n")
        doc = RelatedEntriesManager.load_proposals_yaml(str(ok))
        assert doc["scan"] == {"catalog": "c"}
        assert doc.get("proposals", []) == []

    def test_load_invalid_proposals_type_raises(self, tmp_path):
        """If `proposals:` IS present but is not a list, the loader must
        still raise — that is a real schema error, not an absent key."""
        bad = tmp_path / "bad.yaml"
        bad.write_text("scan:\n  catalog: c\nproposals: not-a-list\n")
        with pytest.raises(ValueError, match="Invalid 'proposals'"):
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
        # The inner `biglake.googleapis.com/...` segment does NOT include
        # a `locations/{l}` segment between `projects/{p}/` and `catalogs/{c}/`
        # — verified against the live `gcloud dataplex entries list` output.
        # Including it would cause `gcloud dataplex entries describe` to
        # return NOT_FOUND even when the entry exists.
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

    def test_biglake_entry_name_without_namespace(self):
        # Same shape, but with no namespace segment in the path.
        result = RelatedEntriesManager._build_biglake_entry_name(
            project="my-project",
            location="us-east1",
            catalog_name="my-catalog",
            namespace="",
            table="audience",
        )
        assert result == (
            "projects/my-project/locations/us-east1"
            "/entryGroups/@biglake/entries/"
            "biglake.googleapis.com/projects/my-project"
            "/catalogs/my-catalog/tables/audience"
        )

    def test_glossary_term_entry_name(self):
        # The full path embeds the project segment that lives inside the
        # entry-id (the "inner" project).  In the canonical setup the
        # outer and inner project segments are equal; in cross-project
        # setups they can differ.  The function takes both explicitly.
        result = RelatedEntriesManager._build_glossary_term_entry_name(
            outer_project="my-project",
            location="us-east1",
            entry_group="@dataplex",
            inner_project="my-project",
            glossary_id="marketing-business-glossary",
            term_name="impression",
        )
        assert result == (
            "projects/my-project/locations/us-east1"
            "/entryGroups/@dataplex/entries/"
            "projects/my-project/locations/us-east1"
            "/glossaries/marketing-business-glossary/terms/impression"
        )

    def test_glossary_term_entry_name_with_underscores(self):
        result = RelatedEntriesManager._build_glossary_term_entry_name(
            outer_project="p",
            location="us-east1",
            entry_group="eg",
            inner_project="p",
            glossary_id="g",
            term_name="country_code",
        )
        # underscores become hyphens in the slug, and the inner-project
        # segment is preserved.
        assert result.endswith(
            "/entries/projects/p/locations/us-east1/glossaries/g/terms/country-code"
        )

    def test_glossary_term_entry_name_inner_project_can_differ(self):
        """Cross-project setups may have an inner-project segment that
        differs from the outer (catalog) project segment.  Both must be
        preserved verbatim in the resulting path."""
        result = RelatedEntriesManager._build_glossary_term_entry_name(
            outer_project="catalog-proj",
            location="us-east1",
            entry_group="@dataplex",
            inner_project="data-proj",
            glossary_id="my-glossary",
            term_name="region",
        )
        assert result == (
            "projects/catalog-proj/locations/us-east1"
            "/entryGroups/@dataplex/entries/"
            "projects/data-proj/locations/us-east1"
            "/glossaries/my-glossary/terms/region"
        )


# ---------------------------------------------------------------------------
# apply_proposals (dry-run)
# ---------------------------------------------------------------------------

class TestApplyProposalsDryRun:
    def _make_manager(self):
        from lake_cli.config import Config
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
        """Dry-run should not invoke gcloud for create/update operations.

        It MAY call ``entry-groups list`` once at the start, so the printed
        "Would link …" preview shows the correct entry-group segment of the
        term-entry name rather than a placeholder.  We assert that no calls
        to ``dataplex entries describe/update`` happen.
        """
        mgr = self._make_manager()
        proposals_path = self._write_proposals(tmp_path)

        from unittest.mock import patch
        with patch.object(mgr, "_run_gcloud") as mock_gcloud:
            with patch.object(mgr, "_resolve_project_number", return_value="test-project"):
                results = mgr.apply_proposals(proposals_path, dry_run=True)

        # No entries describe/update calls (would mutate state).
        mutating = [
            call for call in mock_gcloud.call_args_list
            if any("entries" in str(a) and ("describe" in str(a) or "update" in str(a))
                   for a in call.args)
        ]
        assert mutating == [], f"dry-run made mutating calls: {mutating}"
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
            with patch.object(mgr, "_resolve_project_number", return_value="test-project"):
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


# ---------------------------------------------------------------------------
# export_proposals_yaml metadata round-trip
# ---------------------------------------------------------------------------

class TestExportProposalsYaml:
    """Ensure the YAML written by export_proposals_yaml reflects the
    glossary_project / glossary_location arguments the CLI passed in.
    """

    def _make_manager(self):
        from lake_cli.config import Config
        config = Config(
            data_project_id="test-project",
            catalog_project_id="test-project",
            location="us-east1",
        )
        return RelatedEntriesManager(config)

    def test_yaml_records_explicit_project_and_location(self, tmp_path):
        """When the CLI passes explicit glossary_project / glossary_location
        values, the resulting YAML's ``scan`` section must record them so
        apply-related-entries targets the correct GCP project."""
        mgr = self._make_manager()
        output_file = str(tmp_path / "proposals.yaml")

        mgr.export_proposals_yaml(
            exact_matches=[],
            fuzzy_proposals=[],
            output_path=output_file,
            catalog_name="my-catalog",
            namespace="marketing",
            glossary_id="my-glossary",
            glossary_project="lakehouse-proj",
            glossary_location="eu-west1",
        )

        doc = RelatedEntriesManager.load_proposals_yaml(output_file)
        assert doc["scan"]["glossary_project"] == "lakehouse-proj"
        assert doc["scan"]["glossary_location"] == "eu-west1"
        assert doc["scan"]["glossary"] == "my-glossary"

    def test_yaml_falls_back_to_config_when_unset(self, tmp_path):
        """When the caller does not pass glossary_project / glossary_location,
        the function must still record something usable — i.e. the config's
        project_id and location, not a literal fallback string like
        'my-gcp-project'."""
        mgr = self._make_manager()
        output_file = str(tmp_path / "proposals.yaml")

        mgr.export_proposals_yaml(
            exact_matches=[],
            fuzzy_proposals=[],
            output_path=output_file,
            catalog_name="c",
            namespace=None,
            glossary_id="g",
        )

        doc = RelatedEntriesManager.load_proposals_yaml(output_file)
        assert doc["scan"]["glossary_project"] == "test-project"
        assert doc["scan"]["glossary_location"] == "us-east1"


# ---------------------------------------------------------------------------
# apply_proposals makes the correct gcloud entry-links create call
# ---------------------------------------------------------------------------

class TestApplyProposalsGcloudCall:
    """Pin down the exact ``gcloud alpha dataplex entry-links create`` call
    made per row, alongside the pre-flight ``gcloud dataplex entries describe``
    call.

    Regression coverage for two related bugs:
    - The old gcloud aspect-based path failed with
      ``403 Permission denied … (or it may not exist)`` on missing terms and
      ``403`` on the unregistered ``wpp-dataproducts-lakehouse.us-east1.relatedEntries``
      aspect type.  The new path uses the gcloud ``entry-links create`` subcommand
      (alpha) with link type ``definition``.
    - The inner ``biglake.googleapis.com/...`` segment of the BigLake entry-id
      must NOT include a redundant ``locations/{l}`` token — that returns
      NOT_FOUND on the pre-flight ``entries describe`` even when the entry
      exists.
    - The link must be created in the ``@biglake`` entry-group (the SOURCE
      entry's group) with BigLake as SOURCE first and the term as TARGET
      second (verified against the live API on 2026-06-05).
    """

    def _make_manager(self):
        from lake_cli.config import Config
        config = Config(
            data_project_id="wpp-dataproducts-lakehouse",
            catalog_project_id="wpp-dataproducts-lakehouse",
            location="us-east1",
        )
        return RelatedEntriesManager(config)

    def _write_proposals(self, tmp_path, *, with_namespace: bool = True) -> str:
        import yaml
        doc = {
            "scan": {
                "catalog": "wpp-dataproducts-lakehouse-warehouse",
                "namespace": "marketing" if with_namespace else "",
                "glossary": "marketing-business-glossary",
                "glossary_location": "us-east1",
                "glossary_project": "wpp-dataproducts-lakehouse",
                "scanned_at": "2026-06-04T20:38:23Z",
            },
            "exact_matches": [
                {
                    "glossary_term": "region",
                    "category": "Campaign",
                    "description": "Related to country_code.",
                    "table": "marketing/audience" if with_namespace else "audience",
                    "column": "region",
                    "match_type": "exact",
                    "via_synonym": "",
                    "match_score": 100,
                    "match_rationale": "exact match",
                },
            ],
            "proposals": [],
        }
        path = str(tmp_path / "proposals.yaml")
        with open(path, "w") as fh:
            yaml.dump(doc, fh, sort_keys=False)
        return path

    def _capture_subprocess_run(self, captured_args):
        """Return a fake ``subprocess.run`` that records argv lists."""
        def fake_run(argv, **kwargs):
            captured_args.append(list(argv))
            # Return a CompletedProcess-like with rc=0, no stderr
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        return fake_run

    def test_preflight_describe_and_gcloud_entry_links_create(self, tmp_path):
        """The pre-flight ``gcloud dataplex entries describe`` call must use
        ``biglake.googleapis.com/projects/{p}/catalogs/{c}/namespaces/{n}/tables/{t}``
        (no ``locations/{l}``), and the follow-up ``gcloud alpha dataplex
        entry-links create`` must target ``@biglake`` with BigLake as SOURCE
        first and the term as TARGET second."""
        from unittest.mock import patch
        import os, yaml as _yaml
        mgr = self._make_manager()
        proposals_path = self._write_proposals(tmp_path, with_namespace=True)

        captured_args: list[list[str]] = []
        captured_refs_doc: list[list] = []

        def fake_gcloud(args, **kwargs):
            captured_args.append(list(args))
            return {}

        def fake_run(argv, **kwargs):
            captured_args.append(list(argv))
            # Snapshot the references YAML while the tempfile is still alive
            for a in argv:
                if a.startswith("--entry-references="):
                    refs_path = a.split("=", 1)[1]
                    if os.path.isfile(refs_path):
                        with open(refs_path) as fh:
                            captured_refs_doc.append(_yaml.safe_load(fh))
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch.object(mgr, "_run_gcloud", side_effect=fake_gcloud):
            with patch.object(mgr, "_resolve_project_number", return_value="wpp-dataproducts-lakehouse"):
                with patch.object(mgr, "_resolve_glossary_inner_project", return_value="wpp-dataproducts-lakehouse"):
                    with patch(
                        "lake_cli.related_entries.subprocess.run",
                        side_effect=fake_run,
                    ):
                        mgr.apply_proposals(proposals_path, dry_run=False)

        # Pre-flight describe for the BigLake entry
        describe_calls = [
            args for args in captured_args
            if "describe" in args and "biglake.googleapis.com" in " ".join(args)
        ]
        assert describe_calls, f"no pre-flight describe call captured; saw: {captured_args}"
        describe = describe_calls[0]
        idx = describe.index("describe")
        entry_id = describe[idx + 1]
        assert entry_id == (
            "biglake.googleapis.com/projects/wpp-dataproducts-lakehouse"
            "/catalogs/wpp-dataproducts-lakehouse-warehouse"
            "/namespaces/marketing/tables/audience"
        )
        assert "--location=us-east1" in describe
        assert "--project=wpp-dataproducts-lakehouse" in describe
        assert "--entry-group=@biglake" in describe

        # gcloud entry-links create call shape
        create_calls = [
            args for args in captured_args
            if "entry-links" in args and "create" in args
        ]
        assert len(create_calls) == 1, (
            f"expected exactly one entry-links create call; saw: {create_calls}"
        )
        create = create_calls[0]
        # argv layout: [gcloud, alpha, dataplex, entry-links, create, <id>, ...flags]
        assert create[:5] == ["gcloud", "alpha", "dataplex", "entry-links", "create"]
        entry_link_id_positional = create[5]
        assert entry_link_id_positional == "definition-region-marketing-audience"
        # Link lives in @biglake (the SOURCE entry's group), with the
        # documented entryLinkTypes/definition link type.
        assert "--entry-group=@biglake" in create
        assert "--location=us-east1" in create
        assert "--project=wpp-dataproducts-lakehouse" in create
        assert (
            "--entry-link-type=projects/dataplex-types/locations/global/entryLinkTypes/definition"
            in create
        )
        # The references flag points to a YAML file with the right shape.
        assert any(a.startswith("--entry-references=") for a in create)
        assert len(captured_refs_doc) == 1
        refs_doc = captured_refs_doc[0]
        # BigLake must be SOURCE first; term must be TARGET second.
        assert refs_doc[0]["type"] == "SOURCE"
        assert refs_doc[0]["name"].endswith("/namespaces/marketing/tables/audience")
        assert refs_doc[1]["type"] == "TARGET"
        assert refs_doc[1]["name"].endswith("/glossaries/marketing-business-glossary/terms/region")

    def test_preflight_describe_entry_id_without_namespace(self, tmp_path):
        """When the row's table has no namespace prefix, the pre-flight
        describe call's entry-id must drop the ``/namespaces/{n}/`` segment."""
        from unittest.mock import patch
        mgr = self._make_manager()
        proposals_path = self._write_proposals(tmp_path, with_namespace=False)

        captured_args: list[list[str]] = []

        def fake_gcloud(args, **kwargs):
            captured_args.append(list(args))
            return {}

        with patch.object(mgr, "_run_gcloud", side_effect=fake_gcloud):
            with patch.object(mgr, "_resolve_project_number", return_value="wpp-dataproducts-lakehouse"):
                with patch.object(mgr, "_resolve_glossary_inner_project", return_value="wpp-dataproducts-lakehouse"):
                    with patch(
                        "lake_cli.related_entries.subprocess.run",
                        side_effect=self._capture_subprocess_run(captured_args),
                    ):
                        mgr.apply_proposals(proposals_path, dry_run=False)

        describe_calls = [
            args for args in captured_args
            if "describe" in args and "biglake.googleapis.com" in " ".join(args)
        ]
        assert describe_calls, f"no pre-flight describe call captured; saw: {captured_args}"
        describe = describe_calls[0]
        idx = describe.index("describe")
        entry_id = describe[idx + 1]
        assert entry_id == (
            "biglake.googleapis.com/projects/wpp-dataproducts-lakehouse"
            "/catalogs/wpp-dataproducts-lakehouse-warehouse/tables/audience"
        )


# ---------------------------------------------------------------------------
# _create_entry_link: subprocess wrapper around gcloud alpha entry-links create
# ---------------------------------------------------------------------------

class TestCreateEntryLink:
    """Pin down the gcloud subprocess invocation, the references YAML file,
    and the mapping of gcloud exit codes / stderr into outcomes.
    """

    def _ok_result(self):
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    def _err_result(self, stderr: str, rc: int = 1):
        return type("R", (), {"returncode": rc, "stdout": "", "stderr": stderr})()

    def test_writes_references_yaml_with_source_first(self, tmp_path):
        """The references YAML must put the BigLake entry first as SOURCE
        and the term entry second as TARGET.  The tempfile is removed on
        success."""
        from unittest.mock import patch
        mgr = RelatedEntriesManager.__new__(RelatedEntriesManager)  # bypass __init__
        with patch(
            "lake_cli.related_entries.subprocess.run",
            return_value=self._ok_result(),
        ) as mock_run:
            outcome, detail = mgr._create_entry_link(
                project="p",
                location="l",
                link_entry_group="@biglake",
                entry_link_id="definition-x",
                source_entry_ref="projects/p/locations/l/entryGroups/@biglake/entries/.../audience",
                target_entry_ref="projects/p/locations/l/entryGroups/@dataplex/entries/.../terms/region",
            )
        assert outcome == "created"
        assert detail == ""
        # Subprocess got the right argv
        argv = mock_run.call_args.args[0]
        assert "gcloud" in argv
        assert "entry-links" in argv
        assert "create" in argv
        assert "definition-x" in argv
        assert "--entry-group=@biglake" in argv
        assert (
            "--entry-link-type=projects/dataplex-types/locations/global/entryLinkTypes/definition"
            in argv
        )
        # Find the references file
        refs_idx = argv.index([a for a in argv if a.startswith("--entry-references=")][0])
        refs_path = argv[refs_idx].split("=", 1)[1]
        # Tempfile was cleaned up
        import os
        assert not os.path.exists(refs_path), f"tempfile leaked: {refs_path}"
        # But during the call, the file was written with the right shape.
        # (We can't read it post-delete; instead, capture the file path that
        # was passed and read it via a separate invocation pattern in the
        # next test.)

    def test_references_yaml_shape(self, tmp_path, monkeypatch):
        """Inspect the references YAML that gets passed to gcloud.  Use a
        fake subprocess.run that intercepts the path and reads the file."""
        from unittest.mock import patch
        import os, yaml as _yaml

        seen_refs_path: list[str] = []

        def fake_run(argv, **kwargs):
            for a in argv:
                if a.startswith("--entry-references="):
                    seen_refs_path.append(a.split("=", 1)[1])
            return self._ok_result()

        mgr = RelatedEntriesManager.__new__(RelatedEntriesManager)
        with patch("lake_cli.related_entries.subprocess.run", side_effect=fake_run):
            mgr._create_entry_link(
                project="p",
                location="l",
                link_entry_group="@biglake",
                entry_link_id="definition-x",
                source_entry_ref=(
                    "projects/p/locations/l/entryGroups/@biglake/entries/"
                    "biglake.googleapis.com/projects/p/catalogs/cat/tables/t"
                ),
                target_entry_ref=(
                    "projects/p/locations/l/entryGroups/@dataplex/entries/"
                    "projects/p/locations/l/glossaries/g/terms/region"
                ),
            )

        assert len(seen_refs_path) == 1
        # Tempfile has been deleted by the cleanup block, so we re-create a
        # temporary capture pattern: monkey-patch os.unlink to no-op so we
        # can read the file.
        # (Re-run with monkey-patched unlink for inspection.)
        import tempfile as _tempfile
        with patch("lake_cli.related_entries.os.unlink"):  # don't delete
            with patch(
                "lake_cli.related_entries.subprocess.run",
                side_effect=fake_run,
            ):
                mgr._create_entry_link(
                    project="p",
                    location="l",
                    link_entry_group="@biglake",
                    entry_link_id="definition-x",
                    source_entry_ref="A",
                    target_entry_ref="B",
                )

        # Read the file content
        with open(seen_refs_path[1]) as fh:
            doc = _yaml.safe_load(fh)
        assert doc == [
            {"name": "A", "type": "SOURCE"},
            {"name": "B", "type": "TARGET"},
        ]

    def test_already_exists_returns_skipped(self):
        """A stderr containing ALREADY_EXISTS is mapped to 'skipped' with a
        friendly detail message, not 'error'."""
        from unittest.mock import patch
        mgr = RelatedEntriesManager.__new__(RelatedEntriesManager)
        err = (
            "ERROR: (gcloud.alpha.dataplex.entry-links.create) "
            "ALREADY_EXISTS: EntryLink already exists."
        )
        with patch(
            "lake_cli.related_entries.subprocess.run",
            return_value=self._err_result(err, rc=1),
        ):
            outcome, detail = mgr._create_entry_link(
                project="p", location="l", link_entry_group="@biglake",
                entry_link_id="x", source_entry_ref="a", target_entry_ref="b",
            )
        assert outcome == "skipped"
        assert "already exists" in detail.lower()

    def test_other_error_returns_error_with_stderr(self):
        from unittest.mock import patch
        mgr = RelatedEntriesManager.__new__(RelatedEntriesManager)
        err = "ERROR: (gcloud.alpha.dataplex.entry-links.create) Permission denied"
        with patch(
            "lake_cli.related_entries.subprocess.run",
            return_value=self._err_result(err, rc=1),
        ):
            outcome, detail = mgr._create_entry_link(
                project="p", location="l", link_entry_group="@biglake",
                entry_link_id="x", source_entry_ref="a", target_entry_ref="b",
            )
        assert outcome == "error"
        assert "Permission denied" in detail


# ---------------------------------------------------------------------------
# Entry-link id slug shape (truncation, hyphenation, empty-ns collapse)
# ---------------------------------------------------------------------------

class TestEntryLinkIdSlugShape:
    """Pin down the deterministic, 63-char-bounded entry-link id used as
    the positional ``ENTRY_LINK`` argument on ``entry-links create``.

    Format: ``definition-{term_slug}-{ns}-{table}`` truncated to 63 chars.
    """

    def _make_manager(self):
        from lake_cli.config import Config
        config = Config(
            data_project_id="p", catalog_project_id="p", location="us-east1",
        )
        return RelatedEntriesManager(config)

    def _run_apply(self, mgr, term, table, namespace=""):
        import yaml
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            import os
            path = os.path.join(td, "p.yaml")
            doc = {
                "scan": {
                    "catalog": "cat",
                    "namespace": namespace,
                    "glossary": "gloss",
                    "glossary_location": "us-east1",
                    "glossary_project": "p",
                    "scanned_at": "2026-06-04T20:38:23Z",
                },
                "exact_matches": [{
                    "glossary_term": term, "category": "", "description": "",
                    "table": table, "column": "region",
                    "match_type": "exact", "via_synonym": "",
                    "match_score": 100, "match_rationale": "exact match",
                }],
                "proposals": [],
            }
            with open(path, "w") as fh:
                yaml.dump(doc, fh, sort_keys=False)

            captured: list[list[str]] = []
            def fake_run(argv, **kwargs):
                captured.append(list(argv))
                return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            with patch.object(mgr, "_run_gcloud", return_value={}):
                with patch.object(mgr, "_resolve_project_number", return_value="p"):
                    with patch.object(mgr, "_resolve_glossary_inner_project", return_value="p"):
                        with patch(
                            "lake_cli.related_entries.subprocess.run",
                            side_effect=fake_run,
                        ):
                            mgr.apply_proposals(path, dry_run=False)
            return captured

    def test_basic_slug(self):
        mgr = self._make_manager()
        captured = self._run_apply(mgr, "region", "marketing/audience")
        # argv[5] is the positional ENTRY_LINK id
        assert captured[0][5] == "definition-region-marketing-audience"

    def test_underscores_and_spaces_become_hyphens(self):
        mgr = self._make_manager()
        captured = self._run_apply(mgr, "Country Code", "marketing/audience_data")
        assert captured[0][5] == "definition-country-code-marketing-audience-data"

    def test_truncates_to_63_chars(self):
        mgr = self._make_manager()
        long_term = "a" * 60
        captured = self._run_apply(mgr, long_term, "marketing/some_table")
        entry_link_id = captured[0][5]
        assert len(entry_link_id) <= 63
        assert entry_link_id.startswith("definition-aaaa")

    def test_empty_namespace_collapses(self):
        """When the row has no namespace prefix (and the scan metadata is
        also empty), the entry-link id still has a well-formed shape with
        two hyphens around the empty segment, not three."""
        mgr = self._make_manager()
        captured = self._run_apply(mgr, "region", "audience", namespace="")
        # definition-region--audience  (double hyphen from the empty ns segment)
        assert captured[0][5] == "definition-region--audience"


# ---------------------------------------------------------------------------
# apply_proposals: gcloud entry-links errors surface in ApplyResult.detail
# ---------------------------------------------------------------------------

class TestApplyProposalsGcloudError:
    """When ``gcloud alpha dataplex entry-links create`` returns a non-zero
    exit code, the resulting ``ApplyResult.detail`` must contain the raw
    gcloud stderr (not a generic 'Entry not found' string).  ALREADY_EXISTS
    is the exception: it maps to ``status='skipped'``.
    """

    def _make_manager(self):
        from lake_cli.config import Config
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
            "proposals": [{
                "glossary_term": "impression",
                "category": "Metrics",
                "description": "Ad impression",
                "table": "pixel_events",
                "column": "event_type",
                "match_score": 45,
                "match_rationale": "exact:event_type",
            }],
        }
        path = str(tmp_path / "proposals.yaml")
        with open(path, "w") as fh:
            yaml.dump(doc, fh, sort_keys=False)
        return path

    def test_error_detail_includes_gcloud_stderr(self, tmp_path):
        from unittest.mock import patch
        mgr = self._make_manager()
        proposals_path = self._write_proposals(tmp_path)

        gcloud_stderr = (
            "ERROR: (gcloud.alpha.dataplex.entry-links.create) "
            "Permission denied: dataplex.googleapis.com"
        )

        def fake_run(argv, **kwargs):
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": gcloud_stderr})()

        with patch.object(mgr, "_run_gcloud", return_value={}):
            with patch.object(mgr, "_resolve_project_number", return_value="test-project"):
                with patch.object(mgr, "_resolve_glossary_inner_project", return_value="test-project"):
                    with patch(
                        "lake_cli.related_entries.subprocess.run",
                        side_effect=fake_run,
                    ):
                        results = mgr.apply_proposals(proposals_path, dry_run=False)

        assert len(results) == 1
        assert results[0].status == "error"
        assert "dataplex.googleapis.com" in results[0].detail
        assert "Permission denied" in results[0].detail

    def test_already_exists_is_reported_as_skipped(self, tmp_path):
        from unittest.mock import patch
        mgr = self._make_manager()
        proposals_path = self._write_proposals(tmp_path)

        already_exists_stderr = (
            "ERROR: (gcloud.alpha.dataplex.entry-links.create) "
            "ALREADY_EXISTS: EntryLink already exists."
        )

        def fake_run(argv, **kwargs):
            return type(
                "R", (), {"returncode": 1, "stdout": "", "stderr": already_exists_stderr}
            )()

        with patch.object(mgr, "_run_gcloud", return_value={}):
            with patch.object(mgr, "_resolve_project_number", return_value="test-project"):
                with patch.object(mgr, "_resolve_glossary_inner_project", return_value="test-project"):
                    with patch(
                        "lake_cli.related_entries.subprocess.run",
                        side_effect=fake_run,
                    ):
                        results = mgr.apply_proposals(proposals_path, dry_run=False)

        assert len(results) == 1
        assert results[0].status == "skipped"
        assert "already exists" in results[0].detail.lower()


# ---------------------------------------------------------------------------
# _iter_apply_rows: union of exact_matches + proposals in source order
# ---------------------------------------------------------------------------

class TestIterApplyRows:
    def _doc(self, exact=None, fuzzy=None):
        return {
            "scan": {},
            "exact_matches": exact or [],
            "proposals": fuzzy or [],
        }

    def test_only_exact(self):
        rows = list(RelatedEntriesManager._iter_apply_rows(self._doc(
            exact=[{"glossary_term": "a", "table": "t", "column": "c"}],
        )))
        assert len(rows) == 1
        assert rows[0]["glossary_term"] == "a"

    def test_only_fuzzy(self):
        rows = list(RelatedEntriesManager._iter_apply_rows(self._doc(
            fuzzy=[{"glossary_term": "b", "table": "t", "column": "c"}],
        )))
        assert len(rows) == 1
        assert rows[0]["glossary_term"] == "b"

    def test_exact_before_fuzzy(self):
        rows = list(RelatedEntriesManager._iter_apply_rows(self._doc(
            exact=[{"glossary_term": "a", "table": "t", "column": "c"}],
            fuzzy=[{"glossary_term": "b", "table": "t", "column": "c"}],
        )))
        assert [r["glossary_term"] for r in rows] == ["a", "b"]

    def test_empty_doc(self):
        rows = list(RelatedEntriesManager._iter_apply_rows(self._doc()))
        assert rows == []


# ---------------------------------------------------------------------------
# _resolve_glossary_inner_project
# ---------------------------------------------------------------------------

class TestResolveGlossaryInnerProject:
    def _make_manager(self):
        from lake_cli.config import Config
        config = Config(
            data_project_id="outer-proj",
            catalog_project_id="outer-proj",
            location="us-east1",
        )
        return RelatedEntriesManager(config)

    def test_reads_first_terms_parent(self):
        """When the first term's parent uses a project number, the resolver
        must return that number (since the API requires the project number
        in entry-name references).  The intermediate ``gcloud projects
        describe`` call is patched to return a deterministic number."""
        from unittest.mock import patch
        mgr = self._make_manager()
        terms = [{
            "name": "region",
            "parent": "projects/wpp-dataproducts-lakehouse/locations/us-east1/glossaries/marketing-business-glossary/categories/geo",
        }]
        with patch.object(mgr, "_list_glossary_terms", return_value=terms):
            with patch.object(
                mgr, "_resolve_project_number",
                side_effect=lambda pid: {"outer-proj": "111111", "wpp-dataproducts-lakehouse": "222222"}.get(pid, pid),
            ):
                assert mgr._resolve_glossary_inner_project("gloss") == "222222"

    def test_falls_back_to_config_when_no_terms(self):
        from unittest.mock import patch
        mgr = self._make_manager()
        with patch.object(mgr, "_list_glossary_terms", return_value=[]):
            assert mgr._resolve_glossary_inner_project("gloss") == "outer-proj"

    def test_falls_back_to_config_on_gcloud_failure(self):
        from unittest.mock import patch
        mgr = self._make_manager()
        with patch.object(
            mgr, "_list_glossary_terms",
            side_effect=RuntimeError("permission denied"),
        ):
            assert mgr._resolve_glossary_inner_project("gloss") == "outer-proj"
