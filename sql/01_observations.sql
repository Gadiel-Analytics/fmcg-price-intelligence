-- =============================================================================
-- obs: one row per retailer x SKU x day (latest scrape of the day wins),
-- with flags derived from the title and the promotion badge parsed into a
-- mechanic. Derivations live here, not in the scraper, so every rule change
-- is applied retroactively to the full history.
--
-- Placeholder {fact} is substituted with read_parquet('<path>') by datastore.py.
-- Table brand_map (priority, term, family, owner, segment, private_label) is
-- created from config/catalog.yaml by datastore.connect() before this file runs.
-- =============================================================================
CREATE OR REPLACE VIEW obs AS
WITH raw AS (
    SELECT *,
           CAST(scraped_at AS DATE) AS d,
           NULLIF(TRIM(clubcard_price_text), '') AS promo_text
    FROM {fact}
    WHERE status = 'OK' AND base_price IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY retailer, product_id, CAST(scraped_at AS DATE)
        ORDER BY scraped_at DESC) = 1
),
mapped AS (
    SELECT r.*, m.family AS brand_family, m.owner, m.segment, m.private_label
    FROM raw r
    LEFT JOIN LATERAL (
        SELECT family, owner, segment, private_label FROM brand_map
        WHERE lower(regexp_replace(COALESCE(r.brand, r.title), '[-\s]+', ' ', 'g')) LIKE '%' || term || '%'
        ORDER BY priority LIMIT 1
    ) m ON TRUE
),
flags AS (
    SELECT *,
        regexp_matches(lower(title), 'cherry|vanilla|lime|mango|raspberry') AS flavoured,
        (title ILIKE '%caffeine free%' OR title ILIKE '%zero caffeine%')   AS caffeine_free,
        TRY_CAST(regexp_extract(promo_text, '(\d+)\s*for\s*€\s*(\d+(?:\.\d+)?)', 1) AS INTEGER) AS mb_qty,
        TRY_CAST(regexp_extract(promo_text, '(\d+)\s*for\s*€\s*(\d+(?:\.\d+)?)', 2) AS DOUBLE)  AS mb_price,
        TRY_CAST(regexp_extract(promo_text, 'Only\s*€\s*(\d+(?:\.\d+)?)', 1) AS DOUBLE)        AS only_price
    FROM mapped
)
SELECT *,
    -- Cola comparisons exclude flavour variants; other segments compare all flavours.
    NOT caffeine_free AND (COALESCE(segment, 'Cola') <> 'Cola' OR NOT flavoured) AS is_core,
    CASE WHEN sugar_class = 'full' THEN 'full' ELSE 'no_sugar' END AS sugar_tier,
    CASE
        WHEN promo_text IS NULL                     THEN 'none'
        WHEN mb_qty IS NOT NULL                     THEN 'multibuy'
        WHEN promo_text ILIKE '%rewards%'           THEN 'loyalty_price'
        WHEN only_price IS NOT NULL                 THEN 'price_cut'
        ELSE 'badge'
    END AS mechanic,
    COALESCE(promo_text ILIKE '%rewards%', FALSE) AS loyalty_gated,
    pack_count || 'x' || pack || ' ' || container AS format_key
FROM flags;


-- =============================================================================
-- priced: regular (non-promotional) price inferred per SKU-day, effective price
-- after the promotion, and both normalised to EUR/litre.
--
-- Rule: on 'none' and 'multibuy' days the card shows the shelf price, so it is a
-- clean observation of the regular price. On 'price_cut', 'loyalty_price' and
-- 'badge' days the card price is (or may be) reduced, so the regular price is
-- carried forward from the latest clean day, or back-filled from the next one.
-- NULL (unknown, never zero) when a SKU has never been seen at a clean price,
-- so its promotion depth is unknown rather than reported as 0%.
-- =============================================================================
CREATE OR REPLACE VIEW priced AS
WITH c AS (
    SELECT *,
        CASE WHEN mechanic IN ('none', 'multibuy') THEN base_price END AS clean_price
    FROM obs
),
r AS (
    SELECT *,
        COALESCE(
            LAST_VALUE(clean_price IGNORE NULLS) OVER (
                PARTITION BY retailer, product_id ORDER BY d
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
            FIRST_VALUE(clean_price IGNORE NULLS) OVER (
                PARTITION BY retailer, product_id ORDER BY d
                ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING)
        ) AS inferred_regular
    FROM c
)
SELECT *,
    -- NULL (unknown) when the SKU has never been seen at a clean price
    CASE WHEN inferred_regular IS NULL THEN NULL
         ELSE GREATEST(inferred_regular, base_price) END AS regular_price,
    (clean_price IS NULL)                  AS regular_is_inferred,
    CASE WHEN mechanic = 'multibuy'
         THEN LEAST(base_price, mb_price / mb_qty)
         ELSE base_price END               AS effective_price,
    ROUND(CASE WHEN inferred_regular IS NULL THEN NULL
               ELSE GREATEST(inferred_regular, base_price) END / total_litres, 4) AS regular_ppl,
    ROUND(CASE WHEN mechanic = 'multibuy'
               THEN LEAST(base_price, mb_price / mb_qty)
               ELSE base_price END / total_litres, 4)               AS effective_ppl,
    ROUND(1 - (CASE WHEN mechanic = 'multibuy'
                    THEN LEAST(base_price, mb_price / mb_qty)
                    ELSE base_price END)
              / NULLIF(CASE WHEN inferred_regular IS NULL THEN NULL
                            ELSE GREATEST(inferred_regular, base_price) END, 0), 4) AS promo_depth
FROM r
WHERE total_litres IS NOT NULL;


-- =============================================================================
-- active: latest observation per SKU, restricted to SKUs seen within
-- {active_window_days} days of the latest run (delisted SKUs drop out).
-- =============================================================================
CREATE OR REPLACE VIEW active AS
WITH lastrun AS (SELECT MAX(d) AS max_d FROM priced)
SELECT p.*
FROM priced p, lastrun
WHERE p.d >= lastrun.max_d - INTERVAL {active_window_days} DAY
QUALIFY ROW_NUMBER() OVER (PARTITION BY retailer, product_id ORDER BY d DESC) = 1;
