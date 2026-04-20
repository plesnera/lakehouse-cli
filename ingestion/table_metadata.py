"""Unified table metadata parser.

Reads the extended markdown files in ``metadata_descriptions/`` to provide a
single source of truth for:

* **Catalog entries** — display name and description (first heading + paragraph)
* **Tag values** — ``## Tags`` section with key: value bullets
* **Column descriptions** — ``## Columns`` section
* **Synonym column mappings** — ``Synonym Of: <source_column>`` sub-bullets

Markdown format
===============

.. code-block:: markdown

    # Display Name

    Description paragraph(s).

    ## Tags
    - business_owner: Marketing Data Products
    - data_domain: audience
    - pii_class: pseudonymous
    - refresh_cadence: daily
    - row_count_approx: 8000
    - marketing_usecases: audience_discovery,audience_performance_prediction

    ## Columns
    - audience_id: Surrogate primary key (UUID v4).
    - lat: Centroid latitude of dominant geo cluster.
    - location_lat: Synonym for lat.
      - Synonym Of: lat
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional


METADATA_DIR = "metadata_descriptions"


@dataclass
class ColumnMeta:
    """Parsed metadata for a single column."""
    name: str
    description: str
    synonym_of: Optional[str] = None  # source column this one copies from


@dataclass
class RuleMeta:
    """Parsed data quality rule from markdown."""
    column: str
    rule_type: str  # non_null | set | regex | range
    threshold: float = 1.0
    dimension: str = "COMPLETENESS"
    values: list[str] = field(default_factory=list)
    pattern: str = ""
    min_value: str = ""
    max_value: str = ""
    strict_min_enabled: bool = False
    strict_max_enabled: bool = False


@dataclass
class TableMeta:
    """All metadata parsed from one table's markdown file."""
    table_id: str
    display_name: str
    description: str
    tags: Dict[str, str] = field(default_factory=dict)
    columns: Dict[str, ColumnMeta] = field(default_factory=dict)
    dq_rules: list[RuleMeta] = field(default_factory=list)

    # Convenience views -------------------------------------------------------
    @property
    def synonym_map(self) -> Dict[str, str]:
        """Return ``{synonym_column: source_column}`` for all synonym columns."""
        return {
            c.name: c.synonym_of
            for c in self.columns.values()
            if c.synonym_of
        }

    @property
    def tag_row_count(self) -> float:
        """Return row_count_approx as a float (or 0.0)."""
        try:
            return float(self.tags.get("row_count_approx", 0))
        except (ValueError, TypeError):
            return 0.0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_table_metadata(path: str) -> TableMeta:
    """Parse an extended metadata markdown file into a :class:`TableMeta`."""
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    table_id = os.path.splitext(os.path.basename(path))[0]
    display_name = ""
    description_lines: list[str] = []
    tags: dict[str, str] = {}
    columns: dict[str, ColumnMeta] = {}
    dq_rules: list[RuleMeta] = []

    section: str | None = None  # "tags" | "columns" | "dq_rules" | None
    current_col: ColumnMeta | None = None

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()

        # --- H1: display name ------------------------------------------------
        if stripped.startswith("# ") and not stripped.startswith("## "):
            display_name = stripped[2:].strip()
            section = None
            continue

        # --- H2: section header ----------------------------------------------
        if stripped.startswith("## "):
            heading = stripped[3:].strip().lower()
            if heading == "tags":
                section = "tags"
            elif heading == "columns":
                section = "columns"
            elif heading == "data quality rules":
                section = "dq_rules"
            else:
                section = None
            continue

        # --- Tags section: ``- key: value`` ----------------------------------
        if section == "tags" and stripped.startswith("- "):
            key, _, value = stripped[2:].partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key:
                tags[key] = value
            continue

        # --- Columns section -------------------------------------------------
        if section == "columns":
            is_indented = line != line.lstrip()  # any leading whitespace

            # Indented sub-bullet: ``  - Synonym Of: source_col``
            # Must check BEFORE the top-level bullet to avoid mis-parsing.
            if current_col and is_indented and stripped.startswith("- "):
                kv = stripped[2:].strip()
                key, _, value = kv.partition(":")
                key = key.strip().lower()
                value = value.strip()
                if key == "synonym of":
                    current_col.synonym_of = value
                continue

            # Top-level column bullet: ``- col_name: description``
            if stripped.startswith("- ") and not is_indented:
                # Flush previous column
                if current_col:
                    columns[current_col.name] = current_col

                rest = stripped[2:]
                col_name, _, col_desc = rest.partition(":")
                col_name = col_name.strip()
                col_desc = col_desc.strip()
                current_col = ColumnMeta(name=col_name, description=col_desc)
                continue

        # --- DQ Rules section --------------------------------------------------
        if section == "dq_rules" and stripped.startswith("- "):
            rule = _parse_dq_rule_line(stripped)
            if rule:
                dq_rules.append(rule)
            continue

        # --- Description paragraph (between H1 and first H2) ----------------
        if section is None and stripped and not stripped.startswith("#"):
            description_lines.append(stripped)

    # Flush last column
    if current_col:
        columns[current_col.name] = current_col

    return TableMeta(
        table_id=table_id,
        display_name=display_name or table_id,
        description=" ".join(description_lines),
        tags=tags,
        columns=columns,
        dq_rules=dq_rules,
    )


