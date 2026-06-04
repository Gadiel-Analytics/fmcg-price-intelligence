"""
FMCG Price Intelligence — Daily Run Entrypoint (M3)
===================================================
Wires the SuperValu scraper (M1) to the DuckDB data layer (M2), then exports
the cube slices the dashboard (M4) consumes. Invoked daily by GitHub Actions.

Usage:
    python run.py    # live scrape + ingest + cube export
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scrapers"))

from scraper import load_config, scrape  # noqa: E402
from datastore import (  # noqa: E402
    ingest, latest_prices, sugar_tax_spread, price_trend, DATA_DIR,
)

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def export_cube_json() -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "latest": json.loads(latest_prices().to_json(orient="records")),
        "sugar_tax_spread": json.loads(sugar_tax_spread().to_json(orient="records")),
        "trend": json.loads(price_trend().to_json(orient="records")),
    }
    out = REPORTS_DIR / "cube.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"path": str(out), "latest_rows": len(payload["latest"])}


def main() -> int:
    config = load_config()
    records = scrape(config)
    ok = sum(1 for r in records if r.status == "OK")
    total = len(records)
    print(f"Scrape: {ok}/{total} rows OK")

    if ok == 0:
        print("WARNING: zero successful scrapes — not updating the cube.")
        return 1

    n = ingest(records)
    print(f"Ingested. Historical fact table now holds {n} rows.")
    print(f"Data lake: {DATA_DIR / 'fmcg_prices.parquet'}")

    exp = export_cube_json()
    print(f"Dashboard cube: {exp['path']} ({exp['latest_rows']} latest rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
