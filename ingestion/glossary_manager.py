"""
Business Glossary Manager — Dataplex Glossary REST API client.

Parses a markdown glossary definition file and upserts:
  • Glossary          → POST /v1/.../glossaries
  • Categories        → POST /v1/.../glossaries/{id}/categories
  • Terms             → POST /v1/.../glossaries/{id}/terms  (with correct parent)
  • Synonym links     → POST /v1/.../entryGroups/@dataplex/entryLinks  (entry_link_type/synonym)
  • Related-term links→ POST /v1/.../entryGroups/@dataplex/entryLinks  (entry_link_type/related)
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import dataplex_v1

from generators.config import GeneratorConfig


# ---------------------------------------------------------------------------
# Markdown data model
# ---------------------------------------------------------------------------

@dataclass
class GlossaryTermDef:
    """A single term parsed from the glossary markdown."""
    name: str
    display_name: str
    description: str
    synonyms: List[str] = field(default_factory=list)
    related: List[str] = field(default_factory=list)
    tables: List[str] = field(default_factory=list)
    business_context: str = ""


@dataclass
class GlossaryCategoryDef:
    """A category grouping terms, parsed from a ``## Category: …`` heading."""
    name: str
    display_name: str
    description: str
    terms: List[GlossaryTermDef] = field(default_factory=list)


@dataclass
class GlossaryDef:
    """Top-level glossary definition parsed from the markdown file."""
    glossary_id: str
    display_name: str
    description: str
    categories: List[GlossaryCategoryDef] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

def parse_glossary_markdown(path: str) -> GlossaryDef:
    """
    Parse a glossary markdown file into a ``GlossaryDef``.

    Expected format (see ``business_glossaries/glossary.md`` for the canonical
    example):

        # <Glossary Display Name>

        <description paragraph(s)>

        ## Category: <Category Name>

        <optional category description paragraph>

        - **<term_name>**
          - Synonyms: a, b
          - Related: c
          - Description: …
          - Tables: t1, t2
          - Business Context: …
    """
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    glossary_display_name = ""
    glossary_description_lines: list[str] = []
    categories: list[GlossaryCategoryDef] = []
    current_category: Optional[GlossaryCategoryDef] = None
    current_term: Optional[GlossaryTermDef] = None
    in_header = True  # before first category

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        # --- H1: glossary title -------------------------------------------
        if stripped.startswith("# ") and not stripped.startswith("## "):
            glossary_display_name = stripped[2:].strip()
            in_header = True
            continue

        # --- H2: category header ------------------------------------------
        m = re.match(r"^##\s+Category:\s*(.+)$", stripped)
        if m:
            # Flush previous category
            if current_term and current_category:
                current_category.terms.append(current_term)
                current_term = None
            if current_category:
                categories.append(current_category)

            cat_name = m.group(1).strip()
            cat_id = _slugify(cat_name)
            current_category = GlossaryCategoryDef(
                name=cat_id,
                display_name=cat_name,
                description="",
            )
            in_header = False
            continue

        # --- Term bullet: - **term_name** ---------------------------------
        m = re.match(r"^-\s+\*\*(.+?)\*\*\s*$", stripped)
        if m:
            # Flush previous term
            if current_term and current_category:
                current_category.terms.append(current_term)

            term_name = m.group(1).strip()
            current_term = GlossaryTermDef(
                name=_slugify(term_name),
                display_name=term_name,
                description="",
            )
            continue

        # --- Sub-bullets under a term -------------------------------------
        if current_term and stripped.startswith("- "):
            kv = stripped[2:].strip()
            key, _, value = kv.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "synonyms":
                current_term.synonyms = [s.strip() for s in value.split(",") if s.strip()]
            elif key == "related":
                current_term.related = [s.strip() for s in value.split(",") if s.strip()]
            elif key == "description":
                current_term.description = value
            elif key == "tables":
                current_term.tables = [t.strip() for t in value.split(",") if t.strip()]
            elif key == "business context":
                current_term.business_context = value
            continue

        # --- Category description / glossary description ------------------
        if in_header and stripped and not stripped.startswith("#"):
            glossary_description_lines.append(stripped)
        elif current_category and not current_term and stripped and not stripped.startswith("#"):
            if current_category.description:
                current_category.description += " " + stripped
            else:
                current_category.description = stripped

    # Flush last term / category
    if current_term and current_category:
        current_category.terms.append(current_term)
    if current_category:
        categories.append(current_category)

    glossary_id = _slugify(glossary_display_name) if glossary_display_name else "marketing-glossary"

    return GlossaryDef(
        glossary_id=glossary_id,
        display_name=glossary_display_name or "Marketing Business Glossary",
        description=" ".join(glossary_description_lines),
        categories=categories,
    )


