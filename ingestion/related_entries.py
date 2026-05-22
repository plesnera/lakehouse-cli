"""Related Entries Manager — Dataplex glossary ↔ catalog column discovery.

Provides two workflows:

1. **list-related-entries** — given a glossary term, find all catalog entries
   (tables) whose schema contains a matching column.
2. **scan-for-related-entries** — compare a BigLake catalog's table columns
   against a glossary, producing exact, synonym, and fuzzy match proposals.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ingestion.config import Config


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STOP_WORDS = frozenset(
    "the a an is of for by in to with as and or that used from".split()
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RelatedEntry:
    """A single catalog entry row matched to a glossary term."""
    resource_name: str
    column_name: str
    project: str
    fqn: str
    entry_path: str


@dataclass
class ExactMatch:
    """A term matched via exact or synonym column matching (Phase A)."""
    term_name: str
    matched_columns: List[str]
    found_in_tables: List[str]
    via_synonym: Optional[str] = None  # set if match came via synonym


@dataclass
class FuzzyProposal:
    """A fuzzy match proposal for an unmatched term (Phase B)."""
    term_name: str
    category: str
    description: str
    table_column: str  # "table.column"
    score: int
    rationale: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, hyphens → underscores."""
    return name.lower().replace("-", "_").strip()


def _extract_project_from_resource(resource: str) -> str:
    """Extract the GCP project ID from a resource string like
    ``bigquery.googleapis.com/projects/<project>/...``."""
    m = re.search(r"/projects/([^/]+)", resource)
    return m.group(1) if m else ""


def _extract_entry_group_from_name(entry_name: str) -> str:
    """Extract the entry group segment (e.g. ``@bigquery``) from the full entry name."""
    m = re.search(r"/entryGroups/([^/]+)", entry_name)
    return m.group(1) if m else ""


def _extract_entry_id_from_name(entry_name: str) -> str:
    """Extract the entry ID segment (everything after ``/entries/``)."""
    m = re.search(r"/entries/(.+)$", entry_name)
    return m.group(1) if m else ""


def extract_column_names_from_entry(entry: dict) -> List[str]:
    """Return all column names from a described Dataplex entry's schema aspects.

    Schema fields live under ``aspects.<key>.data.fields`` where ``<key>``
    varies by system (e.g. ``<project_id>.us-east1.schema``).
    """
    columns: list[str] = []
    for _key, aspect in (entry.get("aspects") or {}).items():
        data = aspect.get("data") or {}
        for fld in data.get("fields") or []:
            name = fld.get("name", "")
            if name:
                columns.append(name)
    return columns


def _extract_synonym_target(description: str) -> Optional[str]:
    """If *description* starts with 'Synonym for <term>', return the canonical term."""
    m = re.match(r"^[Ss]ynonym\s+for\s+(\w[\w_-]*)", description)
    return m.group(1) if m else None


