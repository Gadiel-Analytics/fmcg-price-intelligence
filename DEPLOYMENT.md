# Operator runbook

The pipeline is deployed and running daily. This runbook covers the routine operations.

Repository: `https://github.com/Gadiel-Analytics/fmcg-price-intelligence`
Case study: `https://gadiel-analytics.github.io/fmcg-price-intelligence/`
Dashboard: `https://gadiel-analytics.github.io/fmcg-price-intelligence/reports/dashboard.html`
(after the custom domain switch: `https://fmcg.gadielanalytics.com/` and `/reports/dashboard.html`)

---

## Daily run (automatic)

`.github/workflows/daily-scrape.yml` runs at 08:00 UTC (GitHub may start scheduled jobs later
than that). Steps: offline tests → live scrape → quality gate → idempotent ingest → cube export →
commit of `data/`, `reports/` (cube and generated dashboard), `index.html`, `sitemap.xml` and `robots.txt`.

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
python run.py --export-only  # rebuild the cube and all pages from data/fmcg_prices.parquet
python run.py --capture-fixture   # save one live search page to scrapers/fixtures/
python run.py                # full live run (writes data/, the cube and the pages)
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
- **Event outcome:** once known, add `outcome` (one sentence), `outcome_source` (URL) and
  `levy_changed` (true/false). The exhibit shows it as "Announced" and adapts its title.
- **Levy rate change:** add a line to `analysis.levy_schedule` with the date it takes effect and
  the new rate per litre incl. VAT (ex-VAT rate per hectolitre ÷ 100 × 1.23). Earlier dates keep
  the old rate.

## Editing the pages

Edit the templates in `site/` (`site/dashboard.html`, `site/index.html`), never the generated
`reports/dashboard.html` or `index.html`: those are rewritten on every run. Wording of findings
lives in `scrapers/narrative.py`; run `python -m pytest -q` after changing it (one test rejects
causal language). `python run.py --export-only` rebuilds everything locally.

## Custom domain (fmcg.gadielanalytics.com)

Order matters: verify first, so nobody else can claim the subdomain, and switch `base_url` last,
so canonical URLs never point at an address that does not answer yet.

1. **Verify the domain for the organisation.** GitHub → organisation **Gadiel-Analytics** →
   Settings → Pages → *Add a domain* → `gadielanalytics.com`. GitHub shows a TXT record
   (named like `_github-pages-challenge-Gadiel-Analytics`; copy name and value exactly as shown).
   Add it at your DNS provider, then press *Verify*. This protects every subdomain of gadielanalytics.com from takeover.
2. **Point the subdomain.** At your DNS provider add a `CNAME` record: name `fmcg`, value
   `gadiel-analytics.github.io` (no repository name, no `https://`). Leave the TTL at its default.
   **On Cloudflare** (where gadielanalytics.com is served), set *Proxy status* to **DNS only**
   (grey cloud): GitHub can only issue the HTTPS certificate when it answers the subdomain itself.
3. **Attach it to the repository.** Repository → Settings → Pages → *Custom domain* →
   `fmcg.gadielanalytics.com` → Save. GitHub commits a `CNAME` file and checks DNS; wait for the
   green "DNS check successful" (minutes to an hour).
4. **Enforce HTTPS** on the same page once the certificate is issued (up to 24 hours; the box is
   greyed out until then).
5. **Switch the canonical address.** Set `site.base_url` in `config/catalog.yaml` to
   `https://fmcg.gadielanalytics.com`, update the two URLs at the top of `README.md` and
   `url:` in `CITATION.cff`, commit, push, and run the workflow. Old `github.io` links redirect
   automatically.

To roll back: remove the custom domain in Settings → Pages and restore `site.base_url`.

## Search engines

- **Google Search Console** → *Add property* → **Domain** → `gadielanalytics.com` → verify with
  the TXT record it shows (one property covers the main site and every subdomain). Then
  *Sitemaps* → submit `https://fmcg.gadielanalytics.com/sitemap.xml` (or the github.io address
  before the switch), and *URL inspection* → *Request indexing* for the case study and dashboard.
- **Bing Webmaster Tools** → *Import from Google Search Console*. Bing also feeds several
  AI answer engines.
- Check progress under *Performance* → *Queries* for "gadiel guadarrama", "gadiel analytics" and
  "the analytics system". Expect weeks, not days.

## Repository settings that help discovery

Repository → ⚙ next to *About*:

- **Description:** `Daily Coca-Cola vs Pepsi shelf-price intelligence for Ireland: price-pack
  architecture, promotions and the sugar levy. By Gadiel Guadarrama, Gadiel Analytics.`
- **Website:** the case-study URL.

On **gadielanalytics.com**, point the FMCG Price Intelligence card on the home and Work pages
at the case study (`https://fmcg.gadielanalytics.com/`) once the domain is live.
- **Topics:** `revenue-growth-management`, `pricing-analytics`, `price-intelligence`,
  `competitive-intelligence`, `price-pack-architecture`, `fmcg`, `cpg`, `data-science`,
  `analytics-engineering`, `decision-intelligence`, `duckdb`, `python`, `d3js`,
  `github-actions`, `ireland`, `sugar-tax`.

Settings → General → **Social preview** → upload `reports/og-image.png`.

With the GitHub CLI, the first two steps are:

```bash
gh repo edit Gadiel-Analytics/fmcg-price-intelligence \
  --description "Daily Coca-Cola vs Pepsi shelf-price intelligence for Ireland: price-pack architecture, promotions and the sugar levy. By Gadiel Guadarrama, Gadiel Analytics." \
  --homepage "https://gadiel-analytics.github.io/fmcg-price-intelligence/" \
  --add-topic revenue-growth-management,pricing-analytics,price-intelligence,competitive-intelligence,price-pack-architecture,fmcg,cpg,data-science,analytics-engineering,decision-intelligence,duckdb,python,d3js,github-actions,ireland,sugar-tax
```

**Releases** give each milestone a dated, indexable page:

```bash
gh release create v1.0.0 --title "v1.0.0 — Consulting-grade release" \
  --notes "Daily shelf-price intelligence for Coca-Cola and competitors in Ireland. See CHANGELOG.md for F0–F5."
```

**Commit identity:** GitHub → Settings → Emails: add and verify every address you commit with, so
every commit links to your profile.

## After changing the dashboard

GitHub Pages redeploys a minute or two after each push, and browsers cache `dashboard.html`.
Open the dashboard with a hard refresh (Cmd+Shift+R on macOS, Ctrl+F5 on Windows) before judging
a change; `cube.json` is always fetched fresh.

## GitHub Pages

Settings → Pages → Deploy from a branch → `main`, folder `/ (root)`. The case study is served at
the root (`index.html`) and the dashboard at `reports/dashboard.html`; `.nojekyll` serves files
as they are. Each daily commit updates the cube and the pages.
