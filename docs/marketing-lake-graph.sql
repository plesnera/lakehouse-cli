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