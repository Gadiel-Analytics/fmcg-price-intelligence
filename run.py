"""
FMCG Price Intelligence — Daily Run Entrypoint
==============================================
scrape -> quality gate -> idempotent ingest -> cube export. Invoked daily by
GitHub Actions.

Usage:
    python run.py                     # live scrape + ingest + cube export
    python run.py --dry-run           # parse the bundled fixture; no network, no writes
    python run.py --export-only       # rebuild reports/cube.json from existing history
    python run.py --capture-fixture   # save one live search page as a parser fixture
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scrapers"))

from scraper import (  # noqa: E402
    load_config, scrape, parse_cards, build_records, print_records, fetch_html,
)
import datastore as ds  # noqa: E402

REPORTS_DIR = ROOT / "reports"
FIXTURES_DIR = ROOT / "scrapers" / "fixtures"
DRY_RUN_FIXTURE = FIXTURES_DIR / "supervalu_search_synthetic.html"
CUBE_SCHEMA_VERSION = 5


def _records(df) -> list[dict]:
    """DataFrame -> JSON-safe records (NaN -> None)."""
    out = []
    for row in df.to_dict(orient="records"):
        out.append({k: (None if isinstance(v, float) and math.isnan(v) else v)
                    for k, v in row.items()})
    return out


def export_cube_json(config: dict, parquet_path: Path = ds.FACT_PARQUET,
                     out_path: Path = REPORTS_DIR / "cube.json") -> dict:
    analysis = config.get("analysis", {})
    con = ds.connect(parquet_path, int(analysis.get("active_window_days", 2)), config)
    last_d = con.execute("SELECT MAX(d) FROM obs").fetchone()[0]
    levy = ds.levy_in_force(analysis, last_d)

    latest = ds.latest_prices(con)
    spread = ds.sugar_tax_spread(con, levy)
    trend = ds.price_trend(con)
    promos = ds.promo_summary(con)
    counts = ds.daily_counts(con)
    competition = ds.competition_index(con)
    brands = ds.brand_summary(con)
    h2h = ds.head_to_head(con)
    calendar = ds.promo_calendar(con)
    events = ds.event_study(con, config.get("events") or [], int(analysis.get("event_window_days", 14)))
    promo_share = con.execute(
        "SELECT AVG((mechanic <> 'none')::INT) FROM obs WHERE brand_family = 'Coca-Cola'").fetchone()[0]
    con.close()

    ratios = [r for r in spread["levy_ratio"].tolist() if r == r]
    payload = {
        "schema_version": CUBE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "retailer": config["retailer"]["name"],
        "last_run_date": counts["date"].iloc[-1] if len(counts) else None,
        "first_run_date": counts["date"].iloc[0] if len(counts) else None,
        "days_of_history": int(len(counts)),
        "levy": {"per_litre_incl_vat": levy, "source": analysis.get("levy_source"),
                 "schedule": analysis.get("levy_schedule") or []},
        "kpis": {
            "active_skus": int(len(latest)),
            "brands_tracked": int(len(brands)),
            "promo_share_sku_days": round(float(promo_share or 0), 3),
            "levy_ratio_min": min(ratios) if ratios else None,
            "levy_ratio_max": max(ratios) if ratios else None,
            "formats_compared": int(len(spread)),
        },
        "latest": _records(latest),
        "sugar_tax_spread": _records(spread),
        "trend": _records(trend),
        "promo_summary": _records(promos),
        "daily_counts": _records(counts),
        "competition_index": _records(competition),
        "brand_summary": _records(brands),
        "head_to_head": _records(h2h),
        "promo_calendar": calendar,
        "events": events,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {"path": str(out_path), "latest_rows": len(payload["latest"])}


def quality_gate(ok_count: int, config: dict, parquet_path: Path = ds.FACT_PARQUET) -> str | None:
    """Return a failure reason, or None if the run is fit to ingest."""
    if ok_count == 0:
        return "zero successful rows"
    share = float(config.get("quality", {}).get("min_share_of_recent_median", 0.5))
    median = ds.recent_median_skus(parquet_path)
    if median and ok_count < share * median:
        return f"{ok_count} SKUs is below {share:.0%} of the 7-day median ({median:.0f})"
    return None


def cmd_live(config: dict) -> int:
    records = scrape(config)
    ok = sum(1 for r in records if r.status == "OK")
    failed = [r for r in records if r.status != "OK"]
    print(f"Scrape: {ok} SKUs OK, {len(failed)} failed queries")
    for r in failed:
        print(f"  FAILED query={r.search_query!r} status={r.status}")

    reason = quality_gate(ok, config)
    if reason:
        print(f"QUALITY GATE FAILED: {reason}. History and cube left unchanged.")
        return 1

    n = ds.ingest(records)
    print(f"Ingested. Fact table holds {n} rows ({ds.FACT_PARQUET}).")
    exp = export_cube_json(config)
    print(f"Cube: {exp['path']} ({exp['latest_rows']} active SKUs)")
    return 0


def cmd_dry_run(config: dict) -> int:
    html = DRY_RUN_FIXTURE.read_text(encoding="utf-8")
    cards = parse_cards(html)
    records = build_records(cards, config, "fixture", "1970-01-01T00:00:00+00:00",
                            "fixture", set(), int(config["compliance"]["max_skus_per_run"]))
    print(f"Dry run on {DRY_RUN_FIXTURE.name}: {len(cards)} cards parsed, {len(records)} kept")
    print_records(records)
    return 0 if records else 1


def cmd_capture(config: dict) -> int:
    query = config["search_queries"][0]
    html = fetch_html(config, query)
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out = FIXTURES_DIR / f"supervalu_search_{stamp}.html"
    out.write_text(html, encoding="utf-8")
    print(f"Saved {len(parse_cards(html))} cards for query {query!r} to {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--export-only", action="store_true")
    mode.add_argument("--capture-fixture", action="store_true")
    args = ap.parse_args(argv)
    config = load_config()

    if args.dry_run:
        return cmd_dry_run(config)
    if args.export_only:
        exp = export_cube_json(config)
        print(f"Cube rebuilt: {exp['path']} ({exp['latest_rows']} active SKUs)")
        return 0
    if args.capture_fixture:
        return cmd_capture(config)
    return cmd_live(config)


if __name__ == "__main__":
    sys.exit(main())
