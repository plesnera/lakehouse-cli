import uuid
from datetime import datetime
import numpy as np
import pyarrow as pa
from generators.base import BaseGenerator

class CreativeGenerator(BaseGenerator):
    def generate(self, **kwargs) -> pa.Table:
        campaign_table = kwargs.get("campaigns")
        if campaign_table is None:
            raise ValueError("Campaign table required to generate creatives")
            
        campaign_ids = campaign_table.column("campaign_id").to_pylist()
        campaign_brands = campaign_table.column("brand").to_pylist()
        campaign_channels = campaign_table.column("channels").to_pylist()
        
        n_per_campaign = self.config.n_creatives_per_campaign
        n_total = len(campaign_ids) * n_per_campaign
        
        data = {
            "creative_id": [str(uuid.uuid4()) for _ in range(n_total)],
            "campaign_id": [],
            "creative_name": [],
            "format": [],
            "channel": [],
            "duration_seconds": [],
            "width_px": [],
            "height_px": [],
            "brand": [],
            "theme_tags": [],
            "created_at": []
        }

        formats = {
            "video_15s": {"duration": 15, "w": 1920, "h": 1080},
            "video_30s": {"duration": 30, "w": 1920, "h": 1080},
            "static_banner": {"duration": None, "w": 300, "h": 250},
            "carousel": {"duration": None, "w": 1080, "h": 1080},
            "stories": {"duration": 15, "w": 1080, "h": 1920}
        }

        for i, c_id in enumerate(campaign_ids):
            brand = campaign_brands[i]
            channels = campaign_channels[i]
            for j in range(n_per_campaign):
                fmt_key = np.random.choice(list(formats.keys()))
                fmt = formats[fmt_key]
                channel = np.random.choice(channels)
                
                data["campaign_id"].append(c_id)
                data["brand"].append(brand)
                data["channel"].append(channel)
                data["format"].append(fmt_key)
                data["creative_name"].append(f"{brand}_{fmt_key}_{i}_{j}")
                data["duration_seconds"].append(fmt["duration"])
                data["width_px"].append(fmt["w"])
                data["height_px"].append(fmt["h"])
                data["created_at"].append(datetime.now())
                data["theme_tags"].append(np.random.choice(["Minimalist", "High-Energy", "Educational", "Inspirational"], size=np.random.randint(1, 3)).tolist())

        return pa.Table.from_pydict(data, schema=self.get_schema())

    def get_schema(self) -> pa.Schema:
        return pa.schema([
            ("creative_id", pa.string()),
            ("campaign_id", pa.string()),
            ("creative_name", pa.string()),
            ("format", pa.string()),
            ("channel", pa.string()),
            ("duration_seconds", pa.int32()),
            ("width_px", pa.int32()),
            ("height_px", pa.int32()),
            ("brand", pa.string()),
            ("theme_tags", pa.list_(pa.string())),
            ("created_at", pa.timestamp('us'))
        ])
