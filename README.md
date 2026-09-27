# FMCG Price Intelligence — SuperValu Ireland · Coca-Cola CSD

> A zero-cost, low-maintenance **Revenue Growth Management (RGM)** analytics system that
> reads Coca-Cola carbonated soft-drink shelf prices from SuperValu Ireland daily, persists a
> versioned historical fact table, separates regular prices from promotions, and benchmarks the
> full-sugar premium against Ireland's **Sugar-Sweetened Drinks Tax**.

**Live dashboard:** https://gadiel-analytics.github.io/fmcg-price-intelligence/reports/dashboard.html
· **Author:** [@GadielAnalytics](https://github.com/Gadiel-Analytics)
· **Website:** https://gadielanalytics.com/
· **Contact:** hello@gadielanalytics.com

---

## Why this project

RGM rests on four levers: price setting, assortment and mix, promotion, and trade investment.
Three of them are visible on the shelf — which makes public shelf prices a legitimate, if partial,
lens on how a portfolio is priced. Ireland is a sharp test case: an inflationary grocery market,
an active promotional environment, and a Sugar-Sweetened Drinks Tax that splits the cola
portfolio into taxed (full-sugar) and untaxed (Zero, Diet) packs. Coca-Cola products on the island
of Ireland are bottled and distributed by Coca-Cola HBC Ireland & Northern Ireland.

This system reproduces, at hobby scale and zero cost, the kind of daily price-intelligence signal
that underpins those decisions — and frames the output in RGM language. Trade investment is not
observable from the shelf, and the project does not claim to measure it.

## What the data shows (SuperValu IE, 115 days to 26 Sep 2026)

Regular (non-promotional) shelf prices, like-for-like by pack size, pack count and container,
flavoured and caffeine-free variants excluded:

- **Full-sugar Coca-Cola carries a premium over Zero in every matched format: +4% (500 ml PET)
  to +24% (2 L PET), or €0.20–€0.91 per litre.**
- Against the levy on full-sugar drinks (**€0.30/L** incl. VAT), that premium ranges from
  **0.67× to 3.03×**; six of eight formats sit above 1×. The single can carries three times the
  levy; the 500 ml bottle and the 2 × 2 L multipack carry less than the levy.
- **The 2 L Zero Sugar bottle was on promotion on every one of 115 days** (multibuys, price cuts,
  value badges). Its regular price is a reference point shoppers rarely pay.
- **18 of 24 listed SKUs held a single price for the whole period**; price movement happens
  through promotions (19% of SKU-days), not list-price changes.

**How to read the levy ratio.** A ratio above 1× does not show that the tax is over-passed to
shoppers, and one below 1× does not show absorption: the premium also reflects pricing choices per
pack. The ratio is a benchmark, not a measured pass-through. The project states the strength of
its claims explicitly rather than implying causality the data cannot support.

## Architecture

```
GitHub Actions (daily cron) ── pytest (offline) ──┐
        │                                          │ gate
        ▼                                          ▼
  scraper.py  ──(curl_cffi + BeautifulSoup)──►  SuperValu IE public search results
        │
        ▼  quality gate (refuses runs below 50% of the 7-day median SKU count)
  datastore.ingest()  ──(DuckDB, idempotent upsert)──►  data/fmcg_prices.parquet
        │                                                   │
        │                        sql/01_observations.sql  obs → priced → active
        ▼                                                   ▼
  reports/cube.json  ──►  reports/dashboard.html  (D3)  ──►  GitHub Pages (public)
```

| Layer | Tool | Why |
|---|---|---|
| Orchestration | GitHub Actions | Free cron, open network egress, commit-back as audit trail |
| Ingestion | curl_cffi + BeautifulSoup | Browser-grade TLS fingerprint over lightweight parsing |
| Storage / OLAP | DuckDB + Parquet | In-process analytical SQL, zero server, git-versioned history |
| Modelling | Plain SQL views | Derivations applied retroactively to the full history; no framework overhead |
| Visualisation | D3 + GitHub Pages | Static, fast, fully controllable design |

### Pricing model

- **Raw layer** (`data/fmcg_prices.parquet`): one row per retailer × SKU × day; the latest scrape
  of a day wins. Re-running a day never duplicates history.
- **`obs`**: flags derived from the title (flavoured, caffeine-free) and the promotion badge parsed
  into a mechanic — `multibuy`, `price_cut`, `loyalty_price` (SuperValu Real Rewards) or `badge`.
- **`priced`**: on no-promotion and multibuy days the card shows the shelf price, so it is a clean
  observation of the regular price; on other promotion days the regular price is carried forward
  from the latest clean day (or back-filled from the next one). Effective price applies the
  multibuy per-unit price. Promotion depth = 1 − effective / regular.
- **`active`**: SKUs seen within 2 days of the latest run; delisted SKUs drop out of current views.

## A note on source selection (the anti-bot reality)

The original target was Tesco Ireland. During feasibility testing, Tesco returned **HTTP 403**
to automated requests — including with browser-grade TLS impersonation (`curl_cffi`) — from
both a residential connection and GitHub's runners. Defeating that reliably requires paid
residential proxies or a headless browser farm — both of which break this project's priorities of
zero cost and zero maintenance.

SuperValu Ireland (Musgrave Group) serves fully-rendered product cards to a Chrome-impersonated
request, returning real data at zero cost. The RGM analysis is identical regardless of source.
Choosing the accessible source over an arms race is the correct engineering call, and it is
documented here rather than hidden.

## Repository layout

```
config/catalog.yaml        # queries, brands, analysis and quality settings — edit here, not in code
scrapers/scraper.py        # fetch + parse → PriceRecord (pack-aware €/litre normalisation)
scrapers/datastore.py      # idempotent ingest + named cube queries
sql/01_observations.sql    # obs → priced → active views (promo parsing, regular-price inference)
run.py                     # entrypoint: live | --dry-run | --export-only | --capture-fixture
tests/                     # offline tests (parser, brand filter, ingest, pricing model)
reports/dashboard.html     # D3 dashboard (reads cube.json)
.github/workflows/         # daily cron, gated by tests
COMPLIANCE.md              # compliance-by-design statement
DEPLOYMENT.md              # operator runbook
CHANGELOG.md               # changes, including data and methodology corrections
docs/PROJECT_CONTROL.md    # scope, decisions, roadmap and gates
```

## Running locally

```bash
pip install -r requirements-dev.txt
python -m pytest -q          # offline tests
python run.py --dry-run      # parse the bundled fixture; no network, no writes
python run.py --export-only  # rebuild reports/cube.json from the committed history
```

## Compliance

Public, non-personal, factual price data only; human-rate access; honest User-Agent;
provenance logged. Full statement in [`COMPLIANCE.md`](COMPLIANCE.md). Not legal advice.

## Roadmap

- [x] M0 Compliance & feasibility
- [x] M1 Scraper core
- [x] M2 DuckDB data layer + like-for-like cube queries
- [x] M3 GitHub Actions orchestration
- [x] M4 D3 dashboard
- [x] M5 Deploy + accumulate daily history (continuous since 4 Jun 2026)
- [x] F0 Hardening: correct current prices, promotion model, levy benchmark, tests, quality gate
- [ ] F2 Competitive scope: Pepsi, 7UP, Club, Fanta, Sprite, own-label, energy
- [ ] F3 Second retailer
- [ ] F4 Advanced sections: assortment tracker, pack-change detection, deposit-inclusive prices
- [ ] F5 In-browser SQL over the Parquet history; weekly brief with claim-strength guardrails

Details and gates: [`docs/PROJECT_CONTROL.md`](docs/PROJECT_CONTROL.md).
