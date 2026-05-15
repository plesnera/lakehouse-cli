from pydantic import BaseModel, Field
from typing import List
import subprocess
import os


class Config(BaseModel):
    @staticmethod
    def get_current_gcloud_project() -> str:
        """Get the current gcloud project or return None if not available."""
        try:
            # Try gcloud command first
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass

        # Fallback to environment variable
        return os.environ.get("GOOGLE_CLOUD_PROJECT", "wpp-dataproducts-lakehouse")

    # Project configuration - supports cross-project scenarios
    data_project_id: str = Field(
        default_factory=lambda: Config.get_current_gcloud_project(),
        description="GCP project where data is stored (GCS, Iceberg)"
    )
    catalog_project_id: str = Field(
        default_factory=lambda: Config.get_current_gcloud_project(),
        description="GCP project where Dataplex catalog resides"
    )

    # Storage configuration
    iceberg_warehouse: str = Field(
        default_factory=lambda: f"gs://{Config.get_current_gcloud_project()}-warehouse/iceberg",
        description="GCS path for Iceberg data (can be different project)"
    )
    iceberg_namespace: str = "marketing"

    # Connection configuration - template with project placeholder
    biglake_connection: str = Field(
        default="projects/{project_id}/locations/{location}/connections/biglake-conn",
        description="BigLake connection template with {project_id} placeholder"
    )

    # Lakehouse REST Catalog configuration
    lakehouse_catalog_name: str = Field(
        default="",
        description="Lakehouse REST catalog name (REQUIRED - no default, must be explicit)"
    )

    # Location configuration
    location: str = "us-east1"

    # Network configuration for Dataproc
    subnet_name: str = Field(
        default="dataproc-subnet",
        description="VPC subnet for Dataproc Serverless jobs"
    )

    # Backward compatibility property
    @property
    def project_id(self) -> str:
        """Maintain backward compatibility - defaults to catalog_project_id"""
        return self.catalog_project_id

    # Resource path helpers
    @property
    def resource_parent(self) -> str:
        """Returns projects/{project_id}/locations/{location}"""
        return f"projects/{self.project_id}/locations/{self.location}"

    @property
    def catalog_resource_parent(self) -> str:
        """Returns projects/{catalog_project_id}/locations/{location}"""
        return f"projects/{self.catalog_project_id}/locations/{self.location}"

    @property
    def entry_group_path(self) -> str:
        """Returns the full entry group resource path"""
        return f"{self.catalog_resource_parent}/entryGroups/marketing-lakehouse"

    def get_bq_resource_path(self, table: str) -> str:
        """Returns the BigQuery resource path for a table"""
        return f"//bigquery.googleapis.com/projects/{self.project_id}/datasets/{self.iceberg_namespace}/tables/{table}"


# Table list - single source of truth for all tables in the lakehouse
TABLES = ["audience", "cookie_registry", "campaigns", "creatives", "pixel_events", "transactions"]
