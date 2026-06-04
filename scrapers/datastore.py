"""
FMCG Price Intelligence — Data Layer (M2)
=========================================
DuckDB-backed OLAP layer. Ingests daily PriceRecord rows, persists an append-only
historical fact table to Parquet (versioned in git), and exposes the analytical
"cube" queries — including the signature Sugar-Tax spread on a like-for-like,
price-per-litre basis.

Why DuckDB: in-process analytical SQL over Parquet, zero server, runs anywhere.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import duckdb

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FACT_PARQUET = DATA_DIR / "fmcg_prices.parquet"

FACT_COLUMNS = [
    "scraped_at", "retailer", "market", "currency", "product_id", "brand",
    "variant", "sugar_class", "pack", "container", "title", "base_price",
    "unit_price", "unit_price_basis", "clubcard_price_text", "deposit",
    "sugar_g_per_serving", "source_url", "status",
    "pack_count", "total_litres", "is_flavoured",
]


def _connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(database=":memory:")


def _schema_ddl() -> str:
    types = {
        "base_price": "DOUBLE", "unit_price": "DOUBLE", "deposit": "DOUBLE",
        "sugar_g_per_serving": "DOUBLE", "pack_count": "INTEGER",
        "total_litres": "DOUBLE", "is_flavoured": "BOOLEAN",
    }
    return ", ".join(f"{c} {types.get(c, 'VARCHAR')}" for c in FACT_COLUMNS)


def ingest(records: list, parquet_path: Path = FACT_PARQUET) -> int:
    """Append today's records to the historical fact table (Parquet, append-only)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = [dataclasses.asdict(r) if dataclasses.is_dataclass(r) else r for r in records]
    rows = [r for r in rows if r.get("status") == "OK"]  # only persist good rows

    con = _connect()
    con.execute(f"CREATE TABLE incoming ({_schema_ddl()})")
    if rows:
        con.executemany(
            f"INSERT INTO incoming VALUES ({', '.join(['?'] * len(FACT_COLUMNS))})",
            [[row.get(c) for c in FACT_COLUMNS] for row in rows],
        )

    if parquet_path.exists():
        con.execute(f"CREATE TABLE hist AS SELECT * FROM read_parquet('{parquet_path}')")
        con.execute("INSERT INTO hist SELECT * FROM incoming")
    else:
        con.execute("CREATE TABLE hist AS SELECT * FROM incoming")

    con.execute(f"COPY hist TO '{parquet_path}' (FORMAT PARQUET)")
    total = con.execute("SELECT COUNT(*) FROM hist").fetchone()[0]
    con.close()
    return total


def latest_prices(parquet_path: Path = FACT_PARQUET):
    con = _connect()
    df = con.execute(f"""
        WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY retailer, product_id ORDER BY scraped_at DESC
            ) AS rn
            FROM read_parquet('{parquet_path}')
            WHERE status = 'OK'
        )
        SELECT brand, variant, pack, pack_count, container, sugar_class,
               base_price, unit_price, total_litres, is_flavoured,
               clubcard_price_text, scraped_at
        FROM ranked WHERE rn = 1
        ORDER BY sugar_class, unit_price
    """).df()
    con.close()
    return df


def sugar_tax_spread(parquet_path: Path = FACT_PARQUET):
    """
    SIGNATURE INSIGHT — like-for-like Sugar-Tax spread.
    Compares full-sugar vs zero on €/litre, matched by pack (unit size) and
    container, excluding flavoured variants (Cherry/Vanilla) so we compare the
    core cola only. Positive spread = full-sugar dearer per litre = visible
    pass-through of Ireland's Sugar-Sweetened Drinks Tax.
    """
    con = _connect()
    df = con.execute(f"""
        WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY retailer, product_id ORDER BY scraped_at DESC
            ) AS rn
            FROM read_parquet('{parquet_path}')
            WHERE status = 'OK' AND unit_price IS NOT NULL AND NOT is_flavoured
        ),
        latest AS (SELECT * FROM ranked WHERE rn = 1),
        by_format AS (
            SELECT pack, container, pack_count,
                   AVG(CASE WHEN sugar_class = 'full' THEN unit_price END) AS full_per_litre,
                   AVG(CASE WHEN sugar_class = 'zero' THEN unit_price END) AS zero_per_litre
            FROM latest
            GROUP BY pack, container, pack_count
        )
        SELECT pack, container, pack_count,
               ROUND(full_per_litre, 2) AS full_per_litre,
               ROUND(zero_per_litre, 2) AS zero_per_litre,
               ROUND(full_per_litre - zero_per_litre, 2) AS spread_per_litre,
               ROUND(100.0 * (full_per_litre - zero_per_litre)
                     / NULLIF(zero_per_litre, 0), 1) AS spread_pct
        FROM by_format
        WHERE full_per_litre IS NOT NULL AND zero_per_litre IS NOT NULL
        ORDER BY pack_count, pack
    """).df()
    con.close()
    return df


def price_trend(parquet_path: Path = FACT_PARQUET):
    con = _connect()
    df = con.execute(f"""
        SELECT CAST(scraped_at AS DATE) AS date, variant, pack, pack_count,
               AVG(base_price) AS base_price,
               AVG(unit_price) AS price_per_litre
        FROM read_parquet('{parquet_path}')
        WHERE status = 'OK' AND NOT is_flavoured
        GROUP BY 1,2,3,4
        ORDER BY date, variant, pack
    """).df()
    con.close()
    return df
