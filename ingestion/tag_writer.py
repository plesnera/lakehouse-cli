import subprocess
import os
import tempfile
import json
from google.protobuf import field_mask_pb2
from generators.config import GeneratorConfig
from google.cloud import dataplex_v1
from ingestion.table_metadata import load_all_table_metadata

class TagWriter:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.client = dataplex_v1.CatalogServiceClient()

    def ensure_tag_template(self):
        parent = f"projects/{self.config.catalog_project_id}/locations/{self.config.location}"
        aspect_type_id = "marketing-table-metadata"
        aspect_type_path = f"{parent}/aspectTypes/{aspect_type_id}"

        try:
            self.client.get_aspect_type(name=aspect_type_path)
            print(f"Aspect Type {aspect_type_id} exists.")
        except Exception:
            print(f"Creating Aspect Type via gcloud: {aspect_type_id}")
            
            # The structure for gcloud expects a slightly different format sometimes
            # Let's try to simplify or use the API more carefully.
            # Actually, let's just use the API but with a safer field mapping.
            try:
                aspect_type = dataplex_v1.AspectType(
                    display_name="Marketing Table Metadata",
                )
                # We'll set the metadata_spec fields manually if possible or just use gcloud correctly
                # Re-trying gcloud with the correct flag name
                metadata_spec = {
                    "name": "MarketingTableMetadata",
                    "type": "record",
                    "recordFields": [
                        {"name": "business_owner", "type": "string", "index": 1},
                        {"name": "data_domain", "type": "string", "index": 2},
                        {"name": "pii_class", "type": "string", "index": 3},
                        {"name": "refresh_cadence", "type": "string", "index": 4},
                        {"name": "row_count_approx", "type": "double", "index": 5},
                        {"name": "marketing_usecases", "type": "string", "index": 6}
                    ]
                }

                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tf:
                    json.dump(metadata_spec, tf)
                    temp_path = tf.name

                try:
                    cmd = [
                        "gcloud", "dataplex", "aspect-types", "create", aspect_type_id,
                        f"--location={self.config.location}",
                        "--display-name=Marketing Table Metadata",
                        f"--metadata-template-file-name={temp_path}"
                    ]
                    subprocess.run(cmd, check=True)
                    print(f"Successfully created Aspect Type: {aspect_type_id}")
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            except Exception as e:
                print(f"Warning: Could not create Aspect Type: {e}")

    def apply_tags(self):
        """Apply marketing_table_metadata aspect to each table entry.

        Tag values are read from the ``## Tags`` section of each table's
        markdown file in ``metadata_descriptions/``.  Edit those files to
        change what gets applied to Dataplex entries.
        """
        parent = f"projects/{self.config.project_id}/locations/{self.config.location}"
        entry_group_path = f"{parent}/entryGroups/marketing-lakehouse"
        aspect_type_id = "marketing-table-metadata"

        all_meta = load_all_table_metadata()
        tables = ["audience", "cookie_registry", "campaigns", "creatives", "pixel_events", "transactions"]

        for table_name in tables:
            meta = all_meta.get(table_name)
            if not meta or not meta.tags:
                print(f"  ⚠️  No tags found in metadata for {table_name} — skipping")
                continue
            fields = meta.tags
            entry_path = f"{entry_group_path}/entries/{table_name}"
            aspect_key = f"{self.config.project_id}.{self.config.location}.{aspect_type_id}"

            try:
                # Build the aspect with field values
                # Build aspect data dynamically from the parsed tags
                aspect_data = {}
                for k, v in fields.items():
                    if k == "row_count_approx":
                        aspect_data[k] = float(v)
                    else:
                        aspect_data[k] = str(v)

                aspect = dataplex_v1.Aspect(
                    aspect_type=f"{parent}/aspectTypes/{aspect_type_id}",
                    data=aspect_data,
                )

                update_entry = dataplex_v1.Entry(name=entry_path)
                update_entry.aspects[aspect_key] = aspect

                self.client.update_entry(
                    request=dataplex_v1.UpdateEntryRequest(
                        entry=update_entry,
                        update_mask=field_mask_pb2.FieldMask(paths=["aspects"]),
                        aspect_keys=[aspect_key],
                    )
                )
                print(f"  ✅ Applied tag to {table_name}")

            except Exception as e:
                print(f"  ⚠️  Failed to tag {table_name}: {e}")

        print("Tag application complete.")
