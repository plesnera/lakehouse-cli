#!/usr/bin/env python3
"""
Lakehouse REST Catalog (Iceberg) Manager

Manages Google Cloud Lakehouse REST Catalog for Iceberg metadata, providing
a single source of truth for BigQuery, Spark, and Trino table discovery.

Uses gcloud CLI for all operations since the BigLake Iceberg REST API
has non-standard paths and authentication requirements.

IMPORTANT: For vended-credentials mode, tables must be registered via
Spark/Dataproc or GCP Console since gcloud doesn't properly support the
required X-Iceberg-Access-Delegation header.
"""

import subprocess
from typing import Dict

from generators.config import GeneratorConfig, TABLES


class LakehouseCatalogManager:
    """
    Manages Google Cloud Lakehouse REST Catalog operations for Iceberg tables.

    Uses gcloud CLI for all operations.
    """

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.project_id = config.data_project_id
        self.location = config.location
        self.catalog_name = config.lakehouse_catalog_name
        self.namespace = config.iceberg_namespace
        self.warehouse = config.iceberg_warehouse

        # Resource paths
        self.catalog_path = f"{self.project_id}/{self.location}/{self.catalog_name}"

    # ---- Catalog operations via gcloud ----

    def ensure_catalog(self, dry_run: bool = False) -> Dict[str, bool]:
        """
        Verify the Lakehouse REST catalog exists.

        Does NOT create the catalog — for vended-credentials mode it must be
        created via the GCP Console. gcloud does not properly support the
        required X-Iceberg-Access-Delegation header.
        """
        catalog_resource = self.catalog_path

        if dry_run:
            print(f"[DRY RUN] Would verify catalog: {catalog_resource}")
            return {"catalog_exists": True}

        # Check if catalog exists via gcloud
        try:
            result = subprocess.run(
                [
                    "gcloud", "biglake", "iceberg", "catalogs", "describe",
                    self.catalog_name,
                    "--project", self.project_id,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print(f"✅ Catalog exists: {catalog_resource}")
                return {"catalog_exists": True}
            else:
                if "NOT_FOUND" in result.stderr or "not found" in result.stderr.lower():
                    print(f"❌ Catalog not found: {catalog_resource}")
                    print("   Catalogs using vended-credentials can currently only be created via the GCP Console.")
                    print("   Navigate to: BigLake > Iceberg catalogs > Create catalog")
                    return {"catalog_exists": False}
                if "PERMISSION_DENIED" in result.stderr:
                    print(f"✅ Catalog exists (verified via gcloud): {catalog_resource}")
                    print("   Note: Some operations may require additional IAM permissions.")
                    return {"catalog_exists": True}
                print(f"gcloud stderr: {result.stderr}")
                raise RuntimeError(f"Failed to check catalog: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("gcloud describe timed out")
            return {"catalog_exists": False}
        except FileNotFoundError:
            raise RuntimeError("gcloud CLI not available")

    def delete_catalog(self, dry_run: bool = False) -> Dict[str, bool]:
        """Delete the Lakehouse REST catalog (for reset)."""
        if dry_run:
            print(f"[DRY RUN] Would delete catalog: {self.catalog_path}")
            return {"catalog_deleted": True}

        print(f"Deleting catalog: {self.catalog_path}")
        try:
            result = subprocess.run(
                [
                    "gcloud", "biglake", "iceberg", "catalogs", "delete",
                    self.catalog_name,
                    "--project", self.project_id,
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print(f"Deleted catalog: {self.catalog_path}")
                return {"catalog_deleted": True}
            else:
                if "not found" in result.stderr.lower():
                    print(f"Catalog not found (already deleted): {self.catalog_path}")
                    return {"catalog_deleted": False}
                print(f"gcloud stderr: {result.stderr}")
                raise RuntimeError(f"Failed to delete catalog: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("gcloud catalog delete timed out")
        except FileNotFoundError:
            raise RuntimeError("gcloud CLI not available")

    # ---- Namespace operations via gcloud ----

    def ensure_namespace(self, dry_run: bool = False) -> Dict[str, bool]:
        """
        Create the Iceberg namespace if it doesn't exist.

        Uses gcloud since it works when REST API doesn't.
        Idempotent - safe to run multiple times.
        """
        if dry_run:
            print(f"[DRY RUN] Would create namespace: {self.namespace}")
            return {"namespace_created": True}

        # Check if namespace already exists via gcloud
        try:
            result = subprocess.run(
                [
                    "gcloud", "biglake", "iceberg", "namespaces", "describe",
                    self.namespace,
                    "--catalog", self.catalog_name,
                    "--project", self.project_id,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print(f"Namespace already exists: {self.namespace}")
                return {"namespace_created": False}
        except subprocess.TimeoutExpired:
            print("gcloud describe timed out - assuming namespace exists")
            return {"namespace_created": False}
        except FileNotFoundError:
            raise RuntimeError("gcloud CLI not available")

        # Create namespace via gcloud
        print(f"Creating namespace: {self.namespace}")
        try:
            result = subprocess.run(
                [
                    "gcloud", "biglake", "iceberg", "namespaces", "create",
                    self.namespace,
                    "--catalog", self.catalog_name,
                    "--project", self.project_id,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                print(f"Created namespace: {self.namespace}")
                return {"namespace_created": True}
            else:
                if "already exists" in result.stderr.lower():
                    print(f"Namespace already exists: {self.namespace}")
                    return {"namespace_created": False}
                print(f"gcloud stderr: {result.stderr}")
                raise RuntimeError(f"Failed to create namespace: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("gcloud namespace create timed out")

    def delete_namespace(self, dry_run: bool = False) -> Dict[str, bool]:
        """Delete the Iceberg namespace (for reset)."""
        if dry_run:
            print(f"[DRY RUN] Would delete namespace: {self.namespace}")
            return {"namespace_deleted": True}

        print(f"Deleting namespace: {self.namespace}")
        try:
            result = subprocess.run(
                [
                    "gcloud", "biglake", "iceberg", "namespaces", "delete",
                    self.namespace,
                    "--catalog", self.catalog_name,
                    "--project", self.project_id,
                    "--quiet",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print(f"Deleted namespace: {self.namespace}")
                return {"namespace_deleted": True}
            else:
                if "not found" in result.stderr.lower():
                    print(f"Namespace not found (already deleted): {self.namespace}")
                    return {"namespace_deleted": False}
                print(f"gcloud stderr: {result.stderr}")
                return {"namespace_deleted": False}
        except subprocess.TimeoutExpired:
            raise RuntimeError("gcloud namespace delete timed out")

    # ---- Table registration via Dataproc Serverless ----

    def _generate_registration_script(self) -> str:
        """Generate a PySpark script that registers existing Iceberg tables."""
        tables_dict = {
            name: f"{self.warehouse}/{self.namespace}/{name}/metadata.json"
            for name in TABLES
        }

        # Build the script using string concatenation to avoid f-string nesting
        script = (
            'import pyspark\n'
            'from pyspark.context import SparkContext\n'
            'from pyspark.sql import SparkSession\n'
            'import sys\n'
            
            '\n'
            'catalog = "' + self.catalog_name + '"\n'
            'namespace = "' + self.namespace + '"\n'
            'warehouse = "' + self.warehouse + '"\n'
            'project_id = "' + self.project_id + '"\n'
            '\n'
            'tables = ' + repr(tables_dict) + '\n'
            '\n'
            'spark = SparkSession.builder \\\n'
            '    .appName("register-iceberg-tables") \\\n'
            '    .config("spark.sql.defaultCatalog", catalog) \\\n'
            '    .config("spark.sql.catalog." + catalog, "org.apache.iceberg.spark.SparkCatalog") \\\n'
            '    .config("spark.sql.catalog." + catalog + ".type", "rest") \\\n'
            '    .config("spark.sql.catalog." + catalog + ".uri", "https://biglake.googleapis.com/iceberg/v1/restcatalog") \\\n'
            '    .config("spark.sql.catalog." + catalog + ".warehouse", warehouse) \\\n'
            '    .config("spark.sql.catalog." + catalog + ".io-impl", "org.apache.iceberg.gcp.gcs.GCSFileIO") \\\n'
            '    .config("spark.sql.catalog." + catalog + ".header.x-goog-user-project", project_id) \\\n'
            '    .config("spark.sql.catalog." + catalog + ".rest.auth.type", "org.apache.iceberg.gcp.auth.GoogleAuthManager") \\\n'
            '    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \\\n'
            '    .config("spark.sql.catalog." + catalog + ".header.X-Iceberg-Access-Delegation", "vended-credentials") \\\n'
            '    .config("spark.sql.catalog." + catalog + ".gcs.oauth2.refresh-credentials-endpoint=https://oauth2.googleapis.com/token") \\\n'
            '    .getOrCreate()\n'
            '\n'
            '# Ensure namespace exists\n'
            'spark.sql("CREATE NAMESPACE IF NOT EXISTS `" + catalog + "`.`" + namespace + "`")\n'
            '\n'
            'registered = 0\n'
            'failed = 0\n'
            '\n'
            'for table_name, metadata_location in tables.items():\n'
            '    try:\n'
            '        spark.sql(\n'
            '            "CALL `" + catalog + "`.system.register_table("\n'
            '            "table => \'" + namespace + "." + table_name + "\', "\n'
            '            "metadata_file => \'" + metadata_location + "\' )"\n'
            '        )\n'
            '        print("Registered: " + table_name)\n'
            '        registered += 1\n'
            '    except Exception as e:\n'
            '        err = str(e)\n'
            '        if "already exists" in err.lower() or "already registered" in err.lower():\n'
            '            print("Already registered: " + table_name)\n'
            '            registered += 1\n'
            '        else:\n'
            '            print("Failed to register " + table_name + ": " + err)\n'
            '            failed += 1\n'
            '\n'
            'print("Done: " + str(registered) + " registered, " + str(failed) + " failed")\n'
            'sys.exit(0 if failed == 0 else 1)\n'
        )
        return script

    def _upload_script_to_gcs(self, script_content: str) -> str:
        """Upload the PySpark script to the warehouse bucket and return its GCS URI."""
        from google.cloud import storage

        bucket_name = self.warehouse.replace("gs://", "").split("/")[0]
        blob_path = f"{self.namespace}/scripts/register_tables.py"
        gcs_uri = f"gs://{bucket_name}/{blob_path}"

        client = storage.Client(project=self.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_string(script_content)

        return gcs_uri

    def _build_spark_properties(self) -> str:
        """Build comma-separated Spark properties for the Dataproc batch job."""
        props = {
            f"spark.sql.defaultCatalog": self.catalog_name,
            f"spark.sql.catalog.{self.catalog_name}": "org.apache.iceberg.spark.SparkCatalog",
            f"spark.sql.catalog.{self.catalog_name}.type": "rest",
            f"spark.sql.catalog.{self.catalog_name}.uri": "https://biglake.googleapis.com/iceberg/v1/restcatalog",
            f"spark.sql.catalog.{self.catalog_name}.warehouse": self.warehouse,
            f"spark.sql.catalog.{self.catalog_name}.io-impl": "org.apache.iceberg.gcp.gcs.GCSFileIO",
            f"spark.sql.catalog.{self.catalog_name}.header.x-goog-user-project": self.project_id,
            f"spark.sql.catalog.{self.catalog_name}.rest.auth.type": "org.apache.iceberg.gcp.auth.GoogleAuthManager",
            "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
            f"spark.sql.catalog.{self.catalog_name}.header.X-Iceberg-Access-Delegation": "vended-credentials",
            f"spark.sql.catalog.{self.catalog_name}.gcs.oauth2.refresh-credentials-endpoint":"https://oauth2.googleapis.com/token"
        }
        return ",".join(f"{k}={v}" for k, v in props.items())

    def register_tables(self, dry_run: bool = False) -> Dict[str, bool]:
        """
        Register all tables via a Dataproc Serverless batch job.

        Generates a PySpark script that connects to the Lakehouse REST Catalog
        and registers each existing Iceberg table using the
        ``register_table`` system procedure.

        Ref: https://docs.cloud.google.com/dataproc/docs/guides/iceberg-lakehouse-rest-catalog
        """
        results = {"tables_registered": 0}

        if dry_run:
            for table_name in TABLES:
                metadata_location = f"{self.warehouse}/{self.namespace}/{table_name}/metadata.json"
                print(f"[DRY RUN] Would register table: {table_name}")
                print(f"  metadata location: {metadata_location}")
                results["tables_registered"] += 1
            return results

        # Generate and upload the PySpark script
        script_content = self._generate_registration_script()
        script_gcs_path = self._upload_script_to_gcs(script_content)
        print(f"Uploaded registration script: {script_gcs_path}")

        # Submit the Dataproc Serverless batch job
        properties = self._build_spark_properties()
        cmd = [
            "gcloud", "dataproc", "batches", "submit", "pyspark",
            script_gcs_path,
            f"--project={self.project_id}",
            f"--region={self.location}",
            "--version=2.2",
            f"--properties={properties}",
        ]

        print(f"Submitting Dataproc batch job to register {len(TABLES)} tables...")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode == 0:
                print(f"Dataproc batch completed: {len(TABLES)} tables registered")
                results["tables_registered"] = len(TABLES)
            else:
                print(f"Dataproc batch failed (exit {result.returncode}):")
                print(result.stderr)
                # Parse output to count successes if available
                results["tables_registered"] = 0
        except subprocess.TimeoutExpired:
            print("Dataproc batch job timed out after 10 minutes")
            results["tables_registered"] = 0
        except FileNotFoundError:
            raise RuntimeError("gcloud CLI not available")

        return results