def tokenize_description(description: str) -> List[str]:
    """Tokenize a term description into keywords, filtering stop words."""
    words = re.findall(r"[a-z][a-z0-9_]*", description.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def score_column(column_name: str, table_name: str, keywords: List[str]) -> Tuple[int, List[str]]:
    """Score a column against a set of keywords.

    Returns ``(score, list_of_matching_keywords)``.

    Scoring:
      +10 — keyword matches column name exactly
      +5  — keyword is a substring of the column name
      +3  — keyword is a substring of the table name
    """
    score = 0
    matched: list[str] = []
    col_lower = column_name.lower()
    tbl_lower = table_name.lower()

    for kw in keywords:
        if kw == col_lower:
            score += 10
            matched.append(f"exact:{kw}")
        elif kw in col_lower:
            score += 5
            matched.append(f"substr:{kw}")
        elif kw in tbl_lower:
            score += 3
            matched.append(f"table:{kw}")

    return score, matched


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class RelatedEntriesManager:
    """Orchestrates glossary ↔ catalog column discovery via gcloud CLI."""

    def __init__(self, config: Config):
        self.config = config

    # ------------------------------------------------------------------
    # gcloud helpers
    # ------------------------------------------------------------------

    def _run_gcloud(self, args: List[str]) -> Any:
        """Run a gcloud command with ``--format=json`` and return parsed JSON."""
        cmd = ["gcloud"] + args + ["--format=json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(
                f"gcloud command failed (rc={result.returncode}):\n"
                f"  cmd: {' '.join(cmd)}\n"
                f"  stderr: {result.stderr.strip()}"
            )
        text = result.stdout.strip()
        if not text:
            return []
        return json.loads(text)

    def _discover_glossary(self, glossary_hint: Optional[str] = None) -> dict:
        """List glossaries and return the one matching *glossary_hint*.

        If *glossary_hint* is ``None``, returns the first glossary found.
        Returns a dict with at least ``name`` and ``displayName`` keys.
        """
        glossaries = self._run_gcloud([
            "dataplex", "glossaries", "list",
            f"--location={self.config.location}",
        ])

        if not glossaries:
            raise RuntimeError("No glossaries found in the current project/location.")

        if glossary_hint:
            for g in glossaries:
                gid = g.get("name", "").rsplit("/", 1)[-1]
                if gid == glossary_hint or g.get("displayName", "") == glossary_hint:
                    return g
            raise RuntimeError(f"Glossary '{glossary_hint}' not found.")

        return glossaries[0]

    def _list_glossary_terms(self, glossary_id: str) -> List[dict]:
        """List all terms in a glossary."""
        return self._run_gcloud([
            "dataplex", "glossaries", "terms", "list",
            f"--glossary={glossary_id}",
            f"--location={self.config.location}",
        ])

    def _search_entries(self, query: str) -> List[dict]:
        """Search Dataplex catalog entries by keyword."""
        return self._run_gcloud([
            "dataplex", "entries", "search", query,
            f"--project={self.config.project_id}",
        ])

    def _describe_entry(self, entry_id: str, entry_group: str) -> dict:
        """Describe a single Dataplex entry (full view including schema)."""
        return self._run_gcloud([
            "dataplex", "entries", "describe", entry_id,
            f"--entry-group={entry_group}",
            f"--location={self.config.location}",
            "--view=FULL",
        ])

    def _list_biglake_entries(self, limit: int = 100) -> List[dict]:
        """List entries in the ``@biglake`` entry group."""
        return self._run_gcloud([
            "dataplex", "entries", "list",
            "--entry-group=@biglake",
            f"--location={self.config.location}",
            f"--limit={limit}",
        ])

    # ------------------------------------------------------------------
    # list-related-entries
    # ------------------------------------------------------------------

    def list_related_entries(
        self,
        term_name: str,
        glossary: Optional[str] = None,
    ) -> List[RelatedEntry]:
        """Find catalog entries whose schema contains a column matching *term_name*.

        Returns the list of :class:`RelatedEntry` results and also prints
        a human-readable report.
        """
        # 1. Discover glossary
        glossary_info = self._discover_glossary(glossary)
        glossary_id = glossary_info["name"].rsplit("/", 1)[-1]
        glossary_display = glossary_info.get("displayName", glossary_id)

        # 2. List terms to find metadata for the target term
        terms = self._list_glossary_terms(glossary_id)
        term_meta = None
        for t in terms:
            if normalize_name(t.get("displayName", "")) == normalize_name(term_name):
                term_meta = t
                break

        if not term_meta:
            print(f"❌ Term '{term_name}' not found in glossary '{glossary_display}'.")
            return []

        term_display = term_meta.get("displayName", term_name)
        term_desc = term_meta.get("description", "")
        # Extract category from parent path
        parent = term_meta.get("parent", "")
        category = parent.rsplit("/", 1)[-1].replace("-", " ").title() if "/" in parent else ""

        # 3. Search catalog for entries matching the term
        search_results = self._search_entries(term_name)

        # 4/5. Describe each table entry and check for matching columns
        normalized_term = normalize_name(term_name)
        results: list[RelatedEntry] = []

        for entry in search_results:
            entry_name = entry.get("name", "")
            entry_type = entry.get("entryType", "")

            # Skip non-table entries (glossary terms, data products, etc.)
            if "table" not in entry_type.lower() and "table" not in entry_name.lower():
                continue

            entry_group = _extract_entry_group_from_name(entry_name)
            entry_id = _extract_entry_id_from_name(entry_name)

            if not entry_group or not entry_id:
                continue

            try:
                full_entry = self._describe_entry(entry_id, entry_group)
            except RuntimeError:
                continue

            columns = extract_column_names_from_entry(full_entry)
            matching_cols = [
                c for c in columns if normalize_name(c) == normalized_term
            ]

            if not matching_cols:
                continue

            resource = (full_entry.get("entrySource") or {}).get("resource", "")
            fqn = full_entry.get("fullyQualifiedName", "")
            project = _extract_project_from_resource(resource)

            for col in matching_cols:
                results.append(RelatedEntry(
                    resource_name=resource,
                    column_name=col,
                    project=project,
                    fqn=fqn,
                    entry_path=entry_name,
                ))

        # 6. Print formatted output
        self._print_related_entries(
            term_display, term_desc, glossary_display, category, results
        )

        return results

    def _print_related_entries(
        self,
        term_display: str,
        term_desc: str,
        glossary_display: str,
        category: str,
        results: List[RelatedEntry],
    ) -> None:
        """Print the list-related-entries report."""
        desc_suffix = f" — {term_desc}" if term_desc else ""
        print(f"\nGlossary Term: {term_display}{desc_suffix}")
        print(f"Glossary: {glossary_display}")
        if category:
            print(f"Category: {category}")

        if not results:
            print("\nNo matching catalog entries found.")
            return

        print(f"\n{'#':>3} | {'Resource Name':<70} | {'Column':<20} | {'Project':<30} | Fully Qualified Name")
        print("-" * 160)
        for i, r in enumerate(results, 1):
            print(f"{i:>3} | {r.resource_name:<70} | {r.column_name:<20} | {r.project:<30} | {r.fqn}")

        print("\nFull Dataplex Entry Paths:")
        seen: set[str] = set()
        for r in results:
            if r.entry_path not in seen:
                seen.add(r.entry_path)
                print(f"  {r.entry_path}")

    # ------------------------------------------------------------------
    # scan-for-related-entries
    # ------------------------------------------------------------------

    def scan_for_related_entries(
        self,
        catalog_name: str,
        namespace: Optional[str] = None,
        glossary: Optional[str] = None,
    ) -> Tuple[List[ExactMatch], List[FuzzyProposal]]:
        """Compare a BigLake catalog against a glossary to propose matches.

        Returns ``(exact_matches, fuzzy_proposals)`` and prints a report.
        """
        # 1. Discover glossary and terms
        glossary_info = self._discover_glossary(glossary)
        glossary_id = glossary_info["name"].rsplit("/", 1)[-1]
        glossary_display = glossary_info.get("displayName", glossary_id)

        terms = self._list_glossary_terms(glossary_id)
        num_terms = len(terms)
        # Count categories
        categories_seen: set[str] = set()
        for t in terms:
            parent = t.get("parent", "")
            if "/categories/" in parent:
                categories_seen.add(parent.rsplit("/", 1)[-1])
        num_categories = len(categories_seen)

        # Build term lookup: normalized_name -> {displayName, description, category}
        term_lookup: dict[str, dict] = {}
        for t in terms:
            display = t.get("displayName", "")
            parent = t.get("parent", "")
            cat = parent.rsplit("/", 1)[-1].replace("-", " ").title() if "/categories/" in parent else ""
            term_lookup[normalize_name(display)] = {
                "displayName": display,
                "description": t.get("description", ""),
                "category": cat,
            }

        # 2. List BigLake entries
        entries = self._list_biglake_entries()

        # Filter to table entries (exclude catalogs, namespaces, entry-groups)
        table_entries = []
        for e in entries:
            entry_type = e.get("entryType", "")
            if "table" in entry_type.lower():
                table_entries.append(e)

        # Optionally filter by namespace
        if namespace:
            table_entries = [
                e for e in table_entries
                if f"/namespaces/{namespace}/" in e.get("name", "")
                or f"/namespaces/{namespace}/" in e.get("fullyQualifiedName", "")
            ]

        # 3. Extract schema from each table
        table_schemas: dict[str, List[str]] = {}  # table_display_name -> [column_names]
        total_columns = 0
        for e in table_entries:
            entry_name = e.get("name", "")
            entry_group = _extract_entry_group_from_name(entry_name)
            entry_id = _extract_entry_id_from_name(entry_name)

            if not entry_group or not entry_id:
                continue

            try:
                full_entry = self._describe_entry(entry_id, entry_group)
            except RuntimeError:
                continue

            display = (full_entry.get("entrySource") or {}).get("displayName", "")
            if not display:
                display = entry_id.rsplit("/", 1)[-1]
            columns = extract_column_names_from_entry(full_entry)
            table_schemas[display] = columns
            total_columns += len(columns)

        # 4. Phase A — Exact & synonym matching
        exact_matches, matched_terms = self._phase_a_matching(term_lookup, table_schemas)

        # 5. Phase B — Fuzzy matching for unmatched terms
        unmatched = {k: v for k, v in term_lookup.items() if k not in matched_terms}
        fuzzy_proposals = self._phase_b_matching(unmatched, table_schemas)

        # 6. Print report
        self._print_scan_report(
            glossary_id=glossary_id,
            num_terms=num_terms,
            num_categories=num_categories,
            catalog_name=catalog_name,
            namespace=namespace,
            num_tables=len(table_schemas),
            num_columns=total_columns,
            exact_matches=exact_matches,
            fuzzy_proposals=fuzzy_proposals,
        )

        return exact_matches, fuzzy_proposals

    def _phase_a_matching(
        self,
        term_lookup: Dict[str, dict],
        table_schemas: Dict[str, List[str]],
    ) -> Tuple[List[ExactMatch], set[str]]:
        """Phase A: exact and synonym matching.

        Returns ``(matches, matched_normalized_names)``.
        """
        # Build reverse index: normalized_column -> list of table names
        col_to_tables: dict[str, list[str]] = {}
        for table, columns in table_schemas.items():
            for col in columns:
                key = normalize_name(col)
                col_to_tables.setdefault(key, []).append(table)

        matches: list[ExactMatch] = []
        matched_terms: set[str] = set()

        # First pass: direct exact matches
        canonical_matches: dict[str, ExactMatch] = {}  # normalized_name -> match
        for norm_name, info in term_lookup.items():
            if norm_name in col_to_tables:
                tables = sorted(set(col_to_tables[norm_name]))
                m = ExactMatch(
                    term_name=info["displayName"],
                    matched_columns=[norm_name],
                    found_in_tables=tables,
                )
                matches.append(m)
                matched_terms.add(norm_name)
                canonical_matches[norm_name] = m

        # Second pass: synonym detection
        for norm_name, info in term_lookup.items():
            if norm_name in matched_terms:
                continue

            desc = info.get("description", "")
            synonym_target = _extract_synonym_target(desc)
            if synonym_target:
                canonical_norm = normalize_name(synonym_target)
                if canonical_norm in matched_terms:
                    # Inherit the canonical match
                    canon = canonical_matches[canonical_norm]
                    m = ExactMatch(
                        term_name=info["displayName"],
                        matched_columns=[f"(via synonym → {synonym_target})"],
                        found_in_tables=canon.found_in_tables,
                        via_synonym=synonym_target,
                    )
                    matches.append(m)
                    matched_terms.add(norm_name)

        return matches, matched_terms

    def _phase_b_matching(
        self,
        unmatched: Dict[str, dict],
        table_schemas: Dict[str, List[str]],
    ) -> List[FuzzyProposal]:
        """Phase B: fuzzy semantic matching for unmatched terms."""
        proposals: list[FuzzyProposal] = []

        for norm_name, info in unmatched.items():
            desc = info.get("description", "")
            if not desc:
                continue

            keywords = tokenize_description(desc)
            if not keywords:
                continue

            term_proposals: list[FuzzyProposal] = []
            for table, columns in table_schemas.items():
                for col in columns:
                    sc, matched_kws = score_column(col, table, keywords)
                    if sc > 0:
                        rationale = ", ".join(matched_kws)
                        term_proposals.append(FuzzyProposal(
                            term_name=info["displayName"],
                            category=info.get("category", ""),
                            description=desc,
                            table_column=f"{table}.{col}",
                            score=sc,
                            rationale=rationale,
                        ))

            # Sort by score descending
            term_proposals.sort(key=lambda p: -p.score)
            proposals.extend(term_proposals)

        return proposals

    def _print_scan_report(
        self,
        glossary_id: str,
        num_terms: int,
        num_categories: int,
        catalog_name: str,
        namespace: Optional[str],
        num_tables: int,
        num_columns: int,
        exact_matches: List[ExactMatch],
        fuzzy_proposals: List[FuzzyProposal],
    ) -> None:
        """Print the scan-for-related-entries report."""
        ns_str = f" / namespace {namespace}" if namespace else ""
        print(f"\nGlossary: {glossary_id} ({num_terms} terms, {num_categories} categories)")
        print(f"BigLake Catalog: {catalog_name}{ns_str} ({num_tables} tables, {num_columns} columns)")

        # Phase A
        print(f"\nPhase A — Exact & Synonym Matches ({len(exact_matches)} terms):")
        if exact_matches:
            print(f"  {'Glossary Term':<25} | {'Matched Column(s)':<30} | Found In Table(s)")
            print("  " + "-" * 100)
            for m in exact_matches:
                cols = ", ".join(m.matched_columns)
                tables = ", ".join(m.found_in_tables)
                print(f"  {m.term_name:<25} | {cols:<30} | {tables}")
        else:
            print("  (no exact matches)")

        # Phase B
        # Collect unique unmatched term names
        unmatched_terms = sorted(set(p.term_name for p in fuzzy_proposals))
        print(f"\nPhase B — Fuzzy Semantic Proposals ({len(unmatched_terms)} unmatched terms):")
        if fuzzy_proposals:
            print(f"  {'#':>3} | {'Glossary Term':<20} | {'Category':<20} | {'Proposed Table.Column':<40} | {'Score':>5} | Match Rationale")
            print("  " + "-" * 130)
            for i, p in enumerate(fuzzy_proposals, 1):
                print(f"  {i:>3} | {p.term_name:<20} | {p.category:<20} | {p.table_column:<40} | {p.score:>5} | {p.rationale}")
        else:
            print("  (no fuzzy proposals)")
