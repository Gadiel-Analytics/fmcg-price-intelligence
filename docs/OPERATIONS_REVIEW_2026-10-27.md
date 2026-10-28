# Operations and price-evidence review — 27 October 2026

## Incident and recovery

Daily Price Scrape failed seven consecutive times (21–27 October). The last success
on 20 October installed DuckDB 1.5.6; the first failure installed 2.0.0 through the
unbounded `duckdb>=1.0` dependency. All failures stopped before network collection:
`test_ingest_is_idempotent` called `fetchone()` on a relation returned by `duckdb.sql()`.
DuckDB 2.0 removed that relation method. Connection `execute(...).fetchone()` remains
valid and has deliberately not been replaced.

Evidence: [last success](https://github.com/Gadiel-Analytics/fmcg-price-intelligence/actions/runs/39427988010),
[first failure](https://github.com/Gadiel-Analytics/fmcg-price-intelligence/actions/runs/39606975982),
[last failed schedule](https://github.com/Gadiel-Analytics/fmcg-price-intelligence/actions/runs/40515177112).

The original 46 tests passed locally under Python 3.12 / DuckDB 1.5.6. The relation
calls were corrected to `fetchall()[0]`; DuckDB 2.0 is now the reviewed production
version. Runtime and test dependencies, including transitive dependencies, have
exact versions and SHA-256 hashes. Supported families live in `requirements*.in`;
CI installs the compiled `requirements*.txt` snapshots with `--require-hashes`.

The existing analytical values from the committed 20 October history matched
between 1.5.6 and 2.0 after normalizing unordered result lists. No historical prices
were changed to simulate missing collections.

## Additional parser defect found with live evidence

A live public search page on 27 October contained multiple promotion badges:
`Great Value` followed by `3 for €6`. The old parser kept only the first. The parser
now preserves all distinct badges, including Rewards eligibility. A minimal,
factual four-card fixture is retained in `scrapers/fixtures/supervalu_cards_20261027.html`;
product descriptions, images and page scripts are omitted.

The same cards explicitly show `+ €0.25 Deposit` for a 2 L bottle and
`+ €0.15 Deposit` for a 330 ml can. Actual displayed deposits are recorded from now
on; no deposit is guessed for earlier rows. The cube provides `deposit` and
`payable_incl_deposit`, while the analytical comparisons continue to exclude the
refundable deposit. The captured 2 L offer computes to €2.00 per unit, or €2.25
including the displayed deposit, conditional on taking the multibuy.

Earlier rows storing only a generic badge may hide an offer. These cannot be
reconstructed reliably. Generic-badge transitions are labelled **offer evidence**,
not a confirmed promotion change. Changes across an outage use first-observed dates;
an outage alone no longer creates mass relisting or delisting signals.

## Collection and data integrity

The local recovery collection returned **163 SKUs across eight observed brands**,
with **zero failed queries**. The history contains **7,030 observations** across
**140 observed collection days**, through **27 October 2026**. No duplicate SKU-day
keys or invalid price/volume/unmapped-brand observations were found by the release gate.
Six internal collection dates remain missing: **21–26 October**. The scheduled job
on 27 October failed, but the recovery collection observes 27 October; it is therefore
not a missing day in the recovered dataset.

The total-SKU gate remains in place, supplemented by mandatory Coca-Cola and Pepsi
coverage and a per-brand gate against the last seven observed collection dates.
Absent collection dates cannot reset the baseline. Brands never observed are not
invented: own-label remains configured but is not claimed among the eight observed brands.

## F1 price-truth review

The recovered local snapshot has 125 active SKUs with a clean observed regular-price
basis, 13 with an inferred regular price, and 25 whose regular price is unknown.
The dashboard now discloses these categories.

An internal bound check compares inferred prices with a subsequent clean observation
where available: 479 recent SKU-days were checkable; 29 differed by at least €0.01
(**6.1%**). This is a diagnostic, **not** an independent error rate: a true regular-price
change can legitimately produce the difference. The four-card live fixture confirms
current extraction behavior; it does not independently validate historical inference.

**F1's original manual gate is not passed.** The required independently checked
historical comparison (<5% disagreements) remains pending. Obtain dated price evidence
for a stratified sample, prioritizing these 29 bound disagreements and permanently
promoted SKUs. Unknown regular prices remain null; no 0% promotion-depth claim is
made for them. This limitation is exposed rather than silently signed off.

## F4c promotion-pattern readiness

The cube now measures actual coverage and computes descriptive promotion-pattern labels
only for SKUs observed on **all 28 days of the recent window**. Labels are
`low_promotion` (≤10% promotional days), `mixed`, or `promotion_led` (≥50%). They describe
observed promotion frequency, not the retailer's strategic intent, elasticity or ROI.

Competitor history contains **25 observed days in total** and **22 of the latest 28
calendar days**. **No active SKU qualifies** in the recovered local snapshot. EDLP/high-low
interpretation is withheld. With uninterrupted daily collection starting 27 October,
the first complete recent 28-day window is **23 November 2026**; each SKU must still
meet its own coverage gate. No recurring reminder or additional external automation
was created.

## Operational hardening

- Python 3.12 and Ubuntu 24.04 are explicit, replacing the moving Ubuntu label.
- Checkout 7.0.1, setup-python 7.1.0 and upload-artifact 7.0.2 use immutable commit pins
  verified against their official release refs. They use Node 24.
- Code validation runs on pushes and PRs, covering production DuckDB 2.0.0 and previous
  1.5.6 compatibility, parser fixtures, data modeling, guardrails and generated pages.
- The daily workflow also runs on relevant source changes to `main`; generated data
  commits do not retrigger it. Its cron is 08:17 UTC (best effort, not a start-time SLA).
- Query pacing also applies after HTTP/parsing failures. The workflow has a 15-minute
  timeout, concurrency serialization, and a retained collection log.
- Case study and dashboard display the latest observation date. A D3-independent
  freshness check warns after two days, even if no new page build occurs.
- A release gate checks strict JSON, history keys, price/volume/brand validity,
  generated placeholders, observation dates and XML.
- Production verification compares seven public HTTPS files byte-for-byte with the
  candidate publication, including HTML, cube, freshness JavaScript, sitemap, robots
  and favicon. A failed comparison makes the workflow red.

## Deployment evidence

**Publication is blocked by connection authorization, not by a failed candidate test.**
The GitHub connector rejected creation of `fix/recover-price-pipeline` in the
organization repository with HTTP 403, `Resource not accessible by integration`.
The connection lists an installation for personal account `gadx1` only; no
`Gadiel-Analytics` organization installation is exposed. The user's repository
metadata reports admin/push permissions, but these are not proof that the integration
can write. Local git also has no authenticated push credential.

No branch, PR, source commit, new Actions run or deployment was created remotely.
Production was checked through HTTPS and the browser: the dashboard still displays
**20 October 2026**. The last known hosted deployment is the successful 20 October
GitHub Pages run. The recovered 27 October dataset remains a local candidate.

Validation completed locally on Python 3.12: **54 pytest tests pass on DuckDB 2.0.0
and 54 on 1.5.6**, plus the Node freshness test. Both versions produce equal recovered
cube values after ignoring generation time and unordered result lists. The offline
release gate passes. JavaScript syntax checks pass. The new workflows have not run
on GitHub yet. A local browser binary could not be installed, so visual verification
of the changed candidate is also pending; the browser check covers the currently
published version only.

Authorize the GitHub connection for `Gadiel-Analytics/fmcg-price-intelligence` with
the ability to write contents and workflow files, or push the prepared commits using
an existing authorized local checkout. Do not disclose a token in chat. Then:

1. Push the prepared branch; open a PR and wait for both Code validation matrix jobs.
2. Merge the reviewed PR. The source-change trigger runs Daily Price Scrape on `main`.
3. Verify the live query count, per-brand gates, commit-back and Pages deployment.
4. Require the seven-file HTTPS comparison to pass and inspect all six dashboard tabs.

These are pending actions, not completed production evidence.

## Recommended next steps

1. Collect independent dated price evidence to close F1; do not equate the bound check
   with manual validation.
2. Let the 28-day window rebuild before interpreting promotion patterns; monitor the
   scheduled runs and per-brand coverage gates.
3. Review dependencies deliberately: recompile both lock snapshots together, run both
   CI versions, inspect release notes and merge only after validation. Do not run
   an unreviewed dependency upgrade inside the daily job.
4. After collection stability, consider the second-retailer feasibility spike and
   F6 guarded briefing. Keep the zero-recurring-cost constraint.
5. Independently confirm Finance Bill/SSDT event-source status before updating the
   policy claim. This recovery does not claim to have revalidated tax legislation,
   Search Console indexing or Cloudflare DNS account settings.
