"""BigQuery Vector Search — embedding generation and semantic similarity search.

Sets up a remote text-embedding model, generates embeddings on marketing data
text columns, and demonstrates VECTOR_SEARCH queries.

Ref: https://cloud.google.com/bigquery/docs/vector-search-intro
"""

from google.cloud import bigquery

from generators.config import GeneratorConfig

# SQL templates use the BigLake connection already configured in GeneratorConfig.
_DATASET = "{project}.{namespace}"
_CONNECTION = "{project}.{location}.biglake-conn"


class VectorSearchManager:
    """Manages BigQuery Vector Search setup for the marketing lakehouse."""

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset = f"{config.project_id}.{config.iceberg_namespace}"
        self.connection = f"{config.project_id}.{config.location}.biglake-conn"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup(self, dry_run: bool = False) -> None:
        """Create the embedding model, generate embeddings, and create a vector index."""
        steps = [
            ("1/4 Create embedding remote model", self._sql_create_model()),
            ("2/4 Generate audience segment embeddings", self._sql_generate_embeddings()),
            ("3/4 Create vector index on embeddings", self._sql_create_index()),
            ("4/4 Example VECTOR_SEARCH query", self._sql_example_search()),
        ]

        for label, sql in steps:
            print(f"\n--- {label} ---")
            if dry_run:
                print(sql)
            else:
                try:
                    job = self.client.query(sql)
                    job.result()
                    print(f"  ✅ {label} complete")
                except Exception as e:
                    print(f"  ⚠️  {label} failed: {e}")

        print("\nVector search setup complete.")

    # ------------------------------------------------------------------
    # SQL builders
    # ------------------------------------------------------------------

    def _sql_create_model(self) -> str:
        return f"""
CREATE OR REPLACE MODEL `{self.dataset}.embedding_model`
  REMOTE WITH CONNECTION `{self.connection}`
  OPTIONS (ENDPOINT = 'text-embedding-005');
""".strip()

    def _sql_generate_embeddings(self) -> str:
        return f"""
CREATE OR REPLACE TABLE `{self.dataset}.audience_embeddings` AS
SELECT * FROM AI.GENERATE_EMBEDDING(
  MODEL `{self.dataset}.embedding_model`,
  (
    SELECT
      audience_id,
      segment_name,
      CONCAT(
        'Segment: ', segment_name,
        '. Age: ', age_band,
        '. Gender: ', gender,
        '. Income: ', income_band,
        '. Country: ', country_code
      ) AS content
    FROM `{self.dataset}.audience`
  )
)
WHERE LENGTH(status) = 0;
""".strip()

    def _sql_create_index(self) -> str:
        return f"""
CREATE OR REPLACE VECTOR INDEX audience_embedding_index
  ON `{self.dataset}.audience_embeddings`(embedding)
  OPTIONS(index_type = 'IVF', distance_type = 'COSINE');
""".strip()

    def _sql_example_search(self) -> str:
        return f"""
-- Find audience segments similar to 'eco-conscious millennials'
SELECT
  query.content AS query_text,
  base.audience_id,
  base.segment_name,
  distance
FROM VECTOR_SEARCH(
  TABLE `{self.dataset}.audience_embeddings`,
  'embedding',
  (
    SELECT * FROM AI.GENERATE_EMBEDDING(
      MODEL `{self.dataset}.embedding_model`,
      (SELECT 'eco-conscious millennials interested in sustainable brands' AS content)
    )
  ),
  top_k => 10,
  distance_type => 'COSINE'
)
ORDER BY distance
LIMIT 10;
""".strip()
