# FMCG Price Intelligence — SuperValu Ireland · Coca-Cola CSD

> A zero-cost, low-maintenance **Revenue Growth Management (RGM)** analytics system that
> reads Coca-Cola carbonated soft-drink shelf prices from SuperValu Ireland daily, persists a
> versioned historical fact table, and surfaces the **Sugar-Tax spread** and **promotional
> depth** — the signals RGM teams use to balance premiumisation and affordability.

**Live dashboard:** _(GitHub Pages URL after deploy)_ · **Author:** [@GadielAnalytics](https://github.com/Gadx1)

---

## Why this project

Coca-Cola Europacific Partners (CCEP) frames its investor narrative around revenue per
unit case and RGM — data-driven price-pack architecture, promotion optimisation, and the
balance of premiumisation vs affordability. Ireland is a sharp test case: an active
supermarket price war and a Sugar-Sweetened Drinks Tax that splits the cola portfolio into
taxed (full-sugar) and untaxed (zero/diet) packs.

This system reproduces, at hobby scale and zero cost, the kind of daily price-intelligence
signal that underpins those decisions — and frames the output in RGM language.

## The signature insight: Sugar-Tax spread

Normalised unit price (€/litre) of full-sugar vs Zero, matched like-for-like by pack size,
container and pack count, with flavoured variants (Cherry/Vanilla) excluded so the core cola
is compared cleanly. A positive spread is the visible pass-through of Ireland's sugar levy
onto full-sugar price-packs — exactly what an RGM analyst watches.

First live pull (SuperValu IE, June 2026) showed full-sugar Coca-Cola running **13–20%
dearer per litre than Zero across most formats — except the single 2 L bottle, where the two
price-match exactly** (consistent with the 2 L as a traffic-driving hero pack). See
`datastore.sugar_tax_spread()`.

## Architecture

```
GitHub Actions (daily cron)
        │
        ▼
  scraper.py  ──(curl_cffi + BeautifulSoup)──►  SuperValu IE public search results
        │
        ▼
  datastore.py  ──(DuckDB, in-process OLAP)──►  data/fmcg_prices.parquet  (versioned data lake)
        │                                              │
        │                                       cube queries
        ▼                                              ▼
  reports/cube.json  ──►  reports/dashboard.html  (D3 trends + Sugar-Tax spread)
                                   │
                                   ▼
                            GitHub Pages (public)
```

Four core tools, deliberately. The design avoids over-engineering: no headless browser,
no managed database, no paid services.

| Layer | Tool | Why |
|---|---|---|
| Orchestration | GitHub Actions | Free cron, open network egress, commit-back as audit trail |
| Ingestion | curl_cffi + BeautifulSoup | TLS-fingerprint stealth (browser-grade) over lightweight parsing |
| Storage / OLAP | DuckDB + Parquet | In-process analytical SQL, zero server, git-versioned history |
| Visualization | D3 + GitHub Pages | Static, fast, fully controllable design |

## A note on source selection (the anti-bot reality)

The original target was Tesco Ireland. During feasibility testing, Tesco returned **HTTP 403**
to automated requests — including with browser-grade TLS impersonation (`curl_cffi`) — from
both a residential connection and GitHub's runners. Tesco fronts its store with Akamai-class
bot detection that weights more than the TLS fingerprint (IP reputation, behavioural signals,
JS challenges). Defeating that reliably requires paid residential proxies or a headless
browser farm — both of which break this project's stated priorities of zero cost and zero
maintenance.

SuperValu Ireland (Musgrave Group, ~19% market share) serves fully-rendered product cards to
a Chrome-impersonated request, returning real data at zero cost. The RGM analysis — the
Sugar-Tax spread, the cube, the dashboard — is identical regardless of source. Choosing the
accessible source over an arms race is the correct engineering call, and it is documented
here rather than hidden.

## Repository layout

```
config/catalog.yaml        # search queries + brand filter — edit here, never touch code
scrapers/scraper.py        # fetch + parse → PriceRecord (pack-aware €/litre normalisation)
scrapers/datastore.py      # DuckDB ingest + cube queries
run.py                     # daily entrypoint (scrape → ingest → export)
reports/dashboard.html     # D3 dashboard (reads cube.json)
.github/workflows/         # daily cron
COMPLIANCE.md              # compliance-by-design statement
```

## Compliance

Public, non-personal, factual price data only; human-rate access; honest User-Agent;
provenance logged. Full statement in [`COMPLIANCE.md`](COMPLIANCE.md). Not legal advice.

## Roadmap

- [x] M0 Compliance & feasibility
- [x] M1 Scraper core (validated on live SuperValu data — 28 SKUs)
- [x] M2 DuckDB data layer + like-for-like cube queries
- [x] M3 GitHub Actions orchestration
- [x] M4 D3 dashboard
- [ ] M5 Deploy + accumulate daily history (see DEPLOYMENT.md)
- [ ] Future: promo-frequency analysis; cross-retailer comparison; text-to-SQL over DuckDB
