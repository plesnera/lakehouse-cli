"""Unit tests for glossary_manager YAML and Markdown parsers."""

from __future__ import annotations

import yaml
from pathlib import Path

import pytest

from lake_cli.glossary_manager import (
    parse_glossary_markdown,
    parse_glossary_yaml,
    _slugify,
)


class TestSlugify:
    """_slugify() converts display text to Dataplex-compatible resource IDs."""

    def test_lowercase_hyphenated(self):
        assert _slugify("Audience ID") == "audience-id"

    def test_special_chars_removed(self):
        assert _slugify("P&L Statement") == "p-l-statement"

    def test_leading_non_alpha_prefixed(self):
        assert _slugify("123 Column") == "t-123-column"

    def test_empty_string(self):
        assert _slugify("") == ""

    def test_already_slug(self):
        assert _slugify("already-slug") == "already-slug"


class TestParseGlossaryYaml:
    """parse_glossary_yaml() correctly converts YAML to GlossaryDef."""

    def _write_yaml(self, tmp_path: Path, data: dict) -> str:
        path = tmp_path / "glossary.yaml"
        path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True))
        return str(path)

    def test_parses_display_name_and_description(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "glossary_id": "marketing-glossary",
                "display_name": "Marketing Glossary",
                "description": "Description text.",
                "categories": [],
            },
        )
        result = parse_glossary_yaml(path)
        assert result.display_name == "Marketing Glossary"
        assert result.description == "Description text."
        assert result.glossary_id == "marketing-glossary"

    def test_parses_single_category(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "display_name": "Test Glossary",
                "categories": [
                    {
                        "name": "identity",
                        "display_name": "Identity",
                        "description": "Terms for identity resolution.",
                        "terms": [
                            {
                                "name": "cookie-id",
                                "display_name": "cookie_id",
                                "description": "Unique browser identifier.",
                            }
                        ],
                    }
                ],
            },
        )
        result = parse_glossary_yaml(path)
        assert len(result.categories) == 1
        assert result.categories[0].name == "identity"
        assert result.categories[0].display_name == "Identity"
        assert result.categories[0].description == "Terms for identity resolution."
        assert len(result.categories[0].terms) == 1
        assert result.categories[0].terms[0].name == "cookie-id"
        assert result.categories[0].terms[0].display_name == "cookie_id"
        assert result.categories[0].terms[0].description == "Unique browser identifier."

    def test_parses_term_synonyms(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "display_name": "Test Glossary",
                "categories": [
                    {
                        "name": "identity",
                        "display_name": "Identity",
                        "terms": [
                            {
                                "name": "hashed-email",
                                "display_name": "hashed_email",
                                "synonyms": ["hem", "email_hash"],
                            }
                        ],
                    }
                ],
            },
        )
        result = parse_glossary_yaml(path)
        term = result.categories[0].terms[0]
        assert term.synonyms == ["hem", "email_hash"]

    def test_parses_term_related(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "display_name": "Test Glossary",
                "categories": [
                    {
                        "name": "identity",
                        "display_name": "Identity",
                        "terms": [
                            {
                                "name": "cookie-id",
                                "display_name": "cookie_id",
                                "related": ["visitor_id", "device_id"],
                            }
                        ],
                    }
                ],
            },
        )
        result = parse_glossary_yaml(path)
        term = result.categories[0].terms[0]
        assert term.related == ["visitor_id", "device_id"]

    def test_parses_term_tables(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "display_name": "Test Glossary",
                "categories": [
                    {
                        "name": "identity",
                        "display_name": "Identity",
                        "terms": [
                            {
                                "name": "hem",
                                "display_name": "hem",
                                "tables": ["audience", "cookie_registry"],
                            }
                        ],
                    }
                ],
            },
        )
        result = parse_glossary_yaml(path)
        term = result.categories[0].terms[0]
        assert term.tables == ["audience", "cookie_registry"]

    def test_parses_term_business_context(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "display_name": "Test Glossary",
                "categories": [
                    {
                        "name": "identity",
                        "display_name": "Identity",
                        "terms": [
                            {
                                "name": "hem",
                                "display_name": "hem",
                                "business_context": "Used for cross-channel attribution.",
                            }
                        ],
                    }
                ],
            },
        )
        result = parse_glossary_yaml(path)
        term = result.categories[0].terms[0]
        assert term.business_context == "Used for cross-channel attribution."

    def test_parses_multiple_categories(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "display_name": "Test Glossary",
                "categories": [
                    {
                        "name": "identity",
                        "display_name": "Identity",
                        "terms": [
                            {"name": "cookie-id", "display_name": "cookie_id"}
                        ],
                    },
                    {
                        "name": "campaigns",
                        "display_name": "Campaigns",
                        "terms": [
                            {
                                "name": "campaign-name",
                                "display_name": "campaign_name",
                            }
                        ],
                    },
                ],
            },
        )
        result = parse_glossary_yaml(path)
        assert len(result.categories) == 2
        assert result.categories[0].name == "identity"
        assert result.categories[1].name == "campaigns"

    def test_parses_multiple_terms_in_category(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "display_name": "Test Glossary",
                "categories": [
                    {
                        "name": "identity",
                        "display_name": "Identity",
                        "terms": [
                            {
                                "name": "cookie-id",
                                "display_name": "cookie_id",
                                "description": "Browser ID.",
                            },
                            {
                                "name": "visitor-id",
                                "display_name": "visitor_id",
                                "synonyms": ["cookie_id"],
                                "description": "Alias for cookie_id.",
                            },
                        ],
                    }
                ],
            },
        )
        result = parse_glossary_yaml(path)
        assert len(result.categories[0].terms) == 2

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            parse_glossary_yaml(str(tmp_path / "nonexistent.yaml"))

    def test_glossary_id_fallback_to_slug(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "display_name": "My Great Glossary 2024",
                "description": "Description.",
                "categories": [],
            },
        )
        result = parse_glossary_yaml(path)
        assert result.glossary_id == "my-great-glossary-2024"

    def test_empty_glossary_no_categories(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "display_name": "Empty Glossary",
                "categories": [],
            },
        )
        result = parse_glossary_yaml(path)
        assert result.categories == []

    def test_auto_generates_name_from_display_name(self, tmp_path: Path):
        path = self._write_yaml(
            tmp_path,
            {
                "display_name": "Test Glossary",
                "categories": [
                    {
                        "display_name": "Identity",
                        "terms": [
                            {"display_name": "cookie_id", "description": "Browser ID."}
                        ],
                    }
                ],
            },
        )
        result = parse_glossary_yaml(path)
        assert result.categories[0].name == "identity"
        assert result.categories[0].terms[0].name == "cookie-id"


class TestParseGlossaryMarkdown:
    """parse_glossary_markdown() correctly converts markdown to GlossaryDef (backward compat)."""

    def test_parses_h1_title(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text("# Marketing Glossary\n\nDescription text.")
        result = parse_glossary_markdown(str(path))
        assert result.display_name == "Marketing Glossary"
        assert result.description == "Description text."
        assert result.glossary_id == "marketing-glossary"

    def test_parses_term_synonyms(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text(
            "# Test Glossary\n\n"
            "## Category: Identity\n\n"
            "- **hashed_email**\n"
            "  - Synonyms: hem, email_hash\n"
            "  - Description: SHA-256 hash of email.\n"
        )
        result = parse_glossary_markdown(str(path))
        term = result.categories[0].terms[0]
        assert term.synonyms == ["hem", "email_hash"]
