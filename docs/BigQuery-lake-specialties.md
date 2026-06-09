# BigQuery Lake Specialties

This document collects BigQuery-specific topics that are tightly coupled to
the marketing lakehouse but are not part of the CLI command surface. It
combines three previously separate references:

- BigQuery Graph (SQL/PGQ) — modeling the marketing dataset as a property
  graph, including the full DDL for the production 6-node / 8-edge graph.
- BigQuery Data Engineering Agent — using the metadata pipeline in this
  repository to give the agent better context for SQL generation.

The CLI itself is documented in `lake-cli-details.md`; the BigLake Iceberg
catalog operational constraints are documented in
`iceberg_rest_implementations.md`.

## Prerequisites (apply to all sections)

The Data Engineering Agent and the property graph both depend on the same
underlying state:

1. The target BigQuery dataset (default: `marketing`) already contains the
   six expected tables:
   - `audience`
   - `cookie_registry`
   - `campaigns`
   - `creatives`
   - `pixel_events`
   - `transactions`
2. A Lakehouse REST catalog already exists.
3. You have permission to run Dataplex and BigQuery metadata operations.

Run the following preparation steps before either workflow:

```bash
# 1) Verify catalog + namespace
uv run lake setup-catalog \
  --catalog-name YOUR_CATALOG_NAME \
  --full

# 2) Register Dataplex assets, entries, tags, and glossary
uv run lake catalog \
  --catalog-name YOUR_CATALOG_NAME

# 3) Apply table/column descriptions
uv run lake enrich-metadata

# 4) Ensure glossary links are applied
uv run lake manage-glossary --action apply
```

## Part 1 — BigQuery Graph (SQL/PGQ)

