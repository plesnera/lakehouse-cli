# BigLake Iceberg REST Catalog Implementation Attempts

This document tracks the approaches attempted to implement table registration for the Google Cloud BigLake Iceberg REST Catalog and the issues encountered.

## Summary

When using **vended-credentials** mode (the enterprise/recommended default), the gcloud CLI **cannot reliably create catalogs or register tables** because it does not properly send the `X-Iceberg-Access-Delegation: vended-credentials` header that BigLake requires.

| Operation | gcloud + vended-credentials | Workaround |
|-----------|----------------------------|------------|
| Create catalog | ❌ Does not work | **GCP Console** → BigLake > Iceberg catalogs > Create catalog |
| Register tables | ❌ Does not work | **Spark/Dataproc** (e.g. this project's CLI) |

The BigLake Iceberg REST Catalog API is also **non-standard** - it uses `iceberg/v1/restcatalog/v1/{resource}` paths and has undocumented payload formats that differ from the Apache Iceberg specification.

---

## Approach 1: gcloud CLI `biglake iceberg catalogs create`

**Purpose:** Create the catalog

**Command:**
```bash
gcloud biglake iceberg catalogs create <name> \
  --project=<project> \
  --catalog-type=gcs-bucket \
  --credential-mode=vended-credentials
```

**Status:** ✅ Works

**Issues Found:**
- `--location` flag is NOT supported (error: "unrecognized arguments: --location")
- Must use: `gcloud biglake iceberg catalogs create` without location

---

## Approach 2: REST API via `https://biglake.googleapis.com/v1/...`

**Purpose:** Namespace and table operations via REST

**Endpoints Tested:**
- `POST /v1/projects/{project}/locations/{location}/catalogs/{catalog}/namespaces`
- `GET /v1/projects/{project}/locations/{location}/catalogs/{catalog}/namespaces/{ns}`
- `POST /v1/projects/{project}/locations/{location}/catalogs/{catalog}/namespaces/{ns}/tables/{table}/register`

**Status:** ❌ Fails

**Error:** 403/404 across all endpoints
```
{
  "error": {
    "code": 403,
    "message": "Permission 'biglake.catalogs.get' denied...",
    "status": "PERMISSION_DENIED"
  }
}
```

**Root Cause:** User credentials don't have `biglake.*` IAM permissions required for REST access, even though gcloud commands work (gcloud uses a different service account internally).

---

## Approach 3: REST API via `https://biglake.googleapis.com/iceberg/v1/restcatalog/v1/...`

**Purpose:** Namespace and table operations via the BigLake-specific Iceberg endpoint

**Discovery Method:** Used `gcloud --log-http` to see actual API calls made by working gcloud commands.

**Endpoints Tested:**
- `GET /iceberg/v1/restcatalog/v1/projects/{project}/catalogs/{catalog}/namespaces` - List namespaces
- `GET /iceberg/v1/restcatalog/v1/projects/{project}/catalogs/{catalog}/namespaces/{ns}` - Get namespace
- `POST /iceberg/v1/restcatalog/v1/projects/{project}/catalogs/{catalog}/namespaces/{ns}/tables/{table}` - Create table
- `POST /iceberg/v1/restcatalog/v1/projects/{project}/catalogs/{catalog}/namespaces/{ns}/tables/{table}/register` - Register table

**Status:** ⚠️ Partial success

**Results:**
| Operation | Endpoint | Status | Notes |
|-----------|----------|--------|-------|
| List namespaces | GET .../namespaces | ✅ 200 | Works |
| Get namespace | GET .../namespaces/{ns} | ✅ 200 | Works |
| Create table | POST .../tables/{table} | ❌ 400 | Invalid argument |
| Register table | POST .../tables/{table}/register | ❌ 400 | Unknown field "metadataLocation" |

**Root Cause:** BigLake Iceberg REST API has non-standard paths and undocumented payload formats that don't match the Apache Iceberg spec.

---

## Approach 4: gcloud `biglake iceberg tables register` Command

**Purpose:** Register existing Iceberg tables

**Command:**
```bash
gcloud biglake iceberg tables register <table> \
  --namespace=<namespace> \
  --catalog=<catalog> \
  --project=<project> \
  --metadata-location=gs://bucket/path/metadata.json
```

**Status:** ❌ Fails with vended-credentials

**Error:**
```
ERROR: (gcloud.biglake.iceberg.tables.register) INVALID_ARGUMENT:
X-Iceberg-Access-Delegation header must be present and contain
`vended-credentials` when credential mode is `CREDENTIAL_MODE_VENDED_CREDENTIALS`.
```

**Root Cause:** gcloud SDK doesn't properly send the `X-Iceberg-Access-Delegation: vended-credentials` header when using `vended-credentials` credential mode.

**Log Output (via `--log-http`):**
```
uri: https://biglake.googleapis.com/iceberg/v1/restcatalog/v1/projects/.../namespaces/marketing/register?alt=json
method: POST
```

---

## Approach 5: Python SDK `google-cloud-biglake`

**Package:** `google-cloud-biglake==0.3.0`

**Available Methods:**
- `create_iceberg_catalog`
- `get_iceberg_catalog`
- `list_iceberg_catalogs`
- `update_iceberg_catalog`
- `failover_iceberg_catalog`

**Status:** ❌ Insufficient

**Issue:** SDK only exposes catalog-level operations. No methods for:
- `create_iceberg_namespace`
- `register_iceberg_table`
- `list_iceberg_tables`

---

## Working Implementation

### What Works

| Operation | Method | Command/API |
|-----------|--------|-------------|
| Create catalog | gcloud | ✅ Works |
| Verify catalog exists | gcloud | ✅ Works |
| Create namespace | gcloud | ✅ Works |
| Verify namespace exists | REST | ✅ Works |
| List tables | gcloud | ✅ Works |

### What Doesn't Work (vended-credentials)

| Operation | Method | Issue |
|-----------|--------|-------|
| Register table | gcloud | Missing header |
| Register table | REST | Wrong payload format |

---

## Recommended Workaround

For **vended-credentials** mode, register tables via:

### 1. GCP Console
Navigate to: BigLake → Catalog → Namespace → Create Table
- Requires manually specifying metadata location

### 2. Spark/Dataproc
```python
spark.sql(f"""
    CREATE TABLE {catalog}.{namespace}.{table}
    USING iceberg
    LOCATION 'gs://bucket/iceberg/{namespace}/{table}'
""")
```

### 3. Use end-user credentials instead
```bash
gcloud biglake iceberg catalogs create <name> \
  --project=<project> \
  --catalog-type=gcs-bucket \
  --credential-mode=end-user
```

With `end-user` mode, the gcloud `tables register` command works correctly.

---

## Key Findings

1. **API Path Format:** BigLake Iceberg uses `iceberg/v1/restcatalog/v1/{resource}` not standard `v1/{resource}`

2. **Authentication Gap:** User credentials work for gcloud but not REST API due to IAM permission differences

3. **Header Requirement:** `X-Iceberg-Access-Delegation: vended-credentials` is required but gcloud doesn't forward it properly

4. **Undocumented API:** The BigLake Iceberg REST API payload formats are not publicly documented and differ from Apache Iceberg spec

5. **SDK Limitations:** The Python SDK `google-cloud-biglake` is incomplete - only exposes catalog-level operations

---

## Resources

- [BigLake Iceberg REST Catalog Documentation](https://docs.cloud.google.com/biglake/docs/blms-rest-catalog)
- [Apache Iceberg REST Catalog Spec](https://iceberg.apache.org/spec/)
- [BigLake API Reference](https://cloud.google.com/bigquery/docs/reference/biglake/rest)
