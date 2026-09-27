"""
FMCG Price Intelligence — Data Layer
====================================
DuckDB-backed OLAP layer over a git-versioned Parquet fact table.

- `ingest()` is idempotent: one row per retailer x SKU x day, latest scrape wins,
  so re-running a day (manual dispatch, retries) never duplicates history.
- Analytical logic lives in `sql/*.sql` views (obs -> priced -> active); the
  functions below are thin, named queries over those views that feed the cube.

Why DuckDB: in-process analytical SQL over Parquet, zero server, runs anywhere.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
FACT_PARQUET = DATA_DIR / "fmcg_prices.parquet"

FACT_COLUMNS = [
    "scraped_at", "retailer", "market", "currency", "product_id", "brand",
    "variant", "sugar_class", "pack", "container", "title", "base_price",
    "unit_price", "unit_price_basis", "clubcard_price_text", "deposit",
    "sugar_g_per_serving", "source_url", "status",
    "pack_count", "total_litres", "is_flavoured", "search_query",
]
_TYPES = {
    "base_price": "DOUBLE", "unit_price": "DOUBLE", "deposit": "DOUBLE",
    "sugar_g_per_serving": "DOUBLE", "pack_count": "INTEGER",
    "total_litres": "DOUBLE", "is_flavoured": "BOOLEAN",
}
DEFAULT_ACTIVE_WINDOW_DAYS = 2


def _schema_ddl() -> str:
    return ", ".join(f"{c} {_TYPES.get(c, 'VARCHAR')}" for c in FACT_COLUMNS)


def _sql_path(p: Path) -> str:
    return str(p).replace("'", "''")


# --- Ingestion ---------------------------------------------------------------

def ingest(records: list, parquet_path: Path = FACT_PARQUET) -> int:
    """Upsert today's OK records into the fact table; returns total row count."""
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [dataclasses.asdict(r) if dataclasses.is_dataclass(r) else r for r in records]
    rows = [r for r in rows if r.get("status") == "OK"]

    con = duckdb.connect(":memory:")
    con.execute(f"CREATE TABLE hist ({_schema_ddl()})")
    if parquet_path.exists():
        # BY NAME tolerates older files that predate newer columns (e.g. search_query).
        con.execute(f"INSERT INTO hist BY NAME SELECT * FROM read_parquet('{_sql_path(parquet_path)}')")
    if rows:
        con.executemany(
            f"INSERT INTO hist ({', '.join(FACT_COLUMNS)}) VALUES ({', '.join(['?'] * len(FACT_COLUMNS))})",
            [[row.get(c) for c in FACT_COLUMNS] for row in rows],
        )
    con.execute("""
        CREATE TABLE clean AS
        SELECT * FROM hist
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY retailer, product_id, CAST(scraped_at AS DATE)
            ORDER BY scraped_at DESC) = 1
        ORDER BY scraped_at, product_id
    """)
    con.execute(f"COPY clean TO '{_sql_path(parquet_path)}' (FORMAT PARQUET)")
    total = con.execute("SELECT COUNT(*) FROM clean").fetchone()[0]
    con.close()
    return total


# --- Analytical connection ---------------------------------------------------

def connect(parquet_path: Path = FACT_PARQUET,
            active_window_days: int = DEFAULT_ACTIVE_WINDOW_DAYS) -> duckdb.DuckDBPyConnection:
    """In-memory connection with the analytical views registered."""
    con = duckdb.connect(":memory:")
    fact = f"read_parquet('{_sql_path(parquet_path)}')"
    for f in sorted(SQL_DIR.glob("*.sql")):
        sql = (f.read_text(encoding="utf-8")
               .replace("{fact}", fact)
               .replace("{active_window_days}", str(int(active_window_days))))
        con.execute(sql)
    return con


def _df(con, sql: str, params: list | None = None):
    return con.execute(sql, params or []).df()


# --- Cube queries ------------------------------------------------------------

def latest_prices(con):
    """Current price of every active SKU (delisted SKUs excluded)."""
    return _df(con, """
        SELECT product_id, brand, variant, title, pack, pack_count, container,
               sugar_class, is_core, flavoured, caffeine_free, total_litres,
               base_price, regular_price, effective_price,
               ROUND(regular_ppl, 2) AS regular_ppl,
               ROUND(effective_ppl, 2) AS effective_ppl,
               mechanic, promo_text, loyalty_gated,
               ROUND(promo_depth, 3) AS promo_depth,
               strftime(d, '%Y-%m-%d') AS last_seen
        FROM active
        ORDER BY sugar_class, regular_ppl
    """)


