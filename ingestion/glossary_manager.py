"""
Business Glossary Manager — Dataplex Glossary REST API client.
https://docs.cloud.google.com/dataplex/docs/manage-glossaries

Parses a YAML glossary definition file and upserts:
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

import yaml

from google.api_core.exceptions import AlreadyExists, NotFound
from google.cloud import dataplex_v1

from generators.config import GeneratorConfig


# ---------------------------------------------------------------------------
# Data model
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

    Expected format (see ``metadata/glossary.yaml`` for the canonical
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
# YAML parser
# ---------------------------------------------------------------------------

def parse_glossary_yaml(path: str) -> GlossaryDef:
    """Parse a glossary YAML file into a :class:`GlossaryDef`."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    glossary_id = data.get("glossary_id") or _slugify(data.get("display_name", "marketing-business-glossary"))
    categories: list[GlossaryCategoryDef] = []

    for cat_data in data.get("categories", []):
        terms: list[GlossaryTermDef] = []
        for term_data in cat_data.get("terms", []):
            terms.append(
                GlossaryTermDef(
                    name=term_data.get("name", _slugify(term_data.get("display_name", ""))),
                    display_name=term_data.get("display_name", ""),
                    description=term_data.get("description", ""),
                    synonyms=term_data.get("synonyms", []),
                    related=term_data.get("related", []),
                    tables=term_data.get("tables", []),
                    business_context=term_data.get("business_context", ""),
                )
            )
        categories.append(
            GlossaryCategoryDef(
                name=cat_data.get("name", _slugify(cat_data.get("display_name", ""))),
                display_name=cat_data.get("display_name", ""),
                description=cat_data.get("description", ""),
                terms=terms,
            )
        )

    return GlossaryDef(
        glossary_id=glossary_id,
        display_name=data.get("display_name", "Marketing Business Glossary"),
        description=data.get("description", ""),
        categories=categories,
    )


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class BusinessGlossaryManager:
    """Manages Dataplex Business Glossary resources from a YAML definition."""

    DEFAULT_GLOSSARY_DIR = "metadata"
    DEFAULT_GLOSSARY_FILE = "glossary.yaml"

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.glossary_client = dataplex_v1.BusinessGlossaryServiceClient()
        self.catalog_client = dataplex_v1.CatalogServiceClient()
        self.parent = f"projects/{config.project_id}/locations/{config.location}"
        self.project_number = self._get_project_number(config.project_id)

    def _get_project_number(self, project_id: str) -> str:
        """Fetches the GCP project number for a given project ID."""
        import subprocess
        try:
            result = subprocess.run(
                ["gcloud", "projects", "describe", project_id, "--format=value(projectNumber)"],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  🚨 Error fetching project number for '{project_id}': {e}")
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _parse_glossary_file(self, path: str) -> GlossaryDef:
        """Auto-detect format (YAML or Markdown) and parse the glossary file."""
        if path.endswith(".yaml") or path.endswith(".yml"):
            return parse_glossary_yaml(path)
        return parse_glossary_markdown(path)

    def create_glossary_from_markdown(
        self,
        input_path: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        """Parse *input_path* and create/update glossary, categories, terms, and links."""
        path = self._resolve_input(input_path)
        glossary_def = self._parse_glossary_file(path)
        print(f"Parsed glossary '{glossary_def.display_name}' "
              f"({sum(len(c.terms) for c in glossary_def.categories)} terms "
              f"in {len(glossary_def.categories)} categories)")

        if dry_run:
            self._print_dry_run(glossary_def)
            return

        # Pre-pass to ensure all synonym and related terms exist as actual terms
        all_term_defs_by_slug = {term.name: term for category in glossary_def.categories for term in category.terms}
        for cat_def in list(glossary_def.categories):
            for term_def in list(cat_def.terms):
                def ensure_term_def_exists(link_name, link_type):
                    link_slug = _slugify(link_name)
                    if link_slug not in all_term_defs_by_slug:
                        print(f"  ℹ️  Creating implicit term for {link_type}: {link_name}")
                        new_term_def = GlossaryTermDef(
                            name=link_slug,
                            display_name=link_name,
                            description=f"{link_type.capitalize()} of {term_def.display_name}"
                        )
                        cat_def.terms.append(new_term_def)
                        all_term_defs_by_slug[link_slug] = new_term_def

                for syn_name in term_def.synonyms:
                    ensure_term_def_exists(syn_name, "synonym")
                
                for rel_name in term_def.related:
                    ensure_term_def_exists(rel_name, "related term")

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

        # 4. Update terms with links (second pass)
        self._update_term_links(glossary_def, term_names)

        

        print("✅ Glossary creation complete.")

    def validate_glossary(self, input_path: Optional[str] = None) -> bool:
        """Validate that the glossary resources exist in Dataplex."""
        path = self._resolve_input(input_path)
        glossary_def = self._parse_glossary_file(path)

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
        glossary_def = self._parse_glossary_file(path)
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
        glossary_def = self._parse_glossary_file(path)
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
            parent=glossary_name,
            category=category,
            category_id=cat_def.name,
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
                term_id=term_def.name,
                term=term,
            )
        )
        print(f"    ✅ Created term: {term_def.display_name}")
        return result.name

    def _update_term_links(self, glossary_def: GlossaryDef, term_names: Dict[str, str]) -> None:
        """Second pass to update terms with synonym and related term links."""
        auth_token = self._get_auth_token()
        if not auth_token:
            return

        for cat_def in glossary_def.categories:
            for term_def in cat_def.terms:
                # Link Synonyms
                self._create_links_rest(term_def, term_def.synonyms, "synonym", term_names, glossary_def.glossary_id, auth_token)

                # Link Related Terms
                self._create_links_rest(term_def, term_def.related, "related", term_names, glossary_def.glossary_id, auth_token)

    def _create_links_rest(self, term_def: GlossaryTermDef, linked_term_names: List[str], link_type: str, term_names: Dict[str, str], glossary_id: str, auth_token: str):
        """Helper to create entry links for a term using REST."""
        import requests
        
        canonical_slug = term_def.name
        canonical_resource_entry = f"projects/{self.project_number}/locations/{self.config.location}/entryGroups/@dataplex/entries/projects/{self.project_number}/locations/{self.config.location}/glossaries/{glossary_id}/terms/{canonical_slug}"

        for link_name in linked_term_names:
            link_slug = _slugify(link_name)
            if not link_slug in term_names:
                print(f"  ⚠️  Could not find resource for linked term '{link_name}', skipping.")
                continue

            linked_term_entry = f"projects/{self.project_number}/locations/{self.config.location}/entryGroups/@dataplex/entries/projects/{self.project_number}/locations/{self.config.location}/glossaries/{glossary_id}/terms/{link_slug}"
            
            id_parts = sorted([canonical_slug, link_slug])
            entry_link_id = f"{link_type}-{id_parts[0]}-{id_parts[1]}"

            url = f"https://dataplex.googleapis.com/v1/projects/{self.config.project_id}/locations/{self.config.location}/entryGroups/@dataplex/entryLinks?entry_link_id={entry_link_id}"
            
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
            }

            payload = {
                "entry_link_type": f"projects/dataplex-types/locations/global/entryLinkTypes/{link_type}",
                "entry_references": [
                    {"name": canonical_resource_entry},
                    {"name": linked_term_entry},
                ],
            }

            try:
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 409: # AlreadyExists
                    print(f"  ↔️  Link already exists: {term_def.display_name} ↔ {link_name}")
                elif response.status_code == 200:
                    print(f"  🔗 Linked {term_def.display_name} → {link_name} (as {link_type})")
                else:
                    print(f"  ⚠️  Failed to link {term_def.display_name} → {link_name}: {response.status_code} {response.text}")
            except Exception as e:
                print(f"  ⚠️  Failed to link {term_def.display_name} → {link_name}: {e}")

    def _get_auth_token(self) -> Optional[str]:
        """Fetches the GCP auth token from gcloud."""
        import subprocess
        try:
            result = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"  🚨 Error fetching auth token: {e}")
            return None

    

    # ------------------------------------------------------------------
    # Private helpers — misc
    # ------------------------------------------------------------------

    def _resolve_input(self, input_path: Optional[str]) -> str:
        if input_path:
            return input_path
        default = os.path.join(self.DEFAULT_GLOSSARY_DIR, self.DEFAULT_GLOSSARY_FILE)
        if os.path.exists(default):
            return default
        # Fallback to legacy markdown
        legacy = os.path.join(self.DEFAULT_GLOSSARY_DIR, "glossary.md")
        if os.path.exists(legacy):
            return legacy
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
        """Write a minimal glossary YAML template when no bundled file is available."""
        template = {
            "glossary_id": "marketing-business-glossary",
            "display_name": "Marketing Business Glossary",
            "description": "Standardised vocabulary for the Marketing Lakehouse data estate.",
            "categories": [
                {
                    "name": "identity",
                    "display_name": "Identity",
                    "description": "Terms related to user and device identity resolution.",
                    "terms": [
                        {
                            "name": "cookie-id",
                            "display_name": "cookie_id",
                            "description": "Unique identifier for a browser or device session.",
                            "synonyms": ["visitor_id", "device_id"],
                            "tables": ["cookie_registry", "pixel_events"],
                            "business_context": "Identity resolution",
                        },
                        {
                            "name": "hashed-email",
                            "display_name": "hashed_email",
                            "description": "SHA-256 hash of a normalised email address.",
                            "synonyms": ["hem"],
                            "tables": ["audience", "cookie_registry", "transactions"],
                            "business_context": "Cross-channel attribution",
                        },
                    ],
                }
            ],
        }
        with open(dest, "w", encoding="utf-8") as fh:
            yaml.dump(template, fh, sort_keys=False, allow_unicode=True)
