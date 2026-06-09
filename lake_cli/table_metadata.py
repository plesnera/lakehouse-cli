"""Unified table metadata parser.

Reads the structured YAML files in ``metadata/`` to provide a
single source of truth for:

* **Catalog entries** — display name and description
* **Tag values** — tags section with key-value pairs
* **Column descriptions** — columns list with name, description, and synonym mappings
* **Data quality rules** — rules list for Dataplex DQ scans

YAML format
===========

.. code-block:: yaml

    table_id: audience
    display_name: Audience Profiles (Panel Model)
    description: Modelled audience segments derived from panel survey data...

    tags:
      business_owner: Marketing Data Products
      data_domain: audience
      pii_class: pseudonymous
      refresh_cadence: daily
      row_count_approx: 8000
      marketing_usecases: audience_discovery,audience_performance_prediction

    columns:
      - name: audience_id
        description: Surrogate primary key (UUID v4).
      - name: location_lat
        description: Synonym for lat.
        synonym_of: lat

    data_quality_rules:
      - column: audience_id
        rule_type: non_null
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

import yaml


METADATA_DIR = "metadata"


@dataclass
class ColumnMeta:
    """Parsed metadata for a single column."""
    name: str
    description: str
    synonym_of: Optional[str] = None  # source column this one copies from


@dataclass
class RuleMeta:
    """Parsed data quality rule from YAML."""
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
    """All metadata parsed from one table's YAML file."""
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
    """Parse a structured metadata YAML file into a :class:`TableMeta`."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    table_id = data.get("table_id", os.path.splitext(os.path.basename(path))[0])
    display_name = data.get("display_name", table_id)
    description = data.get("description", "").strip()
    tags: dict[str, str] = {}
    columns: dict[str, ColumnMeta] = {}
    dq_rules: list[RuleMeta] = []

    # Tags
    for key, value in (data.get("tags") or {}).items():
        tags[str(key)] = str(value)

    # Columns
    for col_data in (data.get("columns") or []):
        name = col_data.get("name", "")
        if not name:
            continue
        col = ColumnMeta(
            name=name,
            description=col_data.get("description", ""),
            synonym_of=col_data.get("synonym_of"),
        )
        columns[name] = col

    # Data Quality Rules
    for rule_data in (data.get("data_quality_rules") or []):
        column = rule_data.get("column", "")
        rule_type = rule_data.get("rule_type", "")
        if not column or not rule_type:
            continue

        rule = RuleMeta(
            column=column,
            rule_type=rule_type,
            threshold=float(rule_data.get("threshold", 1.0)),
            dimension=rule_data.get("dimension", "COMPLETENESS"),
            values=[str(v).strip() for v in rule_data.get("values", [])],
            pattern=rule_data.get("pattern", ""),
            min_value=str(rule_data.get("min", "")),
            max_value=str(rule_data.get("max", "")),
            strict_min_enabled=bool(rule_data.get("strict_min", False)),
            strict_max_enabled=bool(rule_data.get("strict_max", False)),
        )
        dq_rules.append(rule)

    return TableMeta(
        table_id=table_id,
        display_name=display_name or table_id,
        description=description,
        tags=tags,
        columns=columns,
        dq_rules=dq_rules,
    )


def load_all_table_metadata(
    metadata_dir: str = METADATA_DIR,
) -> Dict[str, TableMeta]:
    """Load metadata for every ``*.yaml`` file in *metadata_dir*.

    Returns a dict keyed by table_id (filename without extension, or the
    ``table_id`` field inside the YAML).
    """
    result: dict[str, TableMeta] = {}
    if not os.path.isdir(metadata_dir):
        return result

    for fname in sorted(os.listdir(metadata_dir)):
        if not fname.endswith(".yaml"):
            continue
        path = os.path.join(metadata_dir, fname)
        meta = parse_table_metadata(path)
        result[meta.table_id] = meta

    return result


def _parse_dq_rule_line(line: str) -> RuleMeta | None:
    """Kept for backwards compatibility — parses a single DQ rule bullet line.

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
