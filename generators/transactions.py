import uuid
from datetime import datetime, date, timedelta
import numpy as np
import pyarrow as pa
from generators.base import BaseGenerator

class TransactionGenerator(BaseGenerator):
    def generate(self, **kwargs) -> pa.Table:
        return next(self.generate_batches(self.config.n_transactions, **kwargs))

    def generate_batches(self, batch_size: int = 10000, **kwargs):
        n_total = self.config.n_transactions
        n_generated = 0
        
        while n_generated < n_total:
            n_batch = min(batch_size, n_total - n_generated)
            yield self._generate_batch(n_batch, **kwargs)
            n_generated += n_batch

    def _generate_batch(self, n, **kwargs) -> pa.Table:
        cookies = kwargs.get("cookies")
        if cookies is None:
            raise ValueError("Cookies table required for Transactions")
            
        cookie_ids = cookies.column("cookie_id").to_pylist()
        cookie_to_hem = {
            cookies.column("cookie_id")[i].as_py(): cookies.column("hem")[i].as_py()
            for i in range(len(cookie_ids))
        }
        
        data = {
            "txn_id": [str(uuid.uuid4()) for _ in range(n)],
            "pan_token": [str(uuid.uuid4()).split('-')[0] for _ in range(n)],
            "cookie_id": [],
            "hem": [],
            "merchant_name": [],
            "merchant_category_code": [np.random.choice(["5411", "5812", "5311", "5912", "5651"]) for _ in range(n)],
            "brand": [],
            "amount_usd": np.random.exponential(50, n).tolist(),
            "currency_code": [],
            "country_code": [np.random.choice(self.config.target_markets) for _ in range(n)],
            "city": [],
            "lat": [],
            "lon": [],
            "channel": [np.random.choice(["in_store", "online", "contactless"]) for _ in range(n)],
            "txn_ts": [],
            "event_date": [],
            "partition_date": []
        }

        for i in range(n):
            market = data["country_code"][i]
            m_faker = self.market_fakers[market]
            
            data["merchant_name"].append(m_faker.company())
            from generators.config import BRANDS
            data["brand"].append(np.random.choice(BRANDS + ["Other"]))
            data["currency_code"].append("USD") # Simplified
            data["city"].append(m_faker.city())
            
            # Match rates
            rates = self.config.market_txn_rates.get(market)
            c_rate = rates.txn_cookie_fill_rate if rates else self.config.txn_cookie_fill_rate
            h_rate = rates.txn_hem_fill_rate if rates else self.config.txn_hem_fill_rate
            
            c_id = None
            hem = None
            if np.random.random() < c_rate:
                c_id = np.random.choice(cookie_ids)
                hem = cookie_to_hem[c_id] # Try to link via cookie
                
            if hem is None and np.random.random() < h_rate:
                # Fallback to random hem from cookie pool
                all_hems = [h for h in cookie_to_hem.values() if h is not None]
                if all_hems:
                    hem = np.random.choice(all_hems)

            data["cookie_id"].append(c_id)
            data["hem"].append(hem)
            
            # Times
            days_ago = np.random.randint(0, self.config.date_range_days)
            event_date = date.today() - timedelta(days=days_ago)
            txn_ts = datetime.combine(event_date, datetime.min.time()) + timedelta(seconds=np.random.randint(0, 86400))
            data["txn_ts"].append(txn_ts)
            data["event_date"].append(event_date)
            data["partition_date"].append(event_date)
            
            # Geo
            loc = m_faker.local_latlng(country_code=market)
            data["lat"].append(float(loc[0]))
            data["lon"].append(float(loc[1]))

        return pa.Table.from_pydict(data, schema=self.get_schema())

    def get_schema(self) -> pa.Schema:
        return pa.schema([
            ("txn_id", pa.string()),
            ("pan_token", pa.string()),
            ("cookie_id", pa.string()),
            ("hem", pa.string()),
            ("merchant_name", pa.string()),
            ("merchant_category_code", pa.string()),
            ("brand", pa.string()),
            ("amount_usd", pa.float64()),
            ("currency_code", pa.string()),
            ("country_code", pa.string()),
            ("city", pa.string()),
            ("lat", pa.float64()),
            ("lon", pa.float64()),
            ("channel", pa.string()),
            ("txn_ts", pa.timestamp('us')),
            ("event_date", pa.date32()),
            ("partition_date", pa.date32())
        ])
