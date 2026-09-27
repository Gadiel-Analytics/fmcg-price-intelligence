# Changelog

## F2.1 — Competition hotfix (2026-09-27)

- **Retailer volume typo:** "Fanta Crimson Cherry Bottle (1.75 ml)" produced €1,805.56 per litre.
  Stated units below 50 ml are now read as litres (flag `volume_corrected`), in the scraper and
  retroactively in SQL.
- **Cola flavour exclusion extended** (cream soda, strawberry, peach, pink, berry): Pepsi Cream Soda
  and Strawberries 'N' Cream no longer enter the like-for-like cola comparison.
- **Competition index now uses the price paid today.** Most competitor SKUs were on a Rewards or
  price-cut promotion on their first day, so their regular price is not yet observable and the
  regular-price index was nearly empty. The index now compares prices after promotions, with
  Rewards prices marked; the regular index is kept in the cube for when regular prices appear.
- Overview finding rewritten on the same basis ("cheaper on N of M matched packs").

## F0.1 + F2 — Brand, navigation and competition (2026-09-27)

### Competition (F2)
- Twelve search queries now cover Coca-Cola, Pepsi, SuperValu own-label cola, Sprite, 7UP, Fanta,
  Club, Red Bull and Monster. Brands carry family, owner and segment in `config/catalog.yaml`,
  mapped in SQL so changes apply retroactively.
- Per-brand sugar terms (e.g. Pepsi Max, 7UP Free, Red Bull Sugarfree, Monster Ultra count as
  no-sugar); "caffeine free" and "zero caffeine" no longer affect sugar classification.
- Guards: cards without a stated volume are skipped (e.g. biscuits sharing a brand word);
  own-label entries must mention cola; the run log lists brand labels the filter dropped.
- New cube tables: `competition_index` (like-for-like €/L index against each segment's reference
  brand) and `brand_summary` (coverage, price range, promotion intensity, full-sugar premium over
  the brand's own no-sugar range). Cube schema v3; the dashboard still reads v2 files.
- The sugar-tax spread, levy ratio, Coca-Cola trend and price-architecture views stay Coca-Cola only.
- Per-run SKU cap raised from 60 to 200.

### Pricing model
- A SKU never observed at a clean (non-promotional) price now has an unknown regular price and
  promotion depth, instead of a regular price equal to its promotional price (which reported 0%
  cuts for permanently promoted SKUs). No Coca-Cola figure changes: every Coca-Cola SKU has clean
  observations.

### Dashboard
- Seven tabs replace the single long page: Overview, Sugar tax, Price architecture, Promotions,
  Trends, Competition, Methodology. Keyboard navigation (arrow keys, Home, End), deep links
  (`#promotions`), and a print layout that includes every tab.
- Overview: KPIs plus findings recomputed on every run, each linked to its evidence.
- Promotions: brand filter; SKUs with under 14 days of history are held back and counted.
- Sugar tax: Diet Coke column and a Diet/Zero price-parity note.
- Methodology tab: collection, pricing model, what the numbers do and do not say, ownership.

### Brand and ownership
- Gadiel Analytics brand bar (bordered monogram on the navy bar, links to Work, Consulting, About,
  Source), author byline, LinkedIn link, copyright line.
- Share metadata (Open Graph, X cards, canonical, theme colour), branded 1200 × 630 share image,
  favicon.
- **Licence:** `COPYRIGHT.md` — all rights reserved; source available for viewing and evaluation,
  consistent with the other flagship Gadiel Analytics products.

### Data notes
- First F0 run: 11 Diet Coke SKUs collected; SuperValu labels them "Diet Coke" (Q-002). Quality
  gate passed; 4 Jun duplicates removed (2,911 rows).

## F0 — Hardening (2026-09-26)

### Data corrections
- **Current-price views now exclude delisted SKUs.** "Latest" previously returned the last
  observation of every SKU ever seen, so six delisted SKUs (e.g. 18-can packs last seen in
  August, a 500 ml can last seen on 12 Jun) fed the Sugar-Tax spread. Two of the ten published
  spread rows came from delisted SKUs, and the 2 × 2 L Zero price mixed in a SKU last seen on
  6 Jun (published +13.3%; correct +18.2%).
- **Regular and promotional prices are now separated.** The card price is a promotional price on
  price-cut and loyalty-price days, so the previous spread mixed promotions with the tax effect.
  The spread now uses regular prices; the promotion-adjusted spread is shown alongside.
- **The June headline was a promotion artefact.** The first pull showed the 2 L full-sugar and
  Zero bottles at the same price; both were on promotion that day. At regular prices the 2 L
  full-sugar bottle is 23.5% dearer per litre.
- **Diet Coke was never collected.** The brand filter kept only cards labelled "Coca-Cola";
  Diet Coke cards carry their own brand label. Collection starts with the next run; no history
  can be recovered.
- **Duplicate rows removed.** Four runs on 4 Jun 2026 stored four copies of that day. Ingest is
  now idempotent (latest scrape per SKU per day wins); the next run rewrites the history without
  the 84 duplicate rows. The originals remain in git history.
- **Caffeine-free variants** are now excluded from the core spread, alongside flavours.

### Fixes
- Trend chart: dates were multiplied by 1000 after already being in milliseconds, placing the
  x-axis tens of thousands of years in the future. Dates are now ISO strings.
- Trend chart rebuilt as one panel per matched format in €/litre (previously ~20 overlapping
  series on a €1.55–€19 axis).
- "Last updated" read the first row of an arbitrarily sorted table; it now reports the latest run.
- README: the Irish bottler is Coca-Cola HBC Ireland & Northern Ireland, not CCEP.

### Added
- Promotion model in SQL (`sql/01_observations.sql`): mechanic, loyalty flag, multibuy
  per-unit price, regular-price inference, promotion depth. Applied to the full history.
- Levy benchmark: spread ÷ €0.30/L (SSDT top band incl. VAT), configurable in `catalog.yaml`.
- Promotions section in the dashboard.
- Quality gate: a run below 50% of the trailing 7-day median SKU count is not ingested.
- Per-run SKU cap enforced across all queries (previously per query).
- Originating search query recorded on every row.
- `run.py --dry-run | --export-only | --capture-fixture`.
- Offline test suite (17 tests); the daily workflow runs it before scraping.

### Removed
- Unused Tesco fixture and `httpx` dependency; Tesco-era instructions in `DEPLOYMENT.md`.
