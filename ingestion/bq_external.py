from google.cloud import bigquery
from generators.config import GeneratorConfig

class BigLakeRegistrar:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.client = bigquery.Client(project=config.catalog_project_id)

    def register_tables(self):
        dataset_id = f"{self.config.catalog_project_id}.{self.config.iceberg_namespace}"
        
        # Ensure dataset exists
        try:
            self.client.get_dataset(dataset_id)
        except Exception:
            dataset = bigquery.Dataset(dataset_id)
            dataset.location = self.config.location
            self.client.create_dataset(dataset)
            print(f"Created dataset: {dataset_id}")

        tables = ["audience", "cookie_registry", "campaigns", "creatives", "pixel_events", "transactions"]
        
        from google.cloud import storage
        # Use data project for storage access (supports cross-project)
        storage_client = storage.Client(project=self.config.data_project_id)
        bucket_name = self.config.iceberg_warehouse.replace("gs://", "").split("/")[0]
        bucket = storage_client.bucket(bucket_name)

        for name in tables:
            table_id = f"{dataset_id}.{name}"
            
            # Find the latest metadata file
            prefix = f"iceberg/{self.config.iceberg_namespace}/{name}/metadata/"
            blobs = list(storage_client.list_blobs(bucket, prefix=prefix))
            metadata_json_files = [b.name for b in blobs if b.name.endswith(".metadata.json")]
            
            if not metadata_json_files:
                print(f"No metadata files found for {name} at {prefix}")
                continue
                
            # Iceberg metadata files are named 00000-<uuid>.metadata.json, 00001-...
            # Sorting will give us the latest version
            latest_metadata = sorted(metadata_json_files)[-1]
            metadata_uri = f"gs://{bucket_name}/{latest_metadata}"
            
            print(f"Using metadata URI for {name}: {metadata_uri}")

            # Connection ID format for BigLake - use catalog project and handle template
            if "{project_id}" in self.config.biglake_connection:
                connection_id = self.config.biglake_connection.replace("{project_id}", self.config.catalog_project_id).replace("{location}", self.config.location)
            else:
                # Backward compatibility for non-template format
                connection_id = f"{self.config.catalog_project_id}.{self.config.location}.biglake-conn"
            
            external_config = bigquery.ExternalConfig("ICEBERG")
            external_config.source_uris = [metadata_uri]
            external_config.connection_id = connection_id
            
            table = bigquery.Table(table_id)
            table.external_data_configuration = external_config
            
            try:
                self.client.delete_table(table_id, not_found_ok=True)
                self.client.create_table(table)
                print(f"Registered BigLake Iceberg table: {table_id}")
            except Exception as e:
                print(f"Failed to register table {name}: {e}")
