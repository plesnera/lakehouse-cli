import uuid
from datetime import datetime, date, timedelta
import numpy as np
import pyarrow as pa
from generators.base import BaseGenerator

class PixelEventGenerator(BaseGenerator):
    def generate(self, **kwargs) -> pa.Table:
        return next(self.generate_batches(self.config.n_pixel_events, **kwargs))

    def generate_batches(self, batch_size: int = 100000, **kwargs):
        n_total = self.config.n_pixel_events
        n_generated = 0
        
        while n_generated < n_total:
            n_batch = min(batch_size, n_total - n_generated)
            yield self._generate_batch(n_batch, **kwargs)
            n_generated += n_batch

    def _generate_batch(self, n, **kwargs) -> pa.Table:
        cookies = kwargs.get("cookies")
        campaigns = kwargs.get("campaigns")
        creatives = kwargs.get("creatives")
        
        if cookies is None or campaigns is None or creatives is None:
            raise ValueError("Cookies, Campaigns, and Creatives tables required for Pixel Events")
            
        cookie_ids = cookies.column("cookie_id").to_pylist()
        campaign_ids = campaigns.column("campaign_id").to_pylist()
        campaign_lookup = {
            c_id: {
                "start": campaigns.column("start_date")[i].as_py(),
                "end": campaigns.column("end_date")[i].as_py(),
                "market": campaigns.column("country_code")[i].as_py(),
                "budget": campaigns.column("budget_usd")[i].as_py()
            } for i, c_id in enumerate(campaign_ids)
        }
        
        creative_ids = creatives.column("creative_id").to_pylist()
        creative_to_campaign = {
            cr_id: creatives.column("campaign_id")[i].as_py()
            for i, cr_id in enumerate(creative_ids)
        }
        creative_to_channel = {
            cr_id: creatives.column("channel")[i].as_py()
            for i, cr_id in enumerate(creative_ids)
        }

        data = {
            "event_id": [str(uuid.uuid4()) for _ in range(n)],
            "event_type": [np.random.choice(["impression", "click", "video_start", "video_complete", "engagement"], p=[0.7, 0.15, 0.05, 0.05, 0.05]) for _ in range(n)],
            "cookie_id": [],
            "campaign_id": [],
            "creative_id": [np.random.choice(creative_ids) for _ in range(n)],
            "channel": [],
            "placement": [np.random.choice(["feed", "sidebar", "pre-roll", "mid-roll", "search_results"]) for _ in range(n)],
            "country_code": [],
            "region": [],
            "lat": [],
            "lon": [],
            "device_type": [np.random.choice(["desktop", "mobile", "tablet", "ctv"], p=[0.2, 0.6, 0.1, 0.1]) for _ in range(n)],
            "spend_usd": [],
            "event_ts": [],
            "event_date": [],
            "partition_date": []
        }

        for i in range(n):
            cr_id = data["creative_id"][i]
            c_id = creative_to_campaign[cr_id]
            camp = campaign_lookup[c_id]
            
            data["campaign_id"].append(c_id)
            data["channel"].append(creative_to_channel[cr_id])
            data["country_code"].append(camp["market"])
            
            m_faker = self.market_fakers[camp["market"]]
            data["region"].append(m_faker.administrative_unit())
            
            # Times (within campaign window)
            delta = (camp["end"] - camp["start"]).days
            event_date = camp["start"] + timedelta(days=np.random.randint(0, delta))
            event_ts = datetime.combine(event_date, datetime.min.time()) + timedelta(seconds=np.random.randint(0, 86400))
            data["event_ts"].append(event_ts)
            data["event_date"].append(event_date)
            data["partition_date"].append(event_date)
            
            # Cookie (82% fill)
            if np.random.random() < self.config.pixel_cookie_fill_rate:
                data["cookie_id"].append(np.random.choice(cookie_ids))
            else:
                data["cookie_id"].append(None)
                
            # Spend (approx CPM)
            if data["event_type"][i] == "impression":
                data["spend_usd"].append(np.random.uniform(0.005, 0.015)) # Pro-rated CPM
            else:
                data["spend_usd"].append(0.0)

            # Geo (50% fill)
            if np.random.random() < 0.5:
                loc = m_faker.local_latlng(country_code=camp["market"])
                data["lat"].append(float(loc[0]))
                data["lon"].append(float(loc[1]))
            else:
                data["lat"].append(None)
                data["lon"].append(None)

        return pa.Table.from_pydict(data, schema=self.get_schema())

    def get_schema(self) -> pa.Schema:
        return pa.schema([
            ("event_id", pa.string()),
            ("event_type", pa.string()),
            ("cookie_id", pa.string()),
            ("campaign_id", pa.string()),
            ("creative_id", pa.string()),
            ("channel", pa.string()),
            ("placement", pa.string()),
            ("country_code", pa.string()),
            ("region", pa.string()),
            ("lat", pa.float64()),
            ("lon", pa.float64()),
            ("device_type", pa.string()),
            ("spend_usd", pa.float64()),
            ("event_ts", pa.timestamp('us')),
            ("event_date", pa.date32()),
            ("partition_date", pa.date32())
        ])
