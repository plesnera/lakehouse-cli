import uuid
from datetime import datetime, timedelta
import numpy as np
import pyarrow as pa
from generators.base import BaseGenerator

class CookieRegistryGenerator(BaseGenerator):
    def generate(self, **kwargs) -> pa.Table:
        audience_table = kwargs.get("audience")
        if audience_table is None:
            raise ValueError("Audience table required for Cookie Registry")
            
        audience_ids = audience_table.column("audience_id").to_pylist()
        audience_hems = audience_table.column("hem").to_pylist()
        # Filter for non-null hems for shared pool
        shared_hems = [h for h in audience_hems if h is not None]
        
        n = self.config.n_cookies
        data = {
            "cookie_id": [str(uuid.uuid4()) for _ in range(n)],
            "visitor_id": [], # Synonym
            "device_id": [],  # Synonym
            "audience_id": [],
            "hem": [],
            "hashed_email": [], # Synonym
            "country_code": [np.random.choice(self.config.target_markets) for _ in range(n)],
            "city": [],
            "lat": [],
            "lon": [],
            "device_type": [np.random.choice(["desktop", "mobile", "tablet", "ctv"], p=[0.2, 0.6, 0.1, 0.1]) for _ in range(n)],
            "browser": [np.random.choice(["Chrome", "Safari", "Firefox", "App", "Unknown"]) for _ in range(n)],
            "first_seen_at": [],
            "last_seen_at": []
        }

        data["visitor_id"] = data["cookie_id"]
        data["device_id"] = data["cookie_id"]

        for i in range(n):
            market = data["country_code"][i]
            m_faker = self.market_fakers[market]
            
            # Fill IDs
            if np.random.random() < self.config.cookie_audience_fill_rate:
                # Random sample from audience
                idx = np.random.randint(0, len(audience_ids))
                data["audience_id"].append(audience_ids[idx])
                # If they have an audience ID, they are more likely to have a hem (logged in)
                if audience_hems[idx] is not None and np.random.random() < 0.8:
                    h = audience_hems[idx]
                    data["hem"].append(h)
                    data["hashed_email"].append(h)
                else:
                    data["hem"].append(None)
                    data["hashed_email"].append(None)
            else:
                data["audience_id"].append(None)
                # Global hem pool
                if np.random.random() < self.config.cookie_hem_fill_rate and shared_hems:
                    h = np.random.choice(shared_hems)
                    data["hem"].append(h)
                    data["hashed_email"].append(h)
                else:
                    data["hem"].append(None)
                    data["hashed_email"].append(None)

            # Geo
            loc = m_faker.local_latlng(country_code=market)
            data["city"].append(m_faker.city())
            data["lat"].append(float(loc[0]))
            data["lon"].append(float(loc[1]))
            
            # Times
            last = datetime.now() - timedelta(days=np.random.randint(0, 30))
            first = last - timedelta(days=np.random.randint(0, 330))
            data["first_seen_at"].append(first)
            data["last_seen_at"].append(last)

        return pa.Table.from_pydict(data, schema=self.get_schema())

    def get_schema(self) -> pa.Schema:
        return pa.schema([
            ("cookie_id", pa.string()),
            ("visitor_id", pa.string()),
            ("device_id", pa.string()),
            ("audience_id", pa.string()),
            ("hem", pa.string()),
            ("hashed_email", pa.string()),
            ("country_code", pa.string()),
            ("city", pa.string()),
            ("lat", pa.float64()),
            ("lon", pa.float64()),
            ("device_type", pa.string()),
            ("browser", pa.string()),
            ("first_seen_at", pa.timestamp('us')),
            ("last_seen_at", pa.timestamp('us'))
        ])
