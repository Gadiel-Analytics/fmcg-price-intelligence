# Deployment Guide — step by step

This is your operator manual. Follow top to bottom. Estimated time: 30–40 min.
Everything here is done by **you** (the repo owner); the code is already generated.

---

## Prerequisites

- A GitHub account (you have `Gadiel-Analytics`).
- Git installed locally, OR willingness to use the GitHub web UI for uploads.
- Python 3.12 locally (optional but recommended, to test before pushing).

---

## Step 1 — Create the repository

1. Go to https://github.com/new
2. Name: `fmcg-price-intel` (or your preference).
3. Visibility: **Public** (it's a portfolio piece).
4. Do **not** initialise with a README (we already have one).
5. Click **Create repository**.

---

## Step 2 — Push the project

**Option A — command line (recommended):**

```bash
cd fmcg-price-intel
git init
git add .
git commit -m "Initial commit: FMCG Price Intelligence PoC (M0–M4)"
git branch -M main
git remote add origin https://github.com/gadiel-analytics/fmcg-price-intel.git
git push -u origin main
```

**Option B — web UI:** on the empty repo page, click **uploading an existing file**,
drag the whole project folder in, commit.

---

## Step 3 — Test locally first (optional, ~2 min)

Confirms the parser works before relying on CI.

```bash
pip install -r requirements.txt
python run.py --dry-run        # parses the bundled fixture, no network
```

You should see the Coca-Cola 2L fields printed (base_price 4.15, etc.).

---

## Step 4 — First REAL run: validate Tesco is reachable from CI

This is the one unknown we could not test from the build sandbox (its network was
locked down). GitHub's runner has open egress, so this is where we confirm tesco.ie
responds 200 and isn't bot-blocking us.

1. In your repo, go to the **Actions** tab.
2. If prompted, click **"I understand my workflows, enable them"**.
3. Select **Daily Price Scrape** → **Run workflow** → **Run workflow** (manual trigger).
4. Watch the run. In the **"Run daily scrape"** step, look for:
   - `Scrape: N/N SKUs OK`  → success, prices fetched and committed.
   - `Scrape: 0/N SKUs OK` with `HTTP_403`  → Tesco is blocking the runner.

### If you get HTTP_403 (the contingency)

This means Tesco's anti-bot (Akamai/PerimeterX) blocks GitHub's datacenter IPs.
Don't panic — this is a known scenario and the fix is small:

- **Easiest:** sign up for a free-tier scraping proxy (ScraperAPI / Firecrawl /
  ScrapingBee all have free monthly credits). Add the API key as a repo secret
  (Settings → Secrets and variables → Actions → New repository secret), then route
  the request through it. Ping me and I'll generate the ~15-line `fetch_via_proxy`
  drop-in for `scraper.py`.
- **Alternative:** add the Zero/Diet SKU IDs and run less aggressively; sometimes
  datacenter blocking is intermittent.

The scraper already records status per SKU, so you'll see exactly what happened.

---

## Step 5 — Fill in the real SKU catalog

The catalog ships with 3 validated full-sugar IDs. To activate the **Sugar-Tax spread**,
you need Zero and Diet IDs.

1. On tesco.ie, search "coca cola zero" and "diet coke".
2. Open each product; the number at the end of the URL
   `…/products/315469891` is the `id`.
3. Edit `config/catalog.yaml`, uncomment the Zero/Diet placeholders, paste the IDs.
4. Commit & push. Next run picks them up automatically.

> Aim for matched packs (e.g. Original 2L **and** Zero 2L) so the spread query has
> like-for-like pairs to compare.

---

## Step 6 — Publish the dashboard on GitHub Pages

1. Repo → **Settings** → **Pages**.
2. Source: **Deploy from a branch**.
3. Branch: `main`, folder: `/ (root)`. Save.
4. Wait ~1 min. Your dashboard will be at:
   `https://gadiel-analytics.github.io/fmcg-price-intel/reports/dashboard.html`

The dashboard reads `reports/cube.json`, which the daily workflow refreshes. So once
Pages is on and the cron runs, the public dashboard updates itself with zero effort.

> Note: the relative `fetch("cube.json")` assumes the dashboard and cube.json sit in the
> same folder — they do (`reports/`). No change needed.

---

## Step 7 — Let it run

The cron fires daily at 08:00 UTC. Each run scrapes, appends to the Parquet history,
re-exports the cube, and commits. The git history of `data/fmcg_prices.parquet` becomes
your audit trail. Nothing else to maintain.

---

## Optional polish for the portfolio

- **Custom domain / cleaner URL:** GitHub Pages supports a custom domain in Settings.
- **Social share image:** add an `og:image` meta tag to the dashboard.
- **LinkedIn post angle:** lead with the Sugar-Tax spread number once you have real data
  ("Full-sugar Coca-Cola runs X% dearer per litre than Zero at Tesco IE — here's the
  automated system that tracks it daily"). That single quantified insight is what makes
  industry contacts stop scrolling.

---

## What to send me next

- The result of Step 4 (the `Scrape: N/N` line) — so we confirm ingestion or pivot to proxy.
- Once real data lands, I can build the M4+ extras: promo-frequency analysis, cross-retailer
  comparison (SuperValu), and a text-to-SQL query layer over DuckDB if you want the AI angle.
```
```
