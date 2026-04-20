from google.cloud import dataplex_v1
from generators.config import GeneratorConfig

class DataplexManager:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.client = dataplex_v1.DataplexServiceClient()

    def ensure_topology(self):
        lake_id = "demo-data"
        lake_path = f"{self.config.catalog_resource_parent}/lakes/{lake_id}"

        # 1. Lake
        try:
            self.client.get_lake(name=lake_path)
            print(f"Lake {lake_id} exists.")
        except Exception:
            lake = dataplex_v1.Lake(display_name="Demo Marketing Lake")
            operation = self.client.create_lake(
                parent=self.config.catalog_resource_parent,
                lake_id=lake_id,
                lake=lake
            )
            operation.result()
            print(f"Created Lake: {lake_id}")

        # 2. Zone - single curated zone (lightweight architecture)
        zone_id = "curated-data"
        zone_path = f"{lake_path}/zones/{zone_id}"
        try:
            self.client.get_zone(name=zone_path)
            print(f"Zone {zone_id} exists.")
        except Exception:
            zone = dataplex_v1.Zone(
                display_name="Curated Data",
                type_=dataplex_v1.Zone.Type.CURATED,
                resource_spec=dataplex_v1.Zone.ResourceSpec(
                    location_type=dataplex_v1.Zone.ResourceSpec.LocationType.SINGLE_REGION
                )
            )
            operation = self.client.create_zone(
                parent=lake_path,
                zone_id=zone_id,
                zone=zone
            )
            operation.result()
            print(f"Created Zone: {zone_id}")

    def register_assets(self):
        # Map BigLake BQ dataset as asset in curated-data zone
        lake_path = f"{self.config.resource_parent}/lakes/demo-data"
        zone_id = "curated-data"
        asset_id = "marketing-dataset"
        asset_path = f"{lake_path}/zones/{zone_id}/assets/{asset_id}"

        try:
            self.client.get_asset(name=asset_path)
            print(f"Asset {asset_id} exists.")
        except Exception:
            asset = dataplex_v1.Asset(
                display_name="Marketing BigQuery Dataset",
                resource_spec=dataplex_v1.Asset.ResourceSpec(
                    name=f"projects/{self.config.project_id}/datasets/{self.config.iceberg_namespace}",
                    type_=dataplex_v1.Asset.ResourceSpec.Type.BIGQUERY_DATASET
                )
            )
            operation = self.client.create_asset(
                parent=f"{lake_path}/zones/{zone_id}",
                asset_id=asset_id,
                asset=asset
            )
            operation.result()
            print(f"Created Asset: {asset_id}")
