from google.cloud import dataplex_v1
from google.protobuf import field_mask_pb2
from lake_cli.config import Config, TABLES
from lake_cli.table_metadata import load_all_table_metadata


class CatalogManager:
    def __init__(self, config: Config):
        self.config = config
        self.client = dataplex_v1.CatalogServiceClient()

    def _build_entry_source(self, name: str, meta) -> dataplex_v1.EntrySource:
        """Build an EntrySource protobuf for a table entry."""
        display = meta.display_name if meta else name.replace("_", " ").title()
        description = meta.description if meta else ""
        resource = self.config.get_bq_resource_path(name)

        return dataplex_v1.EntrySource(
            display_name=display,
            description=description,
            resource=resource,
            system="BigQuery",
            platform="Google Cloud",
        )

    def ensure_entry_type(self, entry_type_id: str = "table"):
        """Create the custom entry type if it doesn't exist."""
        parent = self.config.catalog_resource_parent
        entry_type_path = f"{parent}/entryTypes/{entry_type_id}"

        try:
            self.client.get_entry_type(name=entry_type_path)
            print(f"Entry Type {entry_type_id} exists.")
        except Exception:
            entry_type = dataplex_v1.EntryType(
                display_name=entry_type_id.replace("-", " ").title(),
                description="Generic data table entry type for the marketing lakehouse.",
            )
            operation = self.client.create_entry_type(
                parent=parent,
                entry_type_id=entry_type_id,
                entry_type=entry_type,
            )
            operation.result()
            print(f"Created Entry Type: {entry_type_id}")

    def ensure_entry_group(self):
        parent = self.config.catalog_resource_parent
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
        ``metadata/*.yaml`` — edit those files to change what
        appears in the Dataplex Knowledge Catalog.
        """
        all_meta = load_all_table_metadata()

        for name in TABLES:
            entry_id = name
            entry_path = f"{self.config.entry_group_path}/entries/{entry_id}"
            meta = all_meta.get(name)
            display = meta.display_name if meta else name.replace("_", " ").title()
            entry_source = self._build_entry_source(name, meta)

            try:
                existing = self.client.get_entry(name=entry_path)
                # Update existing entry if entry_source is missing or bare
                if not existing.entry_source or not existing.entry_source.display_name:
                    updated = dataplex_v1.Entry(
                        name=entry_path,
                        entry_source=entry_source,
                    )
                    mask = field_mask_pb2.FieldMask(paths=["entry_source"])
                    self.client.update_entry(entry=updated, update_mask=mask)
                    print(f"Updated Entry: {entry_id} — {display}")
                else:
                    print(f"Entry {entry_id} exists.")
            except Exception:
                entry = dataplex_v1.Entry(
                    entry_type=f"{self.config.catalog_resource_parent}/entryTypes/table",
                    entry_source=entry_source,
                )
                self.client.create_entry(
                    parent=self.config.entry_group_path,
                    entry_id=entry_id,
                    entry=entry,
                )
                print(f"Created Entry: {entry_id} — {display}")
