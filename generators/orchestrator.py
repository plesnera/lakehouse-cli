from generators.config import GeneratorConfig
from generators.audience import AudienceGenerator
from generators.campaigns import CampaignGenerator
from generators.creatives import CreativeGenerator
from generators.cookie_registry import CookieRegistryGenerator
from generators.pixel_events import PixelEventGenerator
from generators.transactions import TransactionGenerator
from ingestion.table_metadata import load_all_table_metadata
from typing import Dict, Generator, Tuple
import pyarrow as pa

def apply_synonym_columns(table: pa.Table, table_name: str, all_meta: dict) -> pa.Table:
    """Copy source column values into synonym columns based on metadata.

    Reads ``Synonym Of:`` annotations from the parsed metadata markdown.
    If the synonym column already exists in the table, its values are
    overwritten with the source column.  If it does not exist, it is
    appended.
    """
    meta = all_meta.get(table_name)
    if not meta:
        return table

    for syn_col, src_col in meta.synonym_map.items():
        if src_col not in table.column_names:
            continue
        src_array = table.column(src_col)
        if syn_col in table.column_names:
            idx = table.column_names.index(syn_col)
            table = table.set_column(idx, syn_col, src_array)
        else:
            table = table.append_column(syn_col, src_array)

    return table


class Orchestrator:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self._meta = load_all_table_metadata()
        self.generators = {
            "audience": AudienceGenerator(config),
            "campaigns": CampaignGenerator(config),
            "creatives": CreativeGenerator(config),
            "cookie_registry": CookieRegistryGenerator(config),
            "pixel_events": PixelEventGenerator(config),
            "transactions": TransactionGenerator(config)
        }

    def _apply_synonyms(self, name: str, table: pa.Table) -> pa.Table:
        """Apply synonym column mappings from metadata markdown."""
        return apply_synonym_columns(table, name, self._meta)

    def generate_all_streamed(self) -> Generator[Tuple[str, pa.Table], None, None]:
        # Small tables first (needed for dependencies)
        print("Generating Audience...")
        audience = self._apply_synonyms("audience", self.generators["audience"].generate())
        yield "audience", audience
        
        print("Generating Campaigns...")
        campaigns = self._apply_synonyms("campaigns", self.generators["campaigns"].generate())
        yield "campaigns", campaigns
        
        print("Generating Creatives...")
        creatives = self._apply_synonyms("creatives", self.generators["creatives"].generate(campaigns=campaigns))
        yield "creatives", creatives
        
        print("Generating Cookie Registry...")
        cookie_registry = self._apply_synonyms("cookie_registry", self.generators["cookie_registry"].generate(audience=audience))
        yield "cookie_registry", cookie_registry
        
        # Large tables streamed
        print("Generating Pixel Events (Streamed)...")
        for batch in self.generators["pixel_events"].generate_batches(
            cookies=cookie_registry,
            campaigns=campaigns,
            creatives=creatives
        ):
            yield "pixel_events", self._apply_synonyms("pixel_events", batch)
            
        print("Generating Transactions (Streamed)...")
        for batch in self.generators["transactions"].generate_batches(cookies=cookie_registry):
            yield "transactions", self._apply_synonyms("transactions", batch)

    def generate_all(self) -> Dict[str, pa.Table]:
        # Legacy support
        tables = {}
        for name, table in self.generate_all_streamed():
            if name in tables:
                tables[name] = pa.concat_tables([tables[name], table])
            else:
                tables[name] = table
        return tables
