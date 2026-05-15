# Introduction to BigQuery Graph (SQL/PGQ)

This note is a lightweight reference for modeling the marketing dataset as a BigQuery property graph.

## Key concepts

- A property graph is a logical layer over existing tables.
- You define entities as **node tables** and relationships as **edge tables**.
- Querying uses graph patterns (`MATCH`) instead of manually writing repeated multi-hop joins.

## Example: campaigns and creatives

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

## Why use graph modeling here

- Simplifies path-style analysis across entities such as:
  - campaign → creative → pixel event
  - audience → cookie registry → transactions
- Makes semantic traversal queries easier to read and maintain than nested joins.

## Query shape example

```sql
GRAPH `project.marketing.marketing_graph`
MATCH (c:campaign)<-[r:belongs_to]-(cr:creative)
RETURN c.campaign_name, cr.creative_name;
```

## Visual reference

![Relationship overview](img.png)