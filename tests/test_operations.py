import json
from datetime import date, timedelta
from pathlib import Path

import datastore as ds
import run
from scraper import load_config, parse_cards
from test_datastore import rec, FULL, ZERO


def test_partial_brand_collection_cannot_hide_behind_total(tmp_path):
    p = tmp_path / 'f.parquet'
    cfg = load_config()
    records = [rec(1, str(i), FULL, 'full', 4.2) for i in range(8)]
    records += [rec(1, 'P'+str(i), 'Pepsi Bottle (2 L)', 'full', 3, brand='Pepsi') for i in range(8)]
    ds.ingest(records, p)
    surviving = records[:8] + records[8:9]
    assert 'Pepsi' in run.quality_gate(len(surviving), cfg, p, surviving)
    assert run.quality_gate(len(records), cfg, p, records) is None
    assert 'required brand' in run.quality_gate(8, cfg, p, records[:8])


def test_gaps_and_unverified_prices_block_pattern_labels(tmp_path):
    p = tmp_path / 'f.parquet'
    records = [rec(1, 'F', FULL, 'full', 4.2), rec(2, 'F', FULL, 'full', 3.5, 'Only €3.50'),
               rec(9, 'F', FULL, 'full', 4.2), rec(9, 'Z', ZERO, 'zero', 2.35, 'Only €2.35')]
    ds.ingest(records, p)
    con = ds.connect(p)
    r = ds.reliability(con, load_config())
    assert r['calendar_days'] == 9 and r['observed_days'] == 3
    assert r['missing_dates'] == [f'2026-07-{i:02d}' for i in range(3, 9)]
    assert all(x['pattern'] is None for x in r['patterns'])
    assert r['price_evidence']['unknown_regular'] == 1
    assert r['price_evidence']['independent_validation'] == 'pending'
    con.close()


def test_complete_window_gets_only_descriptive_pattern(tmp_path):
    p = tmp_path / 'f.parquet'
    records = []
    for day in range(1, 29):
        records.append(rec(day, 'F', FULL, 'full', 4.2))
    ds.ingest(records, p)
    con = ds.connect(p)
    r = ds.reliability(con, load_config())
    assert r['patterns'][0]['status'] == 'ready'
    assert r['patterns'][0]['pattern'] == 'low_promotion'
    con.close()


def test_live_fixture_keeps_the_offer_behind_generic_badge():
    path = Path(__file__).parents[1] / 'scrapers/fixtures/supervalu_cards_20261027.html'
    cards = parse_cards(path.read_text())
    assert len(cards) == 4
    assert cards[0]['promo'] == 'Great Value | 3 for €6'
    assert cards[1]['promo'] == 'Great Value | 3 for €6'
    assert cards[0]['deposit'] == 0.25
    assert cards[2]['deposit'] == 0.15


def test_multiple_badges_flow_through_to_effective_price_and_deposit(tmp_path):
    p = tmp_path / 'f.parquet'
    r = rec(1, 'F', FULL, 'full', 3.5, 'Great Value | 3 for €6')
    r.deposit = 0.25
    ds.ingest([r], p)
    con = ds.connect(p)
    row = ds.latest_prices(con).iloc[0]
    assert row.effective_price == 2.0 and row.payable_incl_deposit == 2.25
    assert row.regular_price == 3.5
    con.close()


def test_cube_reliability_serializes_as_strict_json(tmp_path):
    p = tmp_path / 'f.parquet'
    ds.ingest([rec(1, 'F', FULL, 'full', 4.2), rec(1, 'Z', ZERO, 'zero', 3.4)], p)
    out = tmp_path / 'cube.json'
    run.export_cube_json(load_config(), p, out, build_site=False)
    cube = json.loads(out.read_text())
    assert cube['schema_version'] == 8 and 'price_evidence' in cube['reliability']


def test_collection_outage_is_not_a_mass_relisting_or_delisting(tmp_path):
    p = tmp_path / 'gap.parquet'
    ds.ingest([rec(1, 'F', FULL, 'full', 4.2), rec(1, 'Z', ZERO, 'zero', 3.4)], p)
    ds.ingest([rec(9, 'F', FULL, 'full', 4.2, '3 for €6')], p)
    con = ds.connect(p)
    items = ds.change_feed(con, days=9)['items']
    assert not any(i['kind'] in ['relisted', 'delisted'] for i in items)
    assert items[0]['kind'] == 'promo_start' and items[0]['after_collection_gap']
    con.close()


def test_generic_badge_to_multibuy_is_capture_evidence_not_a_claimed_change(tmp_path):
    p = tmp_path / 'badges.parquet'
    ds.ingest([rec(1, 'F', FULL, 'full', 3.5, 'Great Value'),
               rec(2, 'F', FULL, 'full', 3.5, 'Great Value | 3 for €6')], p)
    con = ds.connect(p)
    item = ds.change_feed(con)['items'][0]
    assert item['kind'] == 'offer_capture' and item['offer_to'] == '3 for €6.00'
    con.close()
