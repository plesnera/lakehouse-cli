from generators.config import GeneratorConfig
from generators.audience import AudienceGenerator
from generators.campaigns import CampaignGenerator
from generators.creatives import CreativeGenerator
from generators.cookie_registry import CookieRegistryGenerator
from generators.pixel_events import PixelEventGenerator
from generators.transactions import TransactionGenerator
from typing import Dict, Generator, Tuple
import pyarrow as pa

class Orchestrator:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.generators = {
            "audience": AudienceGenerator(config),
            "campaigns": CampaignGenerator(config),
            "creatives": CreativeGenerator(config),
            "cookie_registry": CookieRegistryGenerator(config),
            "pixel_events": PixelEventGenerator(config),
            "transactions": TransactionGenerator(config)
        }

    def generate_all_streamed(self) -> Generator[Tuple[str, pa.Table], None, None]:
        # Small tables first (needed for dependencies)
        print("Generating Audience...")
        audience = self.generators["audience"].generate()
        yield "audience", audience
        
        print("Generating Campaigns...")
        campaigns = self.generators["campaigns"].generate()
        yield "campaigns", campaigns
        
        print("Generating Creatives...")
        creatives = self.generators["creatives"].generate(campaigns=campaigns)
        yield "creatives", creatives
        
        print("Generating Cookie Registry...")
        cookie_registry = self.generators["cookie_registry"].generate(audience=audience)
        yield "cookie_registry", cookie_registry
        
        # Large tables streamed
        print("Generating Pixel Events (Streamed)...")
        for batch in self.generators["pixel_events"].generate_batches(
            cookies=cookie_registry,
            campaigns=campaigns,
            creatives=creatives
        ):
            yield "pixel_events", batch
            
        print("Generating Transactions (Streamed)...")
        for batch in self.generators["transactions"].generate_batches(cookies=cookie_registry):
            yield "transactions", batch

    def generate_all(self) -> Dict[str, pa.Table]:
        # Legacy support
        tables = {}
        for name, table in self.generate_all_streamed():
            if name in tables:
                tables[name] = pa.concat_tables([tables[name], table])
            else:
                tables[name] = table
        return tables
