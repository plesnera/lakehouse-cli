import uuid
from datetime import datetime
import numpy as np
import pyarrow as pa
from generators.base import BaseGenerator
import hashlib

class AudienceGenerator(BaseGenerator):
    def generate(self, **kwargs) -> pa.Table:
        n = self.config.n_audience_participants
        data = {
            "audience_id": [str(uuid.uuid4()) for _ in range(n)],
            "segment_name": self._generate_segments(n),
            "country_code": [np.random.choice(self.config.target_markets) for _ in range(n)],
            "region": [],
            "age_band": [np.random.choice(["18-24", "25-34", "35-44", "45-54", "55+"]) for _ in range(n)],
            "gender": [np.random.choice(["M", "F", "NB", "Unknown"], p=[0.48, 0.48, 0.02, 0.02]) for _ in range(n)],
            "income_band": [np.random.choice(["Low", "Mid", "High"], p=[0.3, 0.5, 0.2]) for _ in range(n)],
            "interests": [self._generate_interests() for _ in range(n)],
            "brand_affinity_scores": [self._generate_affinity() for _ in range(n)],
            "channel_index": [self._generate_channel_index() for _ in range(n)],
            "hem": [],
            "lat": [],
            "lon": [],
            "location_lat": [],
            "location_lon": [],
            "panel_weight": np.random.uniform(0.5, 2.0, n).tolist(),
            "created_at": [datetime.now() for _ in range(n)]
        }

        for i in range(n):
            market = data["country_code"][i]
            m_faker = self.market_fakers[market]
            
            # Geo
            loc = m_faker.local_latlng(country_code=market)
            lat, lon = float(loc[0]), float(loc[1])
            # Add small gaussian noise
            lat += np.random.normal(0, 0.05)
            lon += np.random.normal(0, 0.05)
            
            data["lat"].append(lat)
            data["lon"].append(lon)
            data["location_lat"].append(lat)
            data["location_lon"].append(lon)
            data["region"].append(m_faker.administrative_unit())
            
            # HEM (60% fill rate)
            if np.random.random() < self.config.audience_hem_fill_rate:
                email = m_faker.email()
                hem = hashlib.sha256(email.lower().strip().encode()).hexdigest()
                data["hem"].append(hem)
            else:
                data["hem"].append(None)

        return pa.Table.from_pydict(data, schema=self.get_schema())

    def _generate_segments(self, n):
        segments = [f"Segment_{i}" for i in range(self.config.n_audience_segments)]
        return [np.random.choice(segments) for _ in range(n)]

    def _generate_interests(self):
        possible = ["Sports", "Tech", "Fashion", "Travel", "Food", "Finance", "Auto", "Health"]
        return np.random.choice(possible, size=np.random.randint(1, 5), replace=False).tolist()

    def _generate_affinity(self):
        brands = ["BrandA", "BrandB", "BrandC", "BrandD"]
        return {b: round(np.random.random(), 3) for b in brands}

    def _generate_channel_index(self):
        channels = ["meta", "youtube", "tiktok", "display", "ctv", "search"]
        return {c: round(np.random.uniform(0.5, 2.0), 2) for c in channels}

    def get_schema(self) -> pa.Schema:
        return pa.schema([
            ("audience_id", pa.string()),
            ("segment_name", pa.string()),
            ("country_code", pa.string()),
            ("region", pa.string()),
            ("age_band", pa.string()),
            ("gender", pa.string()),
            ("income_band", pa.string()),
            ("interests", pa.list_(pa.string())),
            ("brand_affinity_scores", pa.map_(pa.string(), pa.float32())),
            ("channel_index", pa.map_(pa.string(), pa.float32())),
            ("hem", pa.string()),
            ("lat", pa.float64()),
            ("lon", pa.float64()),
            ("location_lat", pa.float64()),
            ("location_lon", pa.float64()),
            ("panel_weight", pa.float64()),
            ("created_at", pa.timestamp('us'))
        ])
