"""
Dataset-Level Insights via Dataplex DATA_DOCUMENTATION Scans

This module provides AI-generated insights for an entire BigQuery dataset, including:
- AI-generated dataset description
- Relationship graph (how tables connect)
- Cross-table SQL sample queries
- Discovered primary/foreign key relationships

Uses the same Dataplex DataScan API as table-level insights but targets
an entire dataset rather than a single table.
"""

import time
from typing import Optional

import requests
import google.auth
from google.auth.transport.requests import Request
from google.cloud import bigquery

from ingestion.config import Config


class DatasetInsightsManager:
    """
    Manages dataset-level Dataplex DATA_DOCUMENTATION scans for AI-generated insights.

    Unlike table-level insights which target individual tables, dataset-level insights
    analyze an entire dataset to produce:
    - AI-generated dataset description
    - Relationship graph (how tables connect)
    - Cross-table SQL sample queries
    - Discovered primary/foreign key relationships
    """

    def __init__(self, config: Config):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset_id = f"{config.project_id}.{config.iceberg_namespace}"

    def create_scan(self, dry_run: bool = False, timeout: int = 600) -> Optional[str]:
        """
        Create a dataset-level DATA_DOCUMENTATION scan.

        Args:
            dry_run: If True, print scan details without creating the resource

        Returns:
            Scan ID if created successfully, None otherwise
        """
        try:
            project_id = self.config.project_id
            dataset_name = self.config.iceberg_namespace

            # Get dataset location
            dataset_ref = bigquery.DatasetReference(project=project_id, dataset_id=dataset_name)
            dataset_obj = self.client.get_dataset(dataset_ref)
            location = dataset_obj.location

            # Fixed scan ID for dataset-level insights (reusable, not timestamped)
            scan_id = f"dataset-insights-{dataset_name}"

            payload = {
                "data": {
                    "resource": f"//bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_name}"
                },
                "type": "DATA_DOCUMENTATION",
                "dataDocumentationSpec": {
                    "catalogPublishingEnabled": True
                },
                "executionSpec": {
                    "trigger": {
                        "onDemand": {}
                    }
                }
            }

            if dry_run:
                print("👁️  Dry-run: would create dataset-level DataScan:")
                print(f"   Scan ID: {scan_id}")
                print(f"   Resource: //bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_name}")
                print(f"   Location: {location}")
                print(f"   Type: DATA_DOCUMENTATION")
                return scan_id

            credentials, _ = google.auth.default()
            auth_req = Request()
            credentials.refresh(auth_req)
            access_token = credentials.token

            url = (
                f"https://dataplex.googleapis.com/v1/projects/{project_id}"
                f"/locations/{location}/dataScans?dataScanId={scan_id}"
            )
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            print(f"📡 Creating dataset-level DataScan: {scan_id}")
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 409:
                print(f"ℹ️  DataScan already exists: {scan_id} (reusing)")
                return scan_id

            if response.status_code != 200:
                err = response.json().get('error', {}).get('message', response.text)
                print(f"❌ DataScan creation failed ({response.status_code}): {err}")
                return None

            # Poll the long-running operation until it completes
            operation = response.json()
            op_name = operation.get('name', '')
            if op_name and not operation.get('done', False):
                print(f"⏳ Waiting for DataScan creation operation to complete...")
                op_url = f"https://dataplex.googleapis.com/v1/{op_name}"
                start_op_time = time.time()
                while time.time() - start_op_time < timeout:
                    time.sleep(5)
                    op_resp = requests.get(op_url, headers=headers)
                    if op_resp.status_code == 200:
                        op_data = op_resp.json()
                        if op_data.get('done', False):
                            if 'error' in op_data:
                                err = op_data['error'].get('message', 'Unknown error')
                                print(f"❌ DataScan creation operation failed: {err}")
                                return None
                            break
                    else:
                        break

            datascan_name = f"projects/{project_id}/locations/{location}/dataScans/{scan_id}"
            print(f"✅ Dataset-level DataScan created: {datascan_name}")
            return scan_id

        except Exception as e:
            print(f"⚠️  Failed to create dataset insights scan: {e}")
            return None

    def run_scan(self) -> bool:
        """
        Trigger execution of the dataset-level scan.

        Returns:
            True if scan was triggered successfully
        """
        try:
            project_id = self.config.project_id
            dataset_name = self.config.iceberg_namespace

            # Get dataset location
            dataset_ref = bigquery.DatasetReference(project=project_id, dataset_id=dataset_name)
            dataset_obj = self.client.get_dataset(dataset_ref)
            location = dataset_obj.location

            scan_id = f"dataset-insights-{dataset_name}"

            credentials, _ = google.auth.default()
            auth_req = Request()
            credentials.refresh(auth_req)
            access_token = credentials.token

            url = (
                f"https://dataplex.googleapis.com/v1/projects/{project_id}"
                f"/locations/{location}/dataScans/{scan_id}:run"
            )
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            print(f"📡 Triggering dataset insights scan execution: {scan_id}")
            response = requests.post(url, headers=headers, json={})

            if response.status_code != 200:
                err = response.json().get('error', {}).get('message', response.text)
                print(f"❌ Scan run trigger failed ({response.status_code}): {err}")
                return False

            print(f"✅ Scan execution triggered successfully")
            return True

        except Exception as e:
            print(f"⚠️  Failed to trigger scan: {e}")
            return False

    def get_results(self, timeout: int = 600) -> dict:
        """
        Poll for and return dataset insights results.

        Args:
            timeout: Maximum seconds to wait for results

        Returns:
            Dictionary containing insights results or error status
        """
        try:
            project_id = self.config.project_id
            dataset_name = self.config.iceberg_namespace

            # Get dataset location
            dataset_ref = bigquery.DatasetReference(project=project_id, dataset_id=dataset_name)
            dataset_obj = self.client.get_dataset(dataset_ref)
            location = dataset_obj.location

            scan_id = f"dataset-insights-{dataset_name}"

            credentials, _ = google.auth.default()
            auth_req = Request()
            credentials.refresh(auth_req)
            access_token = credentials.token

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            # Poll for results
            start_time = time.time()
            poll_interval = 10

            print(f"📊 Waiting for dataset insights results (timeout: {timeout}s)...")

            while time.time() - start_time < timeout:
                # Fetch the latest job from the /jobs endpoint
                jobs_url = (
                    f"https://dataplex.googleapis.com/v1/projects/{project_id}"
                    f"/locations/{location}/dataScans/{scan_id}/jobs"
                )
                response = requests.get(jobs_url, headers=headers)

                if response.status_code != 200:
                    err = response.json().get('error', {}).get('message', response.text)
                    print(f"❌ Failed to get scan jobs ({response.status_code}): {err}")
                    return {"status": "error", "message": err}

                jobs = response.json().get('dataScans', response.json().get('dataScanJobs', []))
                if not jobs:
                    elapsed = int(time.time() - start_time)
                    print(f"   No jobs found yet ({elapsed}s elapsed, {timeout - elapsed}s remaining)")
                    time.sleep(poll_interval)
                    continue

                latest_job = jobs[0]
                state = latest_job.get('state', 'UNKNOWN')

                if state in ('SUCCEEDED', 'DONE'):
                    # Fetch full results using ?view=FULL on the job URL
                    job_name = latest_job.get('name', '')
                    result_url = f"https://dataplex.googleapis.com/v1/{job_name}?view=FULL"
                    result_response = requests.get(result_url, headers=headers)

                    if result_response.status_code != 200:
                        err = result_response.json().get('error', {}).get('message', result_response.text)
                        print(f"❌ Failed to get scan results ({result_response.status_code}): {err}")
                        return {"status": "error", "message": err}

                    result_data = result_response.json()
                    data_doc_result = result_data.get('dataDocumentationResult', {})
                    dataset_result = data_doc_result.get('datasetResult', {})

                    print(f"✅ Dataset insights completed successfully")

                    return {
                        "status": "success",
                        "description": dataset_result.get('overview', ''),
                        "relationship_graph": dataset_result.get('schemaRelationships', []),
                        "sample_queries": dataset_result.get('queries', []),
                        "primary_keys": dataset_result.get('discoveredPrimaryKeys', []),
                        "foreign_keys": dataset_result.get('discoveredForeignKeys', [])
                    }

                elif state == 'FAILED':
                    return {"status": "failed", "message": "Scan failed"}

                else:
                    elapsed = int(time.time() - start_time)
                    print(f"   Scan state: {state} ({elapsed}s elapsed, {timeout - elapsed}s remaining)")
                    time.sleep(poll_interval)

            return {"status": "timeout", "message": f"Results not available after {timeout}s"}

        except Exception as e:
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    config = Config()
    mgr = DatasetInsightsManager(config)
    mgr.create_scan()