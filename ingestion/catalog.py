from google.cloud import dataplex_v1
from generators.config import GeneratorConfig
from ingestion.table_metadata import load_all_table_metadata


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
        """Register per-table catalog entries with display names and descriptions.

        Display names and descriptions are read from
        ``metadata_descriptions/*.md`` — edit those files to change what
        appears in the Dataplex Knowledge Catalog.
        """
        parent = f"projects/{self.config.project_id}/locations/{self.config.location}/entryGroups/marketing-lakehouse"
        all_meta = load_all_table_metadata()
        tables = ["audience", "cookie_registry", "campaigns", "creatives", "pixel_events", "transactions"]

        for name in tables:
            entry_id = name
            entry_path = f"{parent}/entries/{entry_id}"
            meta = all_meta.get(name)
            display = meta.display_name if meta else name

            try:
                self.client.get_entry(name=entry_path)
                print(f"Entry {entry_id} exists.")
            except Exception:
                entry = dataplex_v1.Entry(
                    entry_type=f"projects/{self.config.project_id}/locations/{self.config.location}/entryTypes/table",
                )
                self.client.create_entry(
                    parent=parent,
                    entry_id=entry_id,
                    entry=entry,
                )
                print(f"Created Entry: {entry_id} — {display}")
