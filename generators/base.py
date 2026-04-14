import abc
import numpy as np
from faker import Faker
import pyarrow as pa
from generators.config import GeneratorConfig

class BaseGenerator(abc.ABC):
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.faker = Faker()
        Faker.seed(config.seed)
        np.random.seed(config.seed)
        self.market_fakers = {
            market: Faker(self._get_locale(market)) 
            for market in config.target_markets
        }
        for m_faker in self.market_fakers.values():
            m_faker.seed_instance(config.seed)

    def _get_locale(self, market: str) -> str:
        locales = {
            "US": "en_US",
            "GB": "en_GB",
            "JP": "ja_JP",
            "DE": "de_DE",
            "FR": "fr_FR",
            "AU": "en_AU"
        }
        return locales.get(market, "en_US")

    @abc.abstractmethod
    def generate(self, **kwargs) -> pa.Table:
        pass

    def generate_batches(self, batch_size: int = 100000, **kwargs):
        """Yields pa.Table batches."""
        # Default implementation just yields one big batch if not overridden
        yield self.generate(**kwargs)

    @abc.abstractmethod
    def get_schema(self) -> pa.Schema:
        pass
