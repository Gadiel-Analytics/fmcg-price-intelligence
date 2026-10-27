"""Offline release gate over the real history and generated public artifacts."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scrapers')]
import datastore as ds
from scraper import load_config


def check(root: Path = ROOT) -> dict:
    cube = json.loads((root / 'reports/cube.json').read_text(),
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    assert cube['schema_version'] == 8
    con = ds.connect(root / 'data/fmcg_prices.parquet', config=load_config())
    duplicates = con.execute('''SELECT COUNT(*) FROM (
        SELECT retailer, product_id, CAST(scraped_at AS DATE), COUNT(*) AS n
        FROM read_parquet(?) GROUP BY ALL HAVING n > 1)''',
        [str(root / 'data/fmcg_prices.parquet')]).fetchone()[0]
    assert duplicates == 0, 'duplicate SKU-day keys'
    invalid = con.execute('''SELECT COUNT(*) FROM obs WHERE base_price <= 0
        OR total_litres IS NULL OR total_litres <= 0 OR brand_family IS NULL''').fetchone()[0]
    assert invalid == 0, 'invalid price, volume or unmapped brand'
    latest = str(con.execute('SELECT MAX(d) FROM obs').fetchone()[0])
    assert cube['last_run_date'] == latest
    assert len(cube['latest']) == cube['kpis']['active_skus']
    assert cube['reliability']['observed_days'] == len(cube['daily_counts'])
    assert cube['reliability']['observed_days'] + len(cube['reliability']['missing_dates']) == cube['reliability']['calendar_days']
    for p in cube['reliability']['patterns']:
        if p['status'] != 'ready':
            assert p['pattern'] is None
    for name in ['index.html', 'reports/dashboard.html']:
        text = (root / name).read_text()
        assert '{{' not in text, f'unrendered placeholder in {name}'
        assert 'id="data-status"' in text and f'data-date="{latest}"' in text
        assert 'rel="canonical"' in text
    ElementTree.fromstring((root / 'sitemap.xml').read_text())
    con.close()
    result = dict(last_observation=latest, active_skus=cube['kpis']['active_skus'],
                  observed_days=cube['days_of_history'], missing_dates=cube['reliability']['missing_dates'],
                  duplicate_keys=duplicates, invalid_observations=invalid)
    print(json.dumps(result, indent=2))
    return result

if __name__ == '__main__':
    check()
