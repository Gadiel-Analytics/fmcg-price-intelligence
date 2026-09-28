# Operator runbook

The pipeline is deployed and running daily. This runbook covers the routine operations.

Repository: `https://github.com/Gadiel-Analytics/fmcg-price-intelligence`
Dashboard: `https://gadiel-analytics.github.io/fmcg-price-intelligence/reports/dashboard.html`

---

## Daily run (automatic)

`.github/workflows/daily-scrape.yml` runs at 08:00 UTC (GitHub may start scheduled jobs later
than that). Steps: offline tests → live scrape → quality gate → idempotent ingest → cube export →
commit of `data/` and `reports/cube.json`.

A red run in the Actions tab means one of:

| Failing step | Meaning | Action |
|---|---|---|
| Run tests | A code change broke the parser or pricing model | Fix and push; no data was touched |
| Scrape … `QUALITY GATE FAILED` | SuperValu returned too few SKUs (layout change, outage, block) | Check the log for `FAILED query=` lines; run `--capture-fixture` locally and compare the markup |
| Commit updated data | Push race with a manual commit | Re-run the workflow |

GitHub emails the repository owner when a scheduled workflow fails.

## Manual run

Actions tab → **Daily Price Scrape** → **Run workflow**. Safe at any time: a same-day re-run
replaces that day's rows instead of duplicating them.

## Local commands

```bash
pip install -r requirements-dev.txt
python -m pytest -q          # offline tests
python run.py --dry-run      # parse the bundled fixture; no network, no writes
python run.py --export-only  # rebuild reports/cube.json from data/fmcg_prices.parquet
python run.py --capture-fixture   # save one live search page to scrapers/fixtures/
python run.py                # full live run (writes data/ and reports/cube.json)
```

## Refreshing the parser fixture

`scrapers/fixtures/supervalu_search_synthetic.html` reproduces the card structure the parser
relies on, but it is synthetic. To replace it with a real page:

1. `python run.py --capture-fixture` (writes `supervalu_search_YYYYMMDD.html`).
2. Point `DRY_RUN_FIXTURE` in `run.py` and `FIXTURE` in `tests/test_scraper.py` at the new file,
   and update the expected card counts in the test.
3. `python -m pytest -q`, then commit.

## Changing coverage

Edit `config/catalog.yaml` only:

- **New search term:** add to `search_queries`.
- **New brand:** add an entry under `brands` with `family`, `owner`, `segment` and `match` terms.
  Optional: `zero_terms` (title words meaning no sugar for that brand, e.g. `max` for Pepsi),
  `title_must_contain` (guard for broad labels such as own-label), `private_label: true`.
  The first brand listed in a segment is that segment's reference (index 100).
- **Tuning:** each run logs `Brand labels dropped by the brand filter: …`. A soft drink appearing
  there is a missing `match` term; add it and re-run.
- **Exclusions:** add title terms to `exclude_title_terms`.

Keep `compliance.max_skus_per_run` above the expected SKU count, or later queries are skipped.

## Events and levy changes

- **New event** (e.g. a levy's effective date): add an entry under `events` in
  `config/catalog.yaml` with `id`, `date`, `label`, `kind`, `detail`, `source`. The next run
  studies it automatically.
- **Levy rate change:** add a line to `analysis.levy_schedule` with the date it takes effect and
  the new rate per litre incl. VAT (ex-VAT rate per hectolitre ÷ 100 × 1.23). Earlier dates keep
  the old rate.

## After changing the dashboard

GitHub Pages redeploys a minute or two after each push, and browsers cache `dashboard.html`.
Open the dashboard with a hard refresh (Cmd+Shift+R on macOS, Ctrl+F5 on Windows) before judging
a change; `cube.json` is always fetched fresh.

## GitHub Pages

Settings → Pages → Deploy from a branch → `main`, folder `/ (root)`. The dashboard reads
`reports/cube.json` from the same folder, so each daily commit updates it.
