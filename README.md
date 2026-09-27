# FMCG Price Intelligence — SuperValu Ireland · Coca-Cola and competitors

**A [Gadiel Analytics](https://gadielanalytics.com/) product** — designed, built and maintained by
**Gadiel Guadarrama, M.Sc.**, Decision-System Architect and author of
[*The Analytics System*](https://theanalyticssystem.com/). Part of the
[Gadiel Analytics portfolio](https://gadielanalytics.com/work/) (Commercial Analytics & RGM).

> A zero-cost, low-maintenance **Revenue Growth Management (RGM)** analytics system that
> reads soft-drink and energy-drink shelf prices from SuperValu Ireland daily, persists a
> versioned historical fact table, separates regular prices from promotions, benchmarks the
> full-sugar Coca-Cola premium against Ireland's **Sugar-Sweetened Drinks Tax**, and compares
> Coca-Cola with its competitors like-for-like per litre.

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

## What the data shows (SuperValu IE, 27 Sep 2026)

Coca-Cola history runs from 4 Jun 2026 (116 days); competitor history from 27 Sep 2026, so the
competitive read is a first snapshot. The dashboard recomputes every finding daily.

- **Coca-Cola charges a full-sugar premium on every pack** (+4% to +24% per litre over Zero Sugar,
  regular prices). Against the levy on full-sugar drinks (**€0.30/L** incl. VAT) the premium ranges
  from **0.67× to 3.03×**; six of eight packs sit above the levy.
- **Pepsi largely does not:** Pepsi and Pepsi Max cost the same in 6 of 7 pack sizes.
- **Pepsi is cheaper than Coca-Cola on 8 of 9 matched packs** at today's prices; only the promoted
  Coca-Cola Zero Sugar 2 L bottle (3 for €6.75) puts Coca-Cola ahead. Five of the nine Pepsi prices
  require a SuperValu Real Rewards card.
- **Coca-Cola promotes the 2 L bottle almost permanently:** four 2 L SKUs were on promotion on at
  least 90% of days; shoppers could buy the 2 L Zero Sugar below its regular price on every day.
- **Diet Coke is priced identically to Zero Sugar** in all eight matched packs.
- **One ladder inversion:** the 500 ml Zero Sugar can costs 8.5% more per litre than the 330 ml can.

**How to read the levy ratio.** A ratio above 1× does not show that the tax is over-passed to
shoppers, and one below 1× does not show absorption: the premium also reflects pricing choices per
pack. It is a benchmark, not a measured pass-through.

## Coverage

| Segment | Brands (reference brand first) |
|---|---|
| Cola | Coca-Cola (incl. Zero Sugar and Diet Coke), Pepsi (incl. Pepsi Max), SuperValu own-label cola |
| Lemon-lime | Sprite, 7UP |
| Orange & fruit | Fanta, Club |
| Energy | Red Bull, Monster |

Coca-Cola history runs from 4 Jun 2026; competitor collection started with the F2 release
(27 Sep 2026). Brands, owners, segments and per-brand sugar terms live in `config/catalog.yaml`.

## Dashboard

A consulting-style report in six sections, each addressable by link (e.g. `dashboard.html#competition`):

| Section | Exhibits |
|---|---|
| **Summary** | Headline, four KPIs and key messages, all computed from the day's data |
| **Sugar tax** | 1 · Full-sugar premium against the levy, pack by pack (dumbbell with levy band) |
| **Pack architecture** | 2 · Price-per-litre ladder by pack volume, Coca-Cola against Pepsi · 3 · Ladder inversions |
| **Promotions** | 4 · Promotion calendar (SKU × day, by mechanic) · 5 · 2 L price paid against regular price |
| **Competition** | 6 · Coca-Cola against Pepsi, pack for pack · 7 · Full-sugar premium by brand · 8 · Sprite–7UP and Fanta–Club · 9 · Energy (adjacent category) |
| **Methodology** | Collection, pricing model, limits, compliance, ownership |

Every exhibit has an action title stating its finding, a source line, and a data table where the
chart carries exact values. Titles are generated from the data with explicit guards, so they
change with the evidence and never overstate it.

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
scrapers/datastore.py      # idempotent ingest, brand map, named cube queries (incl. competition)
sql/01_observations.sql    # obs → priced → active views (promo parsing, regular-price inference)
run.py                     # entrypoint: live | --dry-run | --export-only | --capture-fixture
tests/                     # offline tests (parser, brand filter, ingest, pricing model)
reports/dashboard.html     # D3 dashboard (reads cube.json)
.github/workflows/         # daily cron, gated by tests
COMPLIANCE.md              # compliance-by-design statement
COPYRIGHT.md               # all rights reserved; source available for viewing and evaluation
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

## Author and ownership

© 2026 Gadiel Guadarrama · Gadiel Analytics. Designed, built and maintained by Gadiel Guadarrama.
For pricing, RGM and decision-system advisory: hello@gadielanalytics.com ·
[LinkedIn](https://www.linkedin.com/company/gadielanalytics) · [X @gadielAnalytics](https://x.com/gadielanalytics).

This repository is public so the work can be read and evaluated, not so it can be reused. No
license is granted to copy, modify, distribute or sell the source code or substantial portions of
it without prior written permission. See [COPYRIGHT.md](COPYRIGHT.md).

Not affiliated with SuperValu, Musgrave Group or any brand owner shown. Brand and retailer names are
used descriptively to identify the products and prices observed.

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
- [x] F2 Competitive scope: Pepsi, Sprite, 7UP, Fanta, Club, Red Bull, Monster
- [x] F3 Consulting-style redesign: six sections, nine exhibits, head-to-head competition
- [ ] F3 Second retailer
- [ ] F4 Advanced analytics: price-change feed, assortment tracker, EDLP vs high-low, Budget event annotation, deposit-inclusive prices
- [ ] F5 In-browser SQL over the Parquet history; weekly brief with claim-strength guardrails

Details and gates: [`docs/PROJECT_CONTROL.md`](docs/PROJECT_CONTROL.md).
