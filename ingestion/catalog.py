from google.cloud import dataplex_v1
from generators.config import GeneratorConfig

class CatalogManager:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.client = dataplex_v1.CatalogServiceClient()

    def ensure_entry_group(self):
        parent = f"projects/{self.config.project_id}/locations/{self.config.location}"
        entry_group_id = "marketing-lakehouse"
        entry_group_path = f"{parent}/entryGroups/{entry_group_id}"

        try:
            self.client.get_entry_group(name=entry_group_path)
            print(f"Entry Group {entry_group_id} exists.")
        except Exception:
            entry_group = dataplex_v1.EntryGroup(display_name="Marketing Lakehouse Assets")
            operation = self.client.create_entry_group(
                parent=parent,
                entry_group_id=entry_group_id,
                entry_group=entry_group
            )
            operation.result()
            print(f"Created Entry Group: {entry_group_id}")

    def register_entries(self):
        # Register per-table entries
        parent = f"projects/{self.config.project_id}/locations/{self.config.location}/entryGroups/marketing-lakehouse"
        tables = ["audience", "cookie_registry", "campaigns", "creatives", "pixel_events", "transactions"]
        
        # Descriptions from lakehouse-final.md
        descriptions = {
            "audience": "Modelled audience segments derived from panel survey data.",
            "cookie_registry": "Maps cookie identifiers to device metadata.",
            "pixel_events": "Event-level stream of ad tracking signals.",
            "campaigns": "Master record for advertising campaigns.",
            "creatives": "Catalogue of ad creative assets linked to campaigns.",
            "transactions": "Synthetic purchase transaction feed modelled on Mastercard merchant data."
        }

        for name in tables:
            entry_id = name
            entry_path = f"{parent}/entries/{entry_id}"
            
            try:
                self.client.get_entry(name=entry_path)
                print(f"Entry {entry_id} exists.")
            except Exception:
                # Entry for Dataplex Catalog 
                # Note: Using aspects for description is the modern Dataplex way
                entry = dataplex_v1.Entry(
                    entry_type=f"projects/{self.config.project_id}/locations/{self.config.location}/entryTypes/table"
                )
                self.client.create_entry(
                    parent=parent,
                    entry_id=entry_id,
                    entry=entry
                )
                print(f"Created Entry: {entry_id}")
