import subprocess
import os
import tempfile
import json
from generators.config import GeneratorConfig
from google.cloud import dataplex_v1

class TagWriter:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.client = dataplex_v1.CatalogServiceClient()

    def ensure_tag_template(self):
        parent = f"projects/{self.config.project_id}/locations/{self.config.location}"
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
        print("Note: Automated tagging skipped.")
