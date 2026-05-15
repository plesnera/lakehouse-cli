"""BigQuery ML — Remote Gemini model setup and demonstration.

Creates a remote model connected to Gemini via BigQuery ML, then demonstrates
AI.GENERATE_TEXT and AI.GENERATE_EMBEDDING on marketing data.

Ref: https://cloud.google.com/bigquery/docs/generate-text-tutorial
"""

from google.cloud import bigquery

from ingestion.config import Config


class BQMLGeminiManager:
    """Sets up BigQuery ML remote models for Gemini text generation and embedding."""

    def __init__(self, config: Config):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset = f"{config.project_id}.{config.iceberg_namespace}"
        self.connection = f"{config.project_id}.{config.location}.biglake-conn"

    def setup(self, dry_run: bool = False) -> None:
        """Create Gemini remote models and run example queries."""
        steps = [
            ("1/4 Create Gemini text generation model", self._sql_create_gemini_model()),
            ("2/4 Summarise campaign performance", self._sql_summarise_campaigns()),
            ("3/4 Classify creative themes", self._sql_classify_creatives()),
            ("4/4 Generate creative recommendations", self._sql_generate_recommendations()),
        ]

        for label, sql in steps:
            print(f"\n--- {label} ---")
            if dry_run:
                print(sql)
            else:
                try:
                    job = self.client.query(sql)
                    results = job.result()
                    print(f"  ✅ {label} complete")
                    # Print first few rows for demo queries
                    if "Summarise" in label or "Classify" in label or "recommendations" in label:
                        for row in results:
                            for key, val in row.items():
                                text = str(val)[:200] if val else ""
                                print(f"    {key}: {text}")
                            break  # Only first row for demo
                except Exception as e:
                    print(f"  ⚠️  {label} failed: {e}")

        print("\nBQML Gemini setup complete.")

    # ------------------------------------------------------------------
    # SQL builders
    # ------------------------------------------------------------------

    def _sql_create_gemini_model(self) -> str:
        return f"""
CREATE OR REPLACE MODEL `{self.dataset}.gemini_model`
  REMOTE WITH CONNECTION `{self.connection}`
  OPTIONS (ENDPOINT = 'gemini-2.0-flash');
""".strip()

    def _sql_summarise_campaigns(self) -> str:
        return f"""
SELECT *
FROM AI.GENERATE_TEXT(
  MODEL `{self.dataset}.gemini_model`,
  (
    SELECT CONCAT(
      'Summarise this campaign performance data in 3 bullet points: ',
      'Campaign: ', campaign_name,
      ', Brand: ', brand,
      ', Market: ', country_code,
      ', Objective: ', objective,
      ', Budget: $', CAST(ROUND(budget_usd) AS STRING),
      ', Spend: $', CAST(ROUND(actual_spend_usd) AS STRING),
      ', Status: ', status
    ) AS prompt
    FROM `{self.dataset}.campaigns`
    WHERE status = 'completed'
    LIMIT 3
  ),
  STRUCT(256 AS max_output_tokens, 0.2 AS temperature, TRUE AS flatten_json_output)
);
""".strip()

    def _sql_classify_creatives(self) -> str:
        return f"""
SELECT *
FROM AI.GENERATE_TEXT(
  MODEL `{self.dataset}.gemini_model`,
  (
    SELECT CONCAT(
      'Classify this creative asset into one of: Premium, Standard, Budget. ',
      'Return just the classification. ',
      'Creative: ', creative_name,
      ', Format: ', format,
      ', Channel: ', channel,
      ', Brand: ', brand
    ) AS prompt
    FROM `{self.dataset}.creatives`
    LIMIT 5
  ),
  STRUCT(32 AS max_output_tokens, 0.0 AS temperature, TRUE AS flatten_json_output)
);
""".strip()

    def _sql_generate_recommendations(self) -> str:
        return f"""
SELECT *
FROM AI.GENERATE_TEXT(
  MODEL `{self.dataset}.gemini_model`,
  (
    SELECT CONCAT(
      'Based on the following audience segment, recommend 3 ad creative themes ',
      'and explain why. Segment: ', segment_name,
      ', Demographics: ', age_band, ' ', gender,
      ', Income: ', income_band,
      ', Country: ', country_code
    ) AS prompt
    FROM `{self.dataset}.audience`
    LIMIT 3
  ),
  STRUCT(512 AS max_output_tokens, 0.4 AS temperature, TRUE AS flatten_json_output)
);
""".strip()
