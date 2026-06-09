"""BigQuery Continuous Queries — example real-time processing on pixel_events.

Provides SQL statements for continuous queries that react to new rows in
pixel_events. These require an Enterprise reservation with CONTINUOUS job type.

Ref: https://cloud.google.com/bigquery/docs/continuous-queries
"""

from google.cloud import bigquery

from lake_cli.config import Config


class ContinuousQueryManager:
    """Generates and optionally executes continuous query SQL for the marketing lakehouse."""

    def __init__(self, config: Config):
        self.config = config
        self.client = bigquery.Client(project=config.project_id)
        self.dataset = f"{config.project_id}.{config.iceberg_namespace}"

    def setup(self, dry_run: bool = True) -> None:
        """Print (or execute) the continuous query SQL.

        Defaults to dry_run=True because continuous queries require an
        Enterprise reservation with a CONTINUOUS assignment and incur
        ongoing slot charges.
        """
        queries = [
            ("Create destination table for real-time CTR", self._sql_create_destination()),
            ("Continuous CTR aggregation query", self._sql_continuous_ctr()),
        ]

        for label, sql in queries:
            print(f"\n--- {label} ---")
            if dry_run:
                print(sql)
                print("\n  ℹ️  Run with --no-dry-run to execute (requires Enterprise reservation)")
            else:
                try:
                    job = self.client.query(sql)
                    job.result()
                    print(f"  ✅ {label} executed")
                except Exception as e:
                    print(f"  ⚠️  {label} failed: {e}")

        print("\nContinuous queries setup complete.")

    # ------------------------------------------------------------------
    # SQL builders
    # ------------------------------------------------------------------

    def _sql_create_destination(self) -> str:
        """Create the destination table for the continuous CTR query."""
        return f"""
CREATE TABLE IF NOT EXISTS `{self.dataset}.realtime_campaign_ctr` (
  campaign_id STRING,
  channel STRING,
  country_code STRING,
  impressions INT64,
  clicks INT64,
  ctr FLOAT64,
  window_start TIMESTAMP,
  window_end TIMESTAMP
);
""".strip()

    def _sql_continuous_ctr(self) -> str:
        """Continuous query that computes per-campaign CTR from new pixel_events.

        Uses the APPENDS TVF to process only new rows added to pixel_events.
        Writes aggregated results into realtime_campaign_ctr.

        NOTE: This query must be run with --continuous flag or via the
        BigQuery console continuous query toggle. It requires an Enterprise
        edition reservation with a CONTINUOUS job type assignment.
        """
        return f"""
-- Run this as a continuous query (BigQuery console > More > Continuous query)
-- Or via: bq query --continuous --use_legacy_sql=false '<SQL>'
INSERT INTO `{self.dataset}.realtime_campaign_ctr`
  (campaign_id, channel, country_code, impressions, clicks, ctr, window_start, window_end)
SELECT
  campaign_id,
  channel,
  country_code,
  COUNTIF(event_type = 'impression') AS impressions,
  COUNTIF(event_type = 'click') AS clicks,
  SAFE_DIVIDE(
    COUNTIF(event_type = 'click'),
    COUNTIF(event_type = 'impression')
  ) AS ctr,
  MIN(event_ts) AS window_start,
  MAX(event_ts) AS window_end
FROM APPENDS(
  TABLE `{self.dataset}.pixel_events`,
  CURRENT_TIMESTAMP() - INTERVAL 10 MINUTE
)
GROUP BY campaign_id, channel, country_code;
""".strip()
