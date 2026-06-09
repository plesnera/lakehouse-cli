#!/usr/bin/env python3
"""
Lakehouse REST Catalog (Iceberg) Manager

Manages Google Cloud Lakehouse REST Catalog for Iceberg metadata, providing
a single source of truth for BigQuery, Spark, and Trino table discovery.

Uses gcloud CLI for catalog/namespace operations.
"""

import subprocess
from typing import Dict

from lake_cli.config import Config


class LakehouseCatalogManager:
    """
    Manages Google Cloud Lakehouse REST Catalog operations for Iceberg tables.

    Uses gcloud CLI for catalog/namespace operations.
    Table registration is handled by Dataplex catalog entries
    (CatalogManager.register_entries).
    """

    def __init__(self, config: Config):
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
