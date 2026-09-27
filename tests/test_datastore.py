import duckdb
import pytest

import datastore as ds
from scraper import PriceRecord


def rec(day, sku, title, sugar, price, promo=None, pack="2 L", count=1, litres=2.0, container="PET",
        hour="08"):
    return PriceRecord(
        scraped_at=f"2026-07-{day:02d}T{hour}:00:00+00:00", retailer="supervalu_ie", market="IE",
        currency="EUR", product_id=sku, brand="Coca-Cola", variant="x", sugar_class=sugar,
        pack=pack, container=container, title=title, base_price=price,
        unit_price=round(price / litres, 2), unit_price_basis="litre", clubcard_price_text=promo,
        deposit=None, sugar_g_per_serving=None, source_url="u", status="OK",
        pack_count=count, total_litres=litres, is_flavoured=False, search_query="coca cola")


FULL, ZERO = "Coca-Cola Bottle (2 L)", "Coca-Cola Zero Sugar Bottle (2 L)"


@pytest.fixture
def lake(tmp_path):
    p = tmp_path / "f.parquet"
    ds.ingest([rec(1, "F", FULL, "full", 4.20), rec(1, "Z", ZERO, "zero", 3.40, "3 for €6.75"),
               rec(1, "OLD", FULL.replace("2 L", "2L old"), "full", 9.99)], p)
    ds.ingest([rec(2, "F", FULL, "full", 3.50, "Only €3.50"), rec(2, "Z", ZERO, "zero", 3.40)], p)
    ds.ingest([rec(9, "F", FULL, "full", 4.20), rec(9, "Z", ZERO, "zero", 2.35, "Only €2.35")], p)
    return p


def test_ingest_is_idempotent(lake):
    before = duckdb.sql(f"SELECT COUNT(*) FROM read_parquet('{lake}')").fetchone()[0]
    # re-running day 9 later in the day replaces, never duplicates
    ds.ingest([rec(9, "F", FULL, "full", 4.10, hour="12")], lake)
    after = duckdb.sql(f"SELECT COUNT(*), MAX(base_price) FILTER (WHERE product_id='F' "
                       f"AND scraped_at LIKE '2026-07-09%') FROM read_parquet('{lake}')").fetchone()
    assert before == after[0] == 7
    assert after[1] == 4.10


def test_legacy_files_without_new_columns(tmp_path):
    p = tmp_path / "legacy.parquet"
    cols = [c for c in ds.FACT_COLUMNS if c != "search_query"]
    duckdb.sql(f"COPY (SELECT '2026-06-01T08:00:00+00:00' AS scraped_at, "
               + ", ".join(f"NULL AS {c}" for c in cols if c != "scraped_at")
               + f") TO '{p}' (FORMAT PARQUET)")
    assert ds.ingest([rec(1, "F", FULL, "full", 4.20)], p) == 2


def test_mechanics_regular_and_effective_price(lake):
    con = ds.connect(lake, active_window_days=2)
    rows = {(r[0], r[1]): r[2:] for r in con.execute(
        "SELECT product_id, day(d), mechanic, regular_price, effective_price FROM priced").fetchall()}
    assert rows[("Z", 1)] == ("multibuy", 3.40, 2.25)     # 3 for €6.75
    assert rows[("F", 2)] == ("price_cut", 4.20, 3.50)    # regular carried forward
    assert rows[("Z", 9)] == ("price_cut", 3.40, 2.35)


def test_active_excludes_delisted(lake):
    con = ds.connect(lake, active_window_days=2)
    ids = {r[0] for r in con.execute("SELECT product_id FROM active").fetchall()}
    assert ids == {"F", "Z"}                               # OLD last seen on day 1


def test_spread_uses_regular_prices_and_levy(lake):
    con = ds.connect(lake, active_window_days=2)
    s = ds.sugar_tax_spread(con, 0.30).iloc[0]
    assert s.full_per_litre == 2.10 and s.zero_per_litre == 1.70
    assert s.spread_per_litre == 0.40 and s.levy_ratio == 1.33
    assert s.spread_effective_per_litre == pytest.approx(0.93, abs=0.01)   # 2.10 - 1.175
