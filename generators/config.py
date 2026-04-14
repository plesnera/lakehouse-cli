from pydantic import BaseModel, Field
from typing import Dict, List

class MarketMatchRates(BaseModel):
    txn_cookie_fill_rate: float
    txn_hem_fill_rate: float

class GeneratorConfig(BaseModel):
    seed: int = 42
    target_markets: List[str] = ["US", "GB", "JP"]

    # Scale (matches Agent.md spec)
    n_audience_participants: int = 100
    n_audience_segments: int = 10
    n_cookies: int = 1000
    n_campaigns: int = 10
    n_creatives_per_campaign: int = 2
    n_pixel_events: int = 5000
    n_transactions: int = 1000
    date_range_days: int = 365

    # Match-rate controls — baseline rates
    audience_hem_fill_rate: float = 0.60
    cookie_audience_fill_rate: float = 0.40
    cookie_hem_fill_rate: float = 0.35
    pixel_cookie_fill_rate: float = 0.82
    txn_cookie_fill_rate: float = 0.25     # baseline; overridden per market
    txn_hem_fill_rate: float = 0.20        # baseline; overridden per market

    # Per-market overrides for transaction join rates
    # US: baseline +5pp, UK: baseline -5pp, JP: baseline -10pp
    market_txn_rates: Dict[str, MarketMatchRates] = {
        "US": MarketMatchRates(txn_cookie_fill_rate=0.30, txn_hem_fill_rate=0.25),
        "GB": MarketMatchRates(txn_cookie_fill_rate=0.20, txn_hem_fill_rate=0.15),
        "JP": MarketMatchRates(txn_cookie_fill_rate=0.15, txn_hem_fill_rate=0.10),
    }

    # Iceberg / GCS output
    iceberg_warehouse: str = "gs://wpp-dataproducts-lakehouse-warehouse/iceberg"
    iceberg_namespace: str = "marketing"
    biglake_connection: str = "projects/wpp-dataproducts-lakehouse/locations/us-east1/connections/biglake-conn"
    project_id: str = "wpp-dataproducts-lakehouse"
    location: str = "us-east1"
