"""Read-only HTTPS smoke test: public bytes must match the candidate publication."""
from __future__ import annotations
import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scrapers'))
from scraper import load_config

PATHS = ['index.html', 'reports/dashboard.html', 'reports/cube.json',
         'assets/freshness.js', 'sitemap.xml', 'robots.txt', 'reports/favicon.svg']


def verify(base: str, root: Path = ROOT) -> dict:
    matches = []
    for path in PATHS:
        url = base.rstrip('/') + '/' + ('' if path == 'index.html' else path)
        # A unique query avoids checking an older CDN copy after publication.
        request = Request(url + '?verify=' + str(time.time_ns()),
                          headers={'User-Agent': 'GadielAnalytics-ReleaseCheck/1.0'})
        with urlopen(request, timeout=20) as response:
            assert response.status == 200, (path, response.status)
            assert response.url.startswith('https://'), 'HTTPS redirect downgraded'
            live = response.read()
        expected = (root / path).read_bytes()
        assert hashlib.sha256(live).digest() == hashlib.sha256(expected).digest(), f'publication differs: {path}'
        matches.append(path)
    cube = json.loads((root / 'reports/cube.json').read_text())
    return {'url': base, 'last_observation': cube['last_run_date'], 'matching_files': matches}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--attempts', type=int, default=1)
    ap.add_argument('--delay', type=int, default=20)
    ap.add_argument('--base-url', default=load_config()['site']['base_url'])
    args = ap.parse_args()
    for attempt in range(1, args.attempts + 1):
        try:
            print(json.dumps(verify(args.base_url), indent=2), flush=True)
            return 0
        except Exception as exc:
            print(f'Production check {attempt}/{args.attempts}: {exc}', flush=True)
            if attempt < args.attempts:
                time.sleep(args.delay)
    return 1

if __name__ == '__main__':
    raise SystemExit(main())