BigQuery Graph is a SQL extension for property-graph queries (sometimes
called SQL/PGQ, the SQL Standard's graph query language). It lets you
model entities and relationships as a logical layer over existing tables
and query them with `MATCH` patterns instead of hand-written multi-hop
joins.

### Key concepts

- A property graph is a **logical layer over existing tables** — you do
  not load or copy data; the graph reuses the underlying BigQuery tables.
- You define entities as **node tables** and relationships as **edge
  tables** in a `CREATE PROPERTY GRAPH` statement.
- Querying uses graph patterns (`MATCH ... RETURN ...`) instead of
  manually writing repeated multi-hop joins.
- Edge tables are typically one of the participating node tables with a
  foreign-key column pointing at the other side; the graph definition
  declares the `SOURCE KEY` / `DESTINATION KEY` mapping.

### Why use graph modeling here

Graph modeling simplifies path-style analysis across entities such as:

- `campaign → creative → pixel event`
- `audience → cookie registry → transactions`
- `cookie registry ↔ transactions` (multiple join paths, different fill
  rates — see the full DDL below)

These traversals are easier to read and maintain as `MATCH` patterns
than as nested joins with explicit join conditions and column aliases.

### Conceptual example: campaigns and creatives

The smallest meaningful graph in the marketing dataset is the
campaign-to-creative relationship.

```sql
CREATE OR REPLACE PROPERTY GRAPH `project.marketing.marketing_graph`
NODE TABLES (
  `project.marketing.campaigns` AS `campaigns`
    KEY (`campaign_id`)
    LABEL `campaign`
    PROPERTIES (campaign_id, campaign_name, brand, objective),

  `project.marketing.creatives` AS `creatives`
    KEY (`creative_id`)
    LABEL `creative`
    PROPERTIES (creative_id, creative_name, format, campaign_id)
)
EDGE TABLES (
  `project.marketing.creatives` AS `belongs_to`
    KEY (`creative_id`)
    SOURCE KEY (`creative_id`) REFERENCES `creatives`
    DESTINATION KEY (`campaign_id`) REFERENCES `campaigns`
    LABEL `belongs_to`
    PROPERTIES (campaign_id)
);
```

A `MATCH` query against this graph:

```sql
GRAPH `project.marketing.marketing_graph`
MATCH (c:campaign)<-[r:belongs_to]-(cr:creative)
RETURN c.campaign_name, cr.creative_name;
```

### Production graph DDL for the marketing dataset

The conceptual example above is intentionally tiny. The full production
graph covers all six tables and eight relationships (six one-to-many
foreign keys, plus two alternative identity-resolution paths to
transactions). Run this DDL once in BigQuery to create the graph.

```sql
CREATE OR REPLACE PROPERTY GRAPH `wpp-dataproducts-lakehouse.marketing.marketing-lake-graph`
  NODE TABLES (
    `wpp-dataproducts-lakehouse.marketing.audience` AS `audience`
      KEY (`audience_id`)
        LABEL `audience` PROPERTIES (audience_id AS `audience_id`, segment_name AS `segment_name`, country_code AS `country_code`, region AS `region`, age_band AS `age_band`, gender AS `gender`, income_band AS `income_band`, interests AS `interests`, brand_affinity_scores AS `brand_affinity_scores`, channel_index AS `channel_index`, hem AS `hem`, lat AS `lat`, lon AS `lon`, location_lat AS `location_lat`, location_lon AS `location_lon`, panel_weight AS `panel_weight`, created_at AS `created_at`, _FILE_NAME AS `_FILE_NAME`),

    `wpp-dataproducts-lakehouse.marketing.campaigns` AS `campaigns`
      KEY (`campaign_id`)
        LABEL `campaigns` PROPERTIES (campaign_id AS `campaign_id`, campaign_name AS `campaign_name`, brand AS `brand`, advertiser AS `advertiser`, product_category AS `product_category`, country_code AS `country_code`, regions AS `regions`, channels AS `channels`, objective AS `objective`, budget_usd AS `budget_usd`, actual_spend_usd AS `actual_spend_usd`, start_date AS `start_date`, end_date AS `end_date`, status AS `status`, created_at AS `created_at`, _FILE_NAME AS `_FILE_NAME`),

    `wpp-dataproducts-lakehouse.marketing.cookie_registry` AS `cookie_registry`
      KEY (`cookie_id`)
        LABEL `cookie_registry` PROPERTIES (cookie_id AS `cookie_id`, visitor_id AS `visitor_id`, device_id AS `device_id`, audience_id AS `audience_id`, hem AS `hem`, hashed_email AS `hashed_email`, country_code AS `country_code`, city AS `city`, lat AS `lat`, lon AS `lon`, device_type AS `device_type`, browser AS `browser`, first_seen_at AS `first_seen_at`, last_seen_at AS `last_seen_at`, _FILE_NAME AS `_FILE_NAME`),

    `wpp-dataproducts-lakehouse.marketing.creatives` AS `creatives`
      KEY (`creative_id`)
        LABEL `creatives` PROPERTIES (creative_id AS `creative_id`, campaign_id AS `campaign_id`, creative_name AS `creative_name`, format AS `format`, channel AS `channel`, duration_seconds AS `duration_seconds`, width_px AS `width_px`, height_px AS `height_px`, brand AS `brand`, theme_tags AS `theme_tags`, created_at AS `created_at`, _FILE_NAME AS `_FILE_NAME`),

    `wpp-dataproducts-lakehouse.marketing.pixel_events` AS `pixel_events`
      KEY (`event_id`)
        LABEL `pixel_events` PROPERTIES (event_id AS `event_id`, event_type AS `event_type`, cookie_id AS `cookie_id`, campaign_id AS `campaign_id`, creative_id AS `creative_id`, channel AS `channel`, placement AS `placement`, country_code AS `country_code`, region AS `region`, lat AS `lat`, lon AS `lon`, device_type AS `device_type`, spend_usd AS `spend_usd`, event_ts AS `event_ts`, event_date AS `event_date`, partition_date AS `partition_date`, _FILE_NAME AS `_FILE_NAME`),

    `wpp-dataproducts-lakehouse.marketing.transactions` AS `transactions`
      KEY (`txn_id`)
        LABEL `transactions` PROPERTIES (txn_id AS `txn_id`, pan_token AS `pan_token`, cookie_id AS `cookie_id`, hem AS `hem`, merchant_name AS `merchant_name`, merchant_category_code AS `merchant_category_code`, brand AS `brand`, amount_usd AS `amount_usd`, currency_code AS `currency_code`, country_code AS `country_code`, city AS `city`, lat AS `lat`, lon AS `lon`, channel AS `channel`, txn_ts AS `txn_ts`, event_date AS `event_date`, partition_date AS `partition_date`, _FILE_NAME AS `_FILE_NAME`)
    )
  EDGE TABLES (
    -- campaigns -> creatives (one-to-many)
    `wpp-dataproducts-lakehouse.marketing.creatives` AS `has_creative`
        KEY (`creative_id`)
        SOURCE KEY (`campaign_id`) REFERENCES `campaigns` (`campaign_id`)
        DESTINATION KEY (`creative_id`) REFERENCES `creatives` (`creative_id`)
        PROPERTIES (created_at AS `assigned_at`),

    -- campaigns -> pixel_events (one-to-many)
    `wpp-dataproducts-lakehouse.marketing.pixel_events` AS `has_campaign_event`
        KEY (`event_id`)
        SOURCE KEY (`campaign_id`) REFERENCES `campaigns` (`campaign_id`)
        DESTINATION KEY (`event_id`) REFERENCES `pixel_events` (`event_id`)
        PROPERTIES (event_date AS `event_at`, event_type AS `event_type`),

    -- creatives -> pixel_events (one-to-many)
    `wpp-dataproducts-lakehouse.marketing.pixel_events` AS `has_creative_event`
        KEY (`event_id`)
        SOURCE KEY (`creative_id`) REFERENCES `creatives` (`creative_id`)
        DESTINATION KEY (`event_id`) REFERENCES `pixel_events` (`event_id`)
        PROPERTIES (event_date AS `event_at`, event_type AS `event_type`),

    -- audience -> cookie_registry via audience_id (one-to-many, ~40% fill)
    `wpp-dataproducts-lakehouse.marketing.cookie_registry` AS `has_cookie`
        KEY (`cookie_id`)
        SOURCE KEY (`audience_id`) REFERENCES `audience` (`audience_id`)
        DESTINATION KEY (`cookie_id`) REFERENCES `cookie_registry` (`cookie_id`)
        PROPERTIES (first_seen_at AS `first_seen_at`, last_seen_at AS `last_seen_at`),

    -- cookie_registry -> pixel_events via cookie_id (one-to-many, ~82% fill)
    `wpp-dataproducts-lakehouse.marketing.pixel_events` AS `has_pixel_event`
        KEY (`event_id`)
        SOURCE KEY (`cookie_id`) REFERENCES `cookie_registry` (`cookie_id`)
        DESTINATION KEY (`event_id`) REFERENCES `pixel_events` (`event_id`)
        PROPERTIES (event_date AS `event_at`, event_type AS `event_type`),

    -- cookie_registry -> transactions via cookie_id (one-to-many, ~25% fill)
    `wpp-dataproducts-lakehouse.marketing.transactions` AS `has_transaction`
        KEY (`txn_id`)
        SOURCE KEY (`cookie_id`) REFERENCES `cookie_registry` (`cookie_id`)
        DESTINATION KEY (`txn_id`) REFERENCES `transactions` (`txn_id`)
        PROPERTIES (event_date AS `purchased_at`, amount_usd AS `amount_usd`),

    -- audience -> transactions via hem (one-to-many, ~20% fill)
    `wpp-dataproducts-lakehouse.marketing.transactions` AS `has_purchase`
        KEY (`txn_id`)
        SOURCE KEY (`hem`) REFERENCES `audience` (`hem`)
        DESTINATION KEY (`txn_id`) REFERENCES `transactions` (`txn_id`)
        PROPERTIES (event_date AS `purchased_at`, amount_usd AS `amount_usd`),

    -- cookie_registry -> transactions via hem (one-to-many, ~20% fill)
    `wpp-dataproducts-lakehouse.marketing.transactions` AS `has_purchase_identity`
        KEY (`txn_id`)
        SOURCE KEY (`hem`) REFERENCES `cookie_registry` (`hem`)
        DESTINATION KEY (`txn_id`) REFERENCES `transactions` (`txn_id`)
        PROPERTIES (event_date AS `purchased_at`, amount_usd AS `amount_usd`)
  )
;
```

#### Notes on the production DDL

- **Substitution**: replace `wpp-dataproducts-lakehouse` with your project
  ID before running. The graph name is `marketing-lake-graph`; the graph
  belongs to the `marketing` dataset.
- **Edge fill rates** are inline comments (~40% / ~82% / ~25% / ~20%).
  These reflect how often the foreign key is non-null in production
  data. They matter for the attribution queries in Part 2 — for example,
  `has_transaction` (cookie_id → transactions) covers about a quarter of
  rows, and `has_purchase` (audience.hem → transactions) covers another
  20%, with only modest overlap.
- **Identity resolution**: the two `audience → transactions` and
  `cookie_registry → transactions` edges use the `hem` (hashed-email)
  column rather than `audience_id` or `cookie_id`. This is intentional:
  `hem` is the persistent identity that survives cookie loss, while
  `cookie_id` is per-device.
- **`_FILE_NAME` properties**: included so graph queries can filter by
  source file when working with Iceberg/Parquet-backed tables.

### Visual reference

![Relationship overview](img.png)

## Part 2 — BigQuery Data Engineering Agent

The Data Engineering Agent is a BigQuery Studio feature that generates
SQL pipelines from natural-language prompts. This repository does not
create data tables itself; it manages catalog metadata, glossary terms,
and governance context so the Data Engineering Agent can reason over
existing tables more effectively.

Reference:
- <https://cloud.google.com/bigquery/docs/data-engineering-agent-pipelines>

### Why metadata matters

The agent reads BigQuery table metadata (descriptions, tags, column
descriptions, glossary links) to decide which tables to join and how.
Coverage of these signals directly affects SQL-generation quality and
reduces schema ambiguity. The CLI's preparation workflow in
`Prerequisites` above is what makes the agent's outputs reliable.

### Metadata signals the agent uses

The agent benefits from:

- Dataplex catalog entries (table descriptions and display names) — set
  up by `lake catalog`
- Applied tags from `metadata/*.yaml` — set up by `lake catalog`
- Business glossary term links from `metadata/glossary.yaml` — set up
  by `lake manage-glossary --action apply`
- Column descriptions applied by `lake enrich-metadata`

Better metadata coverage generally improves SQL generation quality and
reduces schema ambiguity.

### Example prompts

These prompts are tuned to the six-table marketing graph described in
Part 1. They assume you have already run the preparation steps in
`Prerequisites` and the agent can resolve table names and join keys from
your enriched metadata.

#### Audience discovery

```
Find US audience segments that over-index on Meta and have high income. Return segment_name, age_band, and brand_affinity_scores.
```

#### Campaign performance pipeline

```
Build a pipeline that joins campaigns and pixel_events to calculate impressions, clicks, CTR, and spend by campaign for completed campaigns.
```

This uses the `has_campaign_event` edge in the graph (campaigns →
pixel_events). Asking the agent to scope to "completed campaigns" lets
it apply the `status = 'completed' AND end_date < CURRENT_DATE()` filter
on the `campaigns` table before the join, which avoids dragging in
in-flight or planned campaigns.

#### Cross-channel attribution

```
Create a pipeline that attributes transactions to ad exposures using cookie_id first and hem as fallback within a 30-day window. Return ROAS by campaign and market.
```

This exercises both the `has_transaction` (cookie_id) and
`has_purchase` / `has_purchase_identity` (hem) edges in the graph, and
forces the agent to consider the differing fill rates (~25% vs ~20%)
when picking the join order.

#### Semantic discovery

```
Which tables contain visitor or advertiser data, and how should they be joined?
```

This prompt is a good smoke-test of your glossary coverage. A
well-applied glossary will let the agent match "visitor" to
`cookie_registry.visitor_id` and "advertiser" to `campaigns.advertiser`
without you having to spell it out.

### Tuning the agent's outputs

When the agent's generated SQL is wrong or sub-optimal, the most common
causes are:

- **Missing column descriptions.** If a column is in a table but has no
  description, the agent falls back to the column name and frequently
  misinterprets high-cardinality or hashed columns. Re-run
  `lake enrich-metadata` (manual mode, with edited YAML files) to add
  descriptions.
- **Glossary terms not linked.** If the agent picks the wrong table, it
  often means the term→table link in the glossary is missing. Re-run
  `lake manage-glossary --action apply` and check the output for terms
  that were skipped.
- **Stale tag values.** Tags from earlier runs may be out of date.
  Re-running `lake catalog` refreshes them.

For deeper tuning, see the official documentation:
<https://cloud.google.com/bigquery/docs/data-engineering-agent-pipelines>.

## Source files

- Property graph DDL (this doc): reproduced from
  `docs/marketing-lake-graph.sql` (the original SQL file is no longer
  shipped; the production DDL lives in the fenced block above).
- Conceptual graph tutorial: adapted from
  `docs/Intro_to_BigQuery_graph.md`.
- Data Engineering Agent guidance: adapted from
  `docs/data-engineering-agent.md`.
