import pyarrow as pa
from pyiceberg.catalog import load_catalog
from generators.config import GeneratorConfig
from typing import Dict, Generator, Tuple
import os

class IcebergWriter:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        
        # Using a local SQL catalog to manage the Iceberg metadata state locally 
        # while writing the actual data and metadata files to GCS.
        # This is a robust way to generate Iceberg-compliant structures in GCS
        # which can then be registered as BigLake tables.
        self.catalog = load_catalog("default", **{
            "type": "sql",
            "uri": "sqlite:///iceberg_catalog.db",
            "warehouse": self.config.iceberg_warehouse
        })

    def write_stream(self, stream: Generator[Tuple[str, pa.Table], None, None]):
        """Writes a stream of table batches to Iceberg."""
        tables_created = set()
        
        for name, table in stream:
            namespace = self.config.iceberg_namespace
            identifier = f"{namespace}.{name}"
            
            # Ensure namespace exists
            try:
                self.catalog.create_namespace(namespace)
                print(f"Created Iceberg namespace: {namespace}")
            except Exception:
                pass # Already exists
            
            if name not in tables_created:
                # Try to load, if fails, create
                try:
                    ice_table = self.catalog.load_table(identifier)
                    print(f"Appending to existing Iceberg table: {identifier}")
                    ice_table.append(table)
                    tables_created.add(name)
                except Exception:
                    print(f"Creating new Iceberg table: {identifier}")
                    from pyiceberg.io.pyarrow import _pyarrow_to_schema_without_ids
                    from pyiceberg.schema import assign_fresh_schema_ids
                    
                    ice_schema = _pyarrow_to_schema_without_ids(table.schema)
                    ice_schema = assign_fresh_schema_ids(ice_schema)
                    
                    if name in ["pixel_events", "transactions"]:
                        from pyiceberg.partitioning import PartitionSpec, PartitionField
                        from pyiceberg.transforms import IdentityTransform
                        
                        source_id = ice_schema.find_field("partition_date").field_id
                        spec = PartitionSpec(
                            PartitionField(
                                source_id=source_id,
                                field_id=1000,
                                transform=IdentityTransform(),
                                name="partition_date"
                            )
                        )
                        self.catalog.create_table(
                            identifier=identifier,
                            schema=ice_schema,
                            partition_spec=spec
                        ).append(table)
                    else:
                        self.catalog.create_table(
                            identifier=identifier,
                            schema=ice_schema
                        ).append(table)
                    tables_created.add(name)
            else:
                # Table already created in this run, just append
                ice_table = self.catalog.load_table(identifier)
                ice_table.append(table)

    def write_tables(self, tables: Dict[str, pa.Table]):
        """Legacy support for writing full tables."""
        def stream():
            for name, table in tables.items():
                yield name, table
        self.write_stream(stream())