def load_all_table_metadata(
    metadata_dir: str = METADATA_DIR,
) -> Dict[str, TableMeta]:
    """Load metadata for every ``*.md`` file in *metadata_dir*.

    Returns a dict keyed by table_id (filename without extension).
    """
    result: dict[str, TableMeta] = {}
    if not os.path.isdir(metadata_dir):
        return result

    for fname in sorted(os.listdir(metadata_dir)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(metadata_dir, fname)
        meta = parse_table_metadata(path)
        result[meta.table_id] = meta

    return result


def _parse_dq_rule_line(line: str) -> RuleMeta | None:
    """Parse a single DQ rule bullet line.

    Format: ``- column: rule_type [param=value ...]``

    Examples:
        - audience_id: non_null
        - hem: non_null threshold=0.57
        - status: set values=planned,active,completed,paused
    """
    # Strip leading "- " and trailing whitespace
    content = line.strip()
    if content.startswith("- "):
        content = content[2:]
    else:
        return None

    # Split on first colon to get column: rule_type [...]
    colon_idx = content.find(":")
    if colon_idx == -1:
        return None

    column = content[:colon_idx].strip()
    rest = content[colon_idx + 1:].strip()

    # rest is "rule_type [param=value ...]"
    parts = rest.split()
    if not parts:
        return None

    rule_type = parts[0]
    params: dict[str, str] = {}
    for param_part in parts[1:]:
        if "=" in param_part:
            key, _, val = param_part.partition("=")
            params[key.strip()] = val.strip()

    rule = RuleMeta(column=column, rule_type=rule_type)

    if "threshold" in params:
        rule.threshold = float(params["threshold"])
    if "dimension" in params:
        rule.dimension = params["dimension"]

    if rule_type == "set":
        if "values" in params:
            rule.values = [v.strip() for v in params["values"].split(",")]

    elif rule_type == "regex":
        if "pattern" in params:
            rule.pattern = params["pattern"]

    elif rule_type == "range":
        if "min" in params:
            rule.min_value = params["min"]
        if "max" in params:
            rule.max_value = params["max"]
        rule.strict_min_enabled = str(params.get("strict_min", "false")).lower() == "true"
        rule.strict_max_enabled = str(params.get("strict_max", "false")).lower() == "true"

    return rule


def parse_dq_rules(section_lines: list[str]) -> list[RuleMeta]:
    """Parse DQ rules from section bullet lines."""
    rules = []
    for line in section_lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            rule = _parse_dq_rule_line(stripped)
            if rule:
                rules.append(rule)
    return rules
