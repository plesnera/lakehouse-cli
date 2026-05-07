#!/usr/bin/env python3
"""
Register existing Iceberg tables using DataprocSparkSession.

Matches the working BigLake Metastore example:
- Uses DataprocSparkSession with Session() configuration
- Configures BigQueryMetastoreCatalog
- Supports VPC subnet and location configuration
"""
import argparse
import json
import sys

from google.cloud.dataproc_spark_connect import DataprocSparkSession
from google.cloud.dataproc_v1 import Session


def register_tables(
    project_id: str,
    region: str,
    subnet_name: str,
    location: str,
    catalog: str,
    namespace: str,
    warehouse: str,
    tables: dict[str, str],
) -> bool:
    """Register existing Iceberg tables via Dataproc Serverless Spark."""
    # Create the Dataproc Serverless session.
    session = Session()
    session.environment_config.execution_config.subnetwork_uri = subnet_name

    # Set catalog properties for BigQuery Metastore.
    props = session.runtime_config.properties
    props[f"spark.sql.catalog.{catalog}"] = "org.apache.iceberg.spark.SparkCatalog"
    props[f"spark.sql.catalog.{catalog}.catalog-impl"] = (
        "org.apache.iceberg.gcp.bigquery.BigQueryMetastoreCatalog"
    )
    props[f"spark.sql.catalog.{catalog}.gcp_project"] = project_id
    props[f"spark.sql.catalog.{catalog}.gcp_location"] = location
    props[f"spark.sql.catalog.{catalog}.warehouse"] = warehouse

    # Create the Spark Connect session.
    spark = (
        DataprocSparkSession.builder.appName("register-iceberg-tables")
        .dataprocSessionConfig(session)
        .getOrCreate()
    )

    # Ensure namespace exists.
    spark.sql(f"USE `{catalog}`;")
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS `{namespace}`;")
    spark.sql(f"USE `{namespace}`;")

    registered = 0
    failed = 0

    for table_name, metadata_location in tables.items():
        try:
            spark.sql(
                f"CALL `{catalog}`.system.register_table("
                f"table => '{namespace}.{table_name}', "
                f"metadata_file => '{metadata_location}' )"
            )
            print(f"Registered: {table_name}")
            registered += 1
        except Exception as e:
            err = str(e)
            if "already exists" in err.lower() or "already registered" in err.lower():
                print(f"Already registered: {table_name}")
                registered += 1
            else:
                print(f"Failed to register {table_name}: {err}")
                failed += 1

    print(f"Done: {registered} registered, {failed} failed")
    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Register Iceberg tables")
    parser.add_argument("--project-id", required=True, help="GCP project ID")
    parser.add_argument("--region", default="us-east1", help="Dataproc region")
    parser.add_argument(
        "--subnet-name", default="dataproc-subnet", help="VPC subnet name"
    )
    parser.add_argument(
        "--location", default="us-east1", help="BigQuery / BigLake location"
    )
    parser.add_argument("--catalog", required=True, help="Catalog name")
    parser.add_argument("--namespace", default="marketing", help="Namespace")
    parser.add_argument("--warehouse", required=True, help="GCS warehouse path")
    parser.add_argument(
        "--tables",
        required=True,
        help="JSON dict of table_name -> metadata_location",
    )

    args = parser.parse_args()
    tables = json.loads(args.tables)

    success = register_tables(
        project_id=args.project_id,
        region=args.region,
        subnet_name=args.subnet_name,
        location=args.location,
        catalog=args.catalog,
        namespace=args.namespace,
        warehouse=args.warehouse,
        tables=tables,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