def _slugify(text: str) -> str:
    """Convert display text to a Dataplex-compatible resource ID (lowercase, hyphens)."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    # Dataplex IDs must start with a letter
    if slug and not slug[0].isalpha():
        slug = "t-" + slug
    return slug


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class BusinessGlossaryManager:
    """Manages Dataplex Business Glossary resources from a markdown definition."""

    DEFAULT_GLOSSARY_DIR = "business_glossaries"
    DEFAULT_GLOSSARY_FILE = "glossary.md"

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.glossary_client = dataplex_v1.BusinessGlossaryServiceClient()
        self.catalog_client = dataplex_v1.CatalogServiceClient()
        self.parent = f"projects/{config.project_id}/locations/{config.location}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_glossary_from_markdown(
        self,
        input_path: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        """Parse *input_path* and create/update glossary, categories, terms, and links."""
        path = self._resolve_input(input_path)
        glossary_def = parse_glossary_markdown(path)
        print(f"Parsed glossary '{glossary_def.display_name}' "
              f"({sum(len(c.terms) for c in glossary_def.categories)} terms "
              f"in {len(glossary_def.categories)} categories)")

        if dry_run:
            self._print_dry_run(glossary_def)
            return

        # 1. Upsert glossary
        glossary_name = self._upsert_glossary(glossary_def)

        # 2. Upsert categories
        category_names: Dict[str, str] = {}
        for cat_def in glossary_def.categories:
            cat_name = self._upsert_category(glossary_name, cat_def)
            category_names[cat_def.name] = cat_name

        # 3. Upsert terms (under their category)
        term_names: Dict[str, str] = {}  # term slug → full resource name
        for cat_def in glossary_def.categories:
            cat_resource = category_names[cat_def.name]
            for term_def in cat_def.terms:
                term_resource = self._upsert_term(glossary_name, cat_resource, term_def)
                term_names[term_def.name] = term_resource

        # 4. Create synonym links
        self._create_synonym_links(glossary_def, glossary_name, term_names)

        # 5. Create related-term links
        self._create_related_links(glossary_def, glossary_name, term_names)

        print("✅ Glossary creation complete.")

    def validate_glossary(self, input_path: Optional[str] = None) -> bool:
        """Validate that the glossary resources exist in Dataplex."""
        path = self._resolve_input(input_path)
        glossary_def = parse_glossary_markdown(path)

        glossary_resource = f"{self.parent}/glossaries/{glossary_def.glossary_id}"
        ok = True

        # Check glossary
        try:
            self.glossary_client.get_glossary(
                request=dataplex_v1.GetGlossaryRequest(name=glossary_resource)
            )
            print(f"✅ Glossary exists: {glossary_def.glossary_id}")
        except NotFound:
            print(f"❌ Glossary missing: {glossary_def.glossary_id}")
            ok = False
            return ok

        # Check categories
        for cat_def in glossary_def.categories:
            cat_resource = f"{glossary_resource}/categories/{cat_def.name}"
            try:
                self.glossary_client.get_glossary_category(
                    request=dataplex_v1.GetGlossaryCategoryRequest(name=cat_resource)
                )
                print(f"  ✅ Category exists: {cat_def.display_name}")
            except NotFound:
                print(f"  ❌ Category missing: {cat_def.display_name}")
                ok = False

        # Check terms
        for cat_def in glossary_def.categories:
            for term_def in cat_def.terms:
                term_resource = f"{glossary_resource}/terms/{term_def.name}"
                try:
                    self.glossary_client.get_glossary_term(
                        request=dataplex_v1.GetGlossaryTermRequest(name=term_resource)
                    )
                    print(f"    ✅ Term exists: {term_def.display_name}")
                except NotFound:
                    print(f"    ❌ Term missing: {term_def.display_name}")
                    ok = False

        if ok:
            print("✅ Glossary validation passed — all resources present.")
        else:
            print("⚠️  Glossary validation found missing resources.")
        return ok

    def reset_glossary(self, input_path: Optional[str] = None) -> None:
        """Delete all terms, categories, and the glossary itself."""
        path = self._resolve_input(input_path)
        glossary_def = parse_glossary_markdown(path)
        glossary_resource = f"{self.parent}/glossaries/{glossary_def.glossary_id}"

        # Delete terms first (must be empty before categories/glossary can be deleted)
        for cat_def in glossary_def.categories:
            for term_def in cat_def.terms:
                term_resource = f"{glossary_resource}/terms/{term_def.name}"
                try:
                    self.glossary_client.delete_glossary_term(
                        request=dataplex_v1.DeleteGlossaryTermRequest(name=term_resource)
                    )
                    print(f"  Deleted term: {term_def.display_name}")
                except NotFound:
                    pass

        # Delete categories
        for cat_def in glossary_def.categories:
            cat_resource = f"{glossary_resource}/categories/{cat_def.name}"
            try:
                self.glossary_client.delete_glossary_category(
                    request=dataplex_v1.DeleteGlossaryCategoryRequest(name=cat_resource)
                )
                print(f"  Deleted category: {cat_def.display_name}")
            except NotFound:
                pass

        # Delete glossary
        try:
            operation = self.glossary_client.delete_glossary(
                request=dataplex_v1.DeleteGlossaryRequest(name=glossary_resource)
            )
            operation.result()
            print(f"✅ Deleted glossary: {glossary_def.glossary_id}")
        except NotFound:
            print(f"ℹ️  Glossary already absent: {glossary_def.glossary_id}")

    def apply_glossary_to_assets(self, input_path: Optional[str] = None) -> None:
        """Create definition links between glossary terms and BigQuery table columns."""
        path = self._resolve_input(input_path)
        glossary_def = parse_glossary_markdown(path)
        glossary_resource = f"{self.parent}/glossaries/{glossary_def.glossary_id}"

        entry_group = f"{self.parent}/entryGroups/@dataplex"

        for cat_def in glossary_def.categories:
            for term_def in cat_def.terms:
                term_resource = f"{glossary_resource}/terms/{term_def.name}"
                for table in term_def.tables:
                    # BigQuery entry path for the column
                    bq_entry = (
                        f"projects/{self.config.project_id}/locations/{self.config.location}"
                        f"/entryGroups/@bigquery/entries/"
                        f"bigquery.table.`{self.config.project_id}`.{self.config.iceberg_namespace}.{table}"
                    )
                    link_id = f"def-{term_def.name}-{_slugify(table)}"

                    try:
                        entry_link = dataplex_v1.EntryLink(
                            entry_link_type="projects/dataplex-types/locations/global/entryLinkTypes/definition",
                            entry_references=[
                                dataplex_v1.EntryLink.EntryReference(
                                    name=term_resource,
                                    type_=dataplex_v1.EntryLink.EntryReference.Type.SOURCE,
                                ),
                                dataplex_v1.EntryLink.EntryReference(
                                    name=bq_entry,
                                    type_=dataplex_v1.EntryLink.EntryReference.Type.TARGET,
                                ),
                            ],
                        )
                        self.catalog_client.create_entry_link(
                            request=dataplex_v1.CreateEntryLinkRequest(
                                parent=entry_group,
                                entry_link_id=link_id,
                                entry_link=entry_link,
                            )
                        )
                        print(f"  🔗 Linked {term_def.display_name} → {table}")
                    except AlreadyExists:
                        print(f"  ↔️  Link already exists: {term_def.display_name} → {table}")
                    except Exception as e:
                        print(f"  ⚠️  Failed to link {term_def.display_name} → {table}: {e}")

        print("✅ Glossary-to-asset linking complete.")

    def generate_template_files(self) -> None:
        """Create the default glossary markdown template if it doesn't exist."""
        os.makedirs(self.DEFAULT_GLOSSARY_DIR, exist_ok=True)
        dest = os.path.join(self.DEFAULT_GLOSSARY_DIR, self.DEFAULT_GLOSSARY_FILE)

        if os.path.exists(dest):
            print(f"ℹ️  Glossary template already exists: {dest}")
            return

        # Copy the bundled template from the repo
        bundled = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            self.DEFAULT_GLOSSARY_DIR,
            self.DEFAULT_GLOSSARY_FILE,
        )
        if os.path.exists(bundled):
            shutil.copy2(bundled, dest)
            print(f"✅ Created glossary template: {dest}")
        else:
            # Generate a minimal template
            self._write_default_template(dest)
            print(f"✅ Generated glossary template: {dest}")

        print(f"   Edit {dest} then run: manage-glossary --action create")

    # ------------------------------------------------------------------
    # Private helpers — glossary / category / term upsert
    # ------------------------------------------------------------------

    def _upsert_glossary(self, gdef: GlossaryDef) -> str:
        """Create or confirm the glossary. Returns the full resource name."""
        resource = f"{self.parent}/glossaries/{gdef.glossary_id}"
        try:
            self.glossary_client.get_glossary(
                request=dataplex_v1.GetGlossaryRequest(name=resource)
            )
            print(f"ℹ️  Glossary already exists: {gdef.glossary_id}")
            return resource
        except NotFound:
            pass

        glossary = dataplex_v1.Glossary(
            display_name=gdef.display_name,
            description=gdef.description,
        )
        operation = self.glossary_client.create_glossary(
            request=dataplex_v1.CreateGlossaryRequest(
                parent=self.parent,
                glossary_id=gdef.glossary_id,
                glossary=glossary,
            )
        )
        result = operation.result()
        print(f"✅ Created glossary: {gdef.glossary_id}")
        return result.name

    def _upsert_category(self, glossary_name: str, cat_def: GlossaryCategoryDef) -> str:
        """Create or confirm a category. Returns the full resource name."""
        resource = f"{glossary_name}/categories/{cat_def.name}"
        try:
            self.glossary_client.get_glossary_category(
                request=dataplex_v1.GetGlossaryCategoryRequest(name=resource)
            )
            print(f"  ℹ️  Category exists: {cat_def.display_name}")
            return resource
        except NotFound:
            pass

        category = dataplex_v1.GlossaryCategory(
            display_name=cat_def.display_name,
            description=cat_def.description,
            parent=glossary_name,
        )
        result = self.glossary_client.create_glossary_category(
            request=dataplex_v1.CreateGlossaryCategoryRequest(
                parent=glossary_name,
                glossary_category_id=cat_def.name,
                glossary_category=category,
            )
        )
        print(f"  ✅ Created category: {cat_def.display_name}")
        return result.name

    def _upsert_term(
        self,
        glossary_name: str,
        category_name: str,
        term_def: GlossaryTermDef,
    ) -> str:
        """Create or confirm a term under its category. Returns the full resource name."""
        resource = f"{glossary_name}/terms/{term_def.name}"
        try:
            self.glossary_client.get_glossary_term(
                request=dataplex_v1.GetGlossaryTermRequest(name=resource)
            )
            print(f"    ℹ️  Term exists: {term_def.display_name}")
            return resource
        except NotFound:
            pass

        term = dataplex_v1.GlossaryTerm(
            display_name=term_def.display_name,
            description=term_def.description,
            parent=category_name,
        )
        result = self.glossary_client.create_glossary_term(
            request=dataplex_v1.CreateGlossaryTermRequest(
                parent=glossary_name,
                glossary_term_id=term_def.name,
                glossary_term=term,
            )
        )
        print(f"    ✅ Created term: {term_def.display_name}")
        return result.name

    # ------------------------------------------------------------------
    # Private helpers — synonym & related links
    # ------------------------------------------------------------------

    def _create_synonym_links(
        self,
        glossary_def: GlossaryDef,
        glossary_name: str,
        term_names: Dict[str, str],
    ) -> None:
        """Create synonym entryLinks between a canonical term and each of its synonym terms.

        Each synonym is created as its own term in the glossary (if not already
        present), then linked via ``entry_link_type/synonym``.
        """
        entry_group = f"{self.parent}/entryGroups/@dataplex"

        for cat_def in glossary_def.categories:
            for term_def in cat_def.terms:
                canonical_resource = term_names.get(term_def.name)
                if not canonical_resource:
                    continue

                for syn_name in term_def.synonyms:
                    syn_slug = _slugify(syn_name)

                    # Ensure the synonym exists as its own term
                    if syn_slug not in term_names:
                        syn_term = GlossaryTermDef(
                            name=syn_slug,
                            display_name=syn_name,
                            description=f"Synonym for {term_def.display_name}. {term_def.description}",
                        )
                        cat_resource = f"{glossary_name}/categories/{cat_def.name}"
                        syn_resource = self._upsert_term(glossary_name, cat_resource, syn_term)
                        term_names[syn_slug] = syn_resource
                    syn_resource = term_names[syn_slug]

                    # Create the synonym link
                    link_id = f"syn-{term_def.name}-{syn_slug}"
                    try:
                        entry_link = dataplex_v1.EntryLink(
                            entry_link_type="projects/dataplex-types/locations/global/entryLinkTypes/synonym",
                            entry_references=[
                                dataplex_v1.EntryLink.EntryReference(
                                    name=canonical_resource,
                                ),
                                dataplex_v1.EntryLink.EntryReference(
                                    name=syn_resource,
                                ),
                            ],
                        )
                        self.catalog_client.create_entry_link(
                            request=dataplex_v1.CreateEntryLinkRequest(
                                parent=entry_group,
                                entry_link_id=link_id,
                                entry_link=entry_link,
                            )
                        )
                        print(f"    🔗 Synonym link: {term_def.display_name} ↔ {syn_name}")
                    except AlreadyExists:
                        print(f"    ↔️  Synonym link exists: {term_def.display_name} ↔ {syn_name}")
                    except Exception as e:
                        print(f"    ⚠️  Failed synonym link {term_def.display_name} ↔ {syn_name}: {e}")

    def _create_related_links(
        self,
        glossary_def: GlossaryDef,
        glossary_name: str,
        term_names: Dict[str, str],
    ) -> None:
        """Create related-term entryLinks for terms with a ``Related:`` field."""
        entry_group = f"{self.parent}/entryGroups/@dataplex"

        for cat_def in glossary_def.categories:
            for term_def in cat_def.terms:
                canonical_resource = term_names.get(term_def.name)
                if not canonical_resource or not term_def.related:
                    continue

                for rel_name in term_def.related:
                    rel_slug = _slugify(rel_name)
                    rel_resource = term_names.get(rel_slug)

                    if not rel_resource:
                        # Create the related term if it doesn't exist yet
                        rel_term = GlossaryTermDef(
                            name=rel_slug,
                            display_name=rel_name,
                            description=f"Related to {term_def.display_name}.",
                        )
                        cat_resource = f"{glossary_name}/categories/{cat_def.name}"
                        rel_resource = self._upsert_term(glossary_name, cat_resource, rel_term)
                        term_names[rel_slug] = rel_resource

                    link_id = f"rel-{term_def.name}-{rel_slug}"
                    try:
                        entry_link = dataplex_v1.EntryLink(
                            entry_link_type="projects/dataplex-types/locations/global/entryLinkTypes/related",
                            entry_references=[
                                dataplex_v1.EntryLink.EntryReference(
                                    name=canonical_resource,
                                ),
                                dataplex_v1.EntryLink.EntryReference(
                                    name=rel_resource,
                                ),
                            ],
                        )
                        self.catalog_client.create_entry_link(
                            request=dataplex_v1.CreateEntryLinkRequest(
                                parent=entry_group,
                                entry_link_id=link_id,
                                entry_link=entry_link,
                            )
                        )
                        print(f"    🔗 Related link: {term_def.display_name} ↔ {rel_name}")
                    except AlreadyExists:
                        print(f"    ↔️  Related link exists: {term_def.display_name} ↔ {rel_name}")
                    except Exception as e:
                        print(f"    ⚠️  Failed related link {term_def.display_name} ↔ {rel_name}: {e}")

    # ------------------------------------------------------------------
    # Private helpers — misc
    # ------------------------------------------------------------------

    def _resolve_input(self, input_path: Optional[str]) -> str:
        if input_path:
            return input_path
        default = os.path.join(self.DEFAULT_GLOSSARY_DIR, self.DEFAULT_GLOSSARY_FILE)
        if os.path.exists(default):
            return default
        raise FileNotFoundError(
            f"No glossary file found at {default}. "
            "Run 'create-templates' first or pass --input."
        )

    def _print_dry_run(self, gdef: GlossaryDef) -> None:
        print("\n--- DRY RUN (no resources will be created) ---")
        print(f"Glossary: {gdef.display_name} ({gdef.glossary_id})")
        for cat in gdef.categories:
            print(f"  Category: {cat.display_name} ({cat.name})")
            for term in cat.terms:
                print(f"    Term: {term.display_name} ({term.name})")
                if term.synonyms:
                    print(f"      Synonyms: {', '.join(term.synonyms)}")
                if term.related:
                    print(f"      Related: {', '.join(term.related)}")
                if term.tables:
                    print(f"      Tables: {', '.join(term.tables)}")
        print("--- END DRY RUN ---\n")

    @staticmethod
    def _write_default_template(dest: str) -> None:
        """Write a minimal glossary template when no bundled file is available."""
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(
                "# Marketing Business Glossary\n\n"
                "Standardised vocabulary for the Marketing Lakehouse data estate.\n\n"
                "## Category: Identity\n\n"
                "Terms related to user and device identity resolution.\n\n"
                "- **cookie_id**\n"
                "  - Synonyms: visitor_id, device_id\n"
                "  - Description: Unique identifier for a browser or device session.\n"
                "  - Tables: cookie_registry, pixel_events\n"
                "  - Business Context: Identity resolution\n\n"
                "- **hashed_email**\n"
                "  - Synonyms: hem\n"
                "  - Description: SHA-256 hash of a normalised email address.\n"
                "  - Tables: audience, cookie_registry, transactions\n"
                "  - Business Context: Cross-channel attribution\n"
            )
