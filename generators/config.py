from pydantic import BaseModel, Field
from typing import Dict, List
import subprocess
import os

class MarketMatchRates(BaseModel):
    txn_cookie_fill_rate: float
    txn_hem_fill_rate: float

# Production-scale defaults matching Agent.md spec
FULL_SCALE = {
    "n_audience_participants": 1000, #8_000,
    "n_audience_segments":   65, #500,
    "n_cookies":  1000, #80_000,
    "n_campaigns": 25,  #200,
    "n_creatives_per_campaign": 1, # 5,
    "n_pixel_events": 2000, #2_000_000,
    "n_transactions": 500, #500_000,
}

# Fictional brands from Agent.md
BRANDS = ["Lucky Cola", "Force Automotive", "AEKI Living"]


class GeneratorConfig(BaseModel):
    seed: int = 42
    target_markets: List[str] = ["US", "GB", "JP"]

    @staticmethod
    def get_current_gcloud_project() -> str:
        """Get the current gcloud project or return None if not available."""
        try:
            # Try gcloud command first
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
        
        # Fallback to environment variable
        return os.environ.get("GOOGLE_CLOUD_PROJECT", "wpp-dataproducts-lakehouse")

    # Scale — dev defaults for fast iteration; use FULL_SCALE for demo
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

    # Project configuration - supports cross-project scenarios
    data_project_id: str = Field(
        default_factory=lambda: GeneratorConfig.get_current_gcloud_project(),
        description="GCP project where data is stored (GCS, Iceberg)"
    )
    catalog_project_id: str = Field(
        default_factory=lambda: GeneratorConfig.get_current_gcloud_project(), 
        description="GCP project where Dataplex catalog resides"
    )

    # Storage configuration
    iceberg_warehouse: str = Field(
        default_factory=lambda: f"gs://{GeneratorConfig.get_current_gcloud_project()}-warehouse/iceberg",
        description="GCS path for Iceberg data (can be different project)"
    )
    iceberg_namespace: str = "marketing"
    
    # Connection configuration - template with project placeholder
    biglake_connection: str = Field(
        default="projects/{project_id}/locations/{location}/connections/biglake-conn",
        description="BigLake connection template with {project_id} placeholder"
    )
    
    # Location configuration
    location: str = "us-east1"
    
    # Backward compatibility property
    @property
    def project_id(self) -> str:
        """Maintain backward compatibility - defaults to catalog_project_id"""
        return self.catalog_project_id

    # Resource path helpers
    @property
    def resource_parent(self) -> str:
        """Returns projects/{project_id}/locations/{location}"""
        return f"projects/{self.project_id}/locations/{self.location}"

    @property
    def catalog_resource_parent(self) -> str:
        """Returns projects/{catalog_project_id}/locations/{location}"""
        return f"projects/{self.catalog_project_id}/locations/{self.location}"

    @property
    def entry_group_path(self) -> str:
        """Returns the full entry group resource path"""
        return f"{self.catalog_resource_parent}/entryGroups/marketing-lakehouse"

    def get_bq_resource_path(self, table: str) -> str:
        """Returns the BigQuery resource path for a table"""
        return f"//bigquery.googleapis.com/projects/{self.project_id}/datasets/{self.iceberg_namespace}/tables/{table}"


# Table list - single source of truth for all tables in the lakehouse
TABLES = ["audience", "cookie_registry", "campaigns", "creatives", "pixel_events", "transactions"]
