"""Unit tests for glossary_manager.parse_glossary_markdown()."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ingestion.glossary_manager import parse_glossary_markdown, _slugify


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


class TestParseGlossaryMarkdown:
    """parse_glossary_markdown() correctly converts markdown to GlossaryDef."""

    def test_parses_h1_title(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text("# Marketing Glossary\n\nDescription text.")
        result = parse_glossary_markdown(str(path))
        assert result.display_name == "Marketing Glossary"
        assert result.description == "Description text."
        assert result.glossary_id == "marketing-glossary"

    def test_parses_single_category(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text(
            "# Test Glossary\n\n"
            "## Category: Identity\n\n"
            "Terms for identity resolution.\n\n"
            "- **cookie_id**\n"
            "  - Description: Unique browser identifier.\n"
        )
        result = parse_glossary_markdown(str(path))
        assert len(result.categories) == 1
        assert result.categories[0].name == "identity"
        assert result.categories[0].display_name == "Identity"
        assert result.categories[0].description == "Terms for identity resolution."
        assert len(result.categories[0].terms) == 1
        assert result.categories[0].terms[0].name == "cookie-id"
        assert result.categories[0].terms[0].display_name == "cookie_id"
        assert result.categories[0].terms[0].description == "Unique browser identifier."

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

    def test_parses_term_related(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text(
            "# Test Glossary\n\n"
            "## Category: Identity\n\n"
            "- **cookie_id**\n"
            "  - Related: visitor_id, device_id\n"
        )
        result = parse_glossary_markdown(str(path))
        term = result.categories[0].terms[0]
        assert term.related == ["visitor_id", "device_id"]

    def test_parses_term_tables(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text(
            "# Test Glossary\n\n"
            "## Category: Identity\n\n"
            "- **hem**\n"
            "  - Tables: audience, cookie_registry\n"
        )
        result = parse_glossary_markdown(str(path))
        term = result.categories[0].terms[0]
        assert term.tables == ["audience", "cookie_registry"]

    def test_parses_term_business_context(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text(
            "# Test Glossary\n\n"
            "## Category: Identity\n\n"
            "- **hem**\n"
            "  - Business Context: Used for cross-channel attribution.\n"
        )
        result = parse_glossary_markdown(str(path))
        term = result.categories[0].terms[0]
        assert term.business_context == "Used for cross-channel attribution."

    def test_parses_multiple_categories(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text(
            "# Test Glossary\n\n"
            "## Category: Identity\n\n"
            "- **cookie_id**\n"
            "  - Description: Browser ID.\n\n"
            "## Category: Campaigns\n\n"
            "- **campaign_name**\n"
            "  - Description: Campaign display name.\n"
        )
        result = parse_glossary_markdown(str(path))
        assert len(result.categories) == 2
        assert result.categories[0].name == "identity"
        assert result.categories[1].name == "campaigns"

    def test_parses_multiple_terms_in_category(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text(
            "# Test Glossary\n\n"
            "## Category: Identity\n\n"
            "- **cookie_id**\n"
            "  - Description: Browser ID.\n\n"
            "- **visitor_id**\n"
            "  - Synonyms: cookie_id\n"
            "  - Description: Alias for cookie_id.\n"
        )
        result = parse_glossary_markdown(str(path))
        assert len(result.categories[0].terms) == 2

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            parse_glossary_markdown(str(tmp_path / "nonexistent.md"))

    def test_glossary_id_is_slugified(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text("# My Great Glossary 2024\n\nDescription.")
        result = parse_glossary_markdown(str(path))
        assert result.glossary_id == "my-great-glossary-2024"

    def test_empty_glossary_no_categories(self, tmp_path: Path):
        path = tmp_path / "glossary.md"
        path.write_text("# Empty Glossary\n")
        result = parse_glossary_markdown(str(path))
        assert result.categories == []