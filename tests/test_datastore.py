import duckdb
import pytest

import datastore as ds
from scraper import PriceRecord


def rec(day, sku, title, sugar, price, promo=None, pack="2 L", count=1, litres=2.0, container="PET",
        hour="08", brand="Coca-Cola"):
    return PriceRecord(
        scraped_at=f"2026-07-{day:02d}T{hour}:00:00+00:00", retailer="supervalu_ie", market="IE",
        currency="EUR", product_id=sku, brand=brand, variant="x", sugar_class=sugar,
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


def test_competition_index_and_brand_summary(tmp_path):
    p = tmp_path / "c.parquet"
    ds.ingest([
        rec(1, "F", FULL, "full", 4.20), rec(1, "Z", ZERO, "zero", 3.40),
        rec(1, "PF", "Pepsi Bottle (2 L)", "full", 3.00, brand="Pepsi"),
        rec(1, "PZ", "Pepsi Max Bottle (2 L)", "zero", 3.00, "2 for €5", brand="Pepsi"),
        rec(1, "OL", "SuperValu Cola Bottle (2 L)", "full", 1.00, brand="SuperValu"),
        rec(1, "M", "Monster Energy Drink Can (500 ml)", "full", 2.20, pack="500 ml",
            litres=0.5, container="Can", brand="Monster"),
    ], p)
    con = ds.connect(p, 2)
    ci = ds.competition_index(con)
    full = ci[(ci.sugar_tier == "full")].set_index("brand_family")
    assert full.loc["Coca-Cola", "regular_index"] == 100
    assert full.loc["Pepsi", "regular_index"] == 71            # 1.50 / 2.10
    assert full.loc["SuperValu own-label", "regular_index"] == 24
    assert full.loc["Pepsi", "effective_index"] == 71
    assert set(ci.segment) == {"Cola"}                           # Monster has no rival format
    bs = ds.brand_summary(con).set_index("brand_family")
    assert bs.loc["Coca-Cola", "sugar_premium"] == pytest.approx(0.235, abs=0.001)
    assert bs.loc["Pepsi", "sugar_premium"] == 0.0              # Pepsi and Pepsi Max at parity
    assert bs.loc["Pepsi", "promo_share"] == 0.5
    assert bool(bs.loc["SuperValu own-label", "private_label"])


def test_spread_is_coca_cola_only(tmp_path):
    p = tmp_path / "s.parquet"
    ds.ingest([rec(1, "F", FULL, "full", 4.20), rec(1, "Z", ZERO, "zero", 3.40),
               rec(1, "PF", "Pepsi Bottle (2 L)", "full", 9.00, brand="Pepsi")], p)
    s = ds.sugar_tax_spread(ds.connect(p, 2), 0.30).iloc[0]
    assert s.full_per_litre == 2.10


def test_regular_price_unknown_when_never_seen_clean(tmp_path):
    p = tmp_path / "u.parquet"
    ds.ingest([rec(1, "S", "7UP Free Bottle (2 L)", "zero", 2.00, "Only €2.00", brand="7UP")], p)
    row = ds.connect(p, 2).execute(
        "SELECT regular_price, regular_ppl, promo_depth FROM priced").fetchone()
    assert row == (None, None, None)


def test_volume_typo_and_cola_flavours(tmp_path):
    p = tmp_path / "v.parquet"
    ds.ingest([rec(1, "T", "Fanta Crimson Cherry Bottle (1.75 ml)", "full", 3.25, pack="1.75 ml",
                   litres=0.00175, brand="Fanta"),
               rec(1, "C", "Pepsi Cream Soda Zero Sugar Bottle (2 L)", "zero", 2.65, brand="Pepsi")], p)
    con = ds.connect(p, 2)
    t = con.execute("SELECT total_litres, volume_corrected, effective_ppl FROM priced WHERE product_id='T'").fetchone()
    assert t[0] == pytest.approx(1.75) and t[1] and t[2] == pytest.approx(1.857, abs=0.001)
    assert con.execute("SELECT is_core FROM obs WHERE product_id='C'").fetchone()[0] is False


def test_head_to_head_and_calendar(tmp_path):
    p = tmp_path / "h.parquet"
    ds.ingest([rec(1, "F", FULL, "full", 4.20), rec(1, "Z", ZERO, "zero", 3.40, "3 for €6.75")], p)
    ds.ingest([rec(2, "F", FULL, "full", 4.20), rec(2, "Z", ZERO, "zero", 3.40, "3 for €6.75"),
               rec(2, "PF", "Pepsi Regular Bottle (2 L)", "full", 2.65, "Only €2.65", brand="Pepsi"),
               rec(2, "PZ", "Pepsi Max No Sugar Cola Bottle (2 L)", "zero", 2.65, "Only €2.65", brand="Pepsi"),
               rec(2, "PC", "Pepsi Cream Soda Zero Sugar Bottle (2 L)", "zero", 1.00, brand="Pepsi")], p)
    con = ds.connect(p, 2)
    h = ds.head_to_head(con).set_index("sugar_tier")
    assert h.loc["full", "gap"] == pytest.approx(2.65 / 4.20 - 1, abs=0.001)
    assert h.loc["no_sugar", "hero_price"] == 2.25                  # multibuy per unit
    assert h.loc["no_sugar", "rival_price"] == 2.65                 # cream soda excluded
    cal = ds.promo_calendar(con)
    assert cal["days"] == 2
    codes = {s["product_id"]: s["codes"] for s in cal["skus"]}
    assert codes["Z"] == "mm" and codes["PF"] == ".p" and "F" not in codes
    bs = ds.brand_summary(con).set_index("brand_family")
    assert bs.loc["Pepsi", "parity_formats_today"] == 1


def test_levy_in_force_uses_schedule():
    a = {"levy_per_litre_incl_vat": 0.30,
         "levy_schedule": [{"from": "2018-05-01", "per_litre_incl_vat": 0.30},
                           {"from": "2027-01-01", "per_litre_incl_vat": 0.40}]}
    assert ds.levy_in_force(a, "2026-12-31") == 0.30
    assert ds.levy_in_force(a, "2027-01-01") == 0.40
    assert ds.levy_in_force({"levy_per_litre_incl_vat": 0.30}, "2026-01-01") == 0.30


def _event_lake(tmp_path, days, jump_from=None):
    p = tmp_path / "e.parquet"
    for day in days:
        full = 4.60 if jump_from and day >= jump_from else 4.20
        ds.ingest([rec(day, "F", FULL, "full", full), rec(day, "Z", ZERO, "zero", 3.40),
                   rec(day, "PF", "Pepsi Regular Bottle (2 L)", "full", 2.65, brand="Pepsi")], p)
    return p


def test_event_study_upcoming_captures_baseline(tmp_path):
    p = _event_lake(tmp_path, range(1, 6))
    ev = ds.event_study(ds.connect(p, 2), [{"id": "b", "date": "2026-07-20", "label": "Budget"}], 14)[0]
    assert ev["status"] == "upcoming" and ev["days_to"] == 15
    assert ev["pre_start"] == "2026-07-01" and ev["pre_days"] == 5
    r = ev["rows"][0]
    assert r["prem_pre"] == pytest.approx(0.40) and r["prem_post"] is None


def test_event_study_after_event_measures_change(tmp_path):
    p = _event_lake(tmp_path, range(1, 21), jump_from=11)
    ev = ds.event_study(ds.connect(p, 2), [{"id": "b", "date": "2026-07-11", "label": "Budget"}], 14)[0]
    assert ev["status"] == "in_window" and ev["post_days"] == 10
    r = ev["rows"][0]
    assert r["prem_pre"] == pytest.approx(0.40) and r["prem_post"] == pytest.approx(0.60)
    assert r["delta"] == pytest.approx(0.20)
    g = ev["rival"][0]
    assert g["gap_pre"] == pytest.approx(2.65 / 4.20 - 1, abs=0.001)
    assert g["gap_post"] == pytest.approx(2.65 / 4.60 - 1, abs=0.001)