def sugar_tax_spread(con, levy_per_litre: float):
    """
    Like-for-like full-sugar vs Zero spread on active core SKUs (no flavours,
    no caffeine-free), matched by pack size, count and container.

    `spread_regular_*` uses regular shelf prices (price-pack architecture);
    `spread_effective_*` uses today's promotional prices (what shoppers pay).
    `levy_ratio` = regular spread / levy per litre. A ratio of 1.0 means the
    full-sugar premium equals the levy; it is a benchmark, not a measured
    pass-through — the premium also reflects commercial choices.
    """
    return _df(con, """
        WITH f AS (
            SELECT pack, container, pack_count, format_key,
                AVG(regular_ppl)   FILTER (WHERE sugar_class = 'full') AS full_reg,
                AVG(regular_ppl)   FILTER (WHERE sugar_class = 'zero') AS zero_reg,
                AVG(regular_ppl)   FILTER (WHERE sugar_class = 'diet') AS diet_reg,
                AVG(effective_ppl) FILTER (WHERE sugar_class = 'full') AS full_eff,
                AVG(effective_ppl) FILTER (WHERE sugar_class = 'zero') AS zero_eff,
                BOOL_OR(mechanic <> 'none')                          AS any_promo,
                MIN(total_litres / pack_count)                       AS unit_litres
            FROM active
            WHERE is_core
            GROUP BY ALL
        )
        SELECT pack, container, pack_count, format_key,
            ROUND(full_reg, 2) AS full_per_litre,
            ROUND(zero_reg, 2) AS zero_per_litre,
            ROUND(diet_reg, 2) AS diet_per_litre,
            ROUND(full_reg - zero_reg, 2) AS spread_per_litre,
            ROUND(100 * (full_reg - zero_reg) / NULLIF(zero_reg, 0), 1) AS spread_pct,
            ROUND((full_reg - zero_reg) / ?, 2) AS levy_ratio,
            ROUND(full_eff - zero_eff, 2) AS spread_effective_per_litre,
            any_promo
        FROM f
        WHERE full_reg IS NOT NULL AND zero_reg IS NOT NULL
        ORDER BY pack_count, unit_litres
    """, [levy_per_litre])


def price_trend(con):
    """Daily regular and effective EUR/litre by format x sugar class (core SKUs)."""
    return _df(con, """
        SELECT strftime(d, '%Y-%m-%d') AS date, format_key, pack, pack_count,
               container, sugar_class,
               ROUND(AVG(regular_ppl), 3)   AS regular_ppl,
               ROUND(AVG(effective_ppl), 3) AS effective_ppl
        FROM priced
        WHERE is_core
        GROUP BY ALL
        ORDER BY date, pack_count, pack, sugar_class
    """)


def promo_summary(con):
    """Promotion frequency, mechanics and depth per SKU over the full history."""
    return _df(con, """
        WITH a AS (SELECT DISTINCT product_id FROM active)
        SELECT p.product_id, ANY_VALUE(p.title) AS title, ANY_VALUE(p.sugar_class) AS sugar_class,
               ANY_VALUE(p.format_key) AS format_key,
               COUNT(*) AS days_observed,
               ROUND(AVG((p.mechanic <> 'none')::INT), 3) AS promo_share,
               string_agg(DISTINCT p.mechanic, ', ' ORDER BY p.mechanic)
                   FILTER (WHERE p.mechanic <> 'none') AS mechanics,
               ROUND(MAX(p.promo_depth), 3) AS max_depth,
               ROUND(AVG(p.promo_depth) FILTER (WHERE p.mechanic <> 'none'), 3) AS avg_depth,
               COUNT(DISTINCT p.base_price) AS distinct_prices,
               (p.product_id IN (SELECT product_id FROM a)) AS active
        FROM priced p
        GROUP BY p.product_id
        ORDER BY active DESC, promo_share DESC, title
    """)


def daily_counts(con):
    """Distinct SKUs observed per day — the basis of the data-quality gate."""
    return _df(con, """
        SELECT strftime(d, '%Y-%m-%d') AS date, COUNT(DISTINCT product_id) AS skus
        FROM obs GROUP BY d ORDER BY d
    """)


def recent_median_skus(parquet_path: Path = FACT_PARQUET, days: int = 7) -> float | None:
    if not parquet_path.exists():
        return None
    con = connect(parquet_path)
    row = con.execute(f"""
        SELECT MEDIAN(n) FROM (
            SELECT d, COUNT(DISTINCT product_id) AS n FROM obs
            GROUP BY d ORDER BY d DESC LIMIT {int(days)})
    """).fetchone()
    con.close()
    return float(row[0]) if row and row[0] is not None else None
