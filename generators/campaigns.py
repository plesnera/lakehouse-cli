import uuid
from datetime import datetime, date, timedelta
import numpy as np
import pyarrow as pa
from generators.base import BaseGenerator

class CampaignGenerator(BaseGenerator):
    def generate(self, **kwargs) -> pa.Table:
        n = self.config.n_campaigns
        data = {
            "campaign_id": [str(uuid.uuid4()) for _ in range(n)],
            "campaign_name": [],
            "brand": [],
            "advertiser": [],
            "product_category": [np.random.choice(["Apparel", "Beauty", "CPG", "Entertainment", "Finance", "Tech"]) for _ in range(n)],
            "country_code": [np.random.choice(self.config.target_markets) for _ in range(n)],
            "regions": [],
            "channels": [],
            "objective": [np.random.choice(["awareness", "consideration", "conversion", "retention"]) for _ in range(n)],
            "budget_usd": np.random.uniform(50000, 1000000, n).tolist(),
            "actual_spend_usd": [],
            "start_date": [],
            "end_date": [],
            "status": [],
            "created_at": []
        }

        base_date = date.today() - timedelta(days=self.config.date_range_days)
        
        from generators.config import BRANDS
        brands = BRANDS

        for i in range(n):
            brand = np.random.choice(brands)
            data["brand"].append(brand)
            data["advertiser"].append(None)  # populated by orchestrator synonym mapping
            data["campaign_name"].append(f"{brand} - {data['product_category'][i]} {i}")
            
            # Dates
            start = base_date + timedelta(days=np.random.randint(0, self.config.date_range_days - 30))
            duration = np.random.randint(30, 90)
            end = start + timedelta(days=duration)
            data["start_date"].append(start)
            data["end_date"].append(end)
            data["created_at"].append(datetime.combine(start - timedelta(days=14), datetime.min.time()))
            
            # Status
            if end < date.today():
                data["status"].append("completed")
                data["actual_spend_usd"].append(data["budget_usd"][i] * np.random.uniform(0.9, 1.1))
            elif start < date.today():
                data["status"].append("active")
                data["actual_spend_usd"].append(data["budget_usd"][i] * np.random.uniform(0.1, 0.8))
            else:
                data["status"].append("planned")
                data["actual_spend_usd"].append(0.0)
                
            # Geo / Channels
            m_faker = self.market_fakers[data["country_code"][i]]
            data["regions"].append([m_faker.administrative_unit() for _ in range(3)])
            data["channels"].append(np.random.choice(["meta", "youtube", "tiktok", "display", "ctv", "search"], size=np.random.randint(1, 4), replace=False).tolist())

        return pa.Table.from_pydict(data, schema=self.get_schema())

    def get_schema(self) -> pa.Schema:
        return pa.schema([
            ("campaign_id", pa.string()),
            ("campaign_name", pa.string()),
            ("brand", pa.string()),
            ("advertiser", pa.string()),
            ("product_category", pa.string()),
            ("country_code", pa.string()),
            ("regions", pa.list_(pa.string())),
            ("channels", pa.list_(pa.string())),
            ("objective", pa.string()),
            ("budget_usd", pa.float64()),
            ("actual_spend_usd", pa.float64()),
            ("start_date", pa.date32()),
            ("end_date", pa.date32()),
            ("status", pa.string()),
            ("created_at", pa.timestamp('us'))
        ])
