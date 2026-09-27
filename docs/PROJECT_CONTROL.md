# FMCG Price Intelligence — Project Control

> Single source of truth for scope, decisions, milestones and gates. A decision is real once it
> appears in the Decision log (§4). Nothing is deleted: superseded entries are marked and kept.

| Field | Value |
|---|---|
| Document version | `v1.0.0` |
| Owner | Gadiel Guadarrama |
| Last updated | 2026-09-26 |
| Current phase | F0 complete → F1 promotion depth review, F2 competitive scope |
| Next external date | Irish Budget 2027, 6 Oct 2026 (possible SSDT change → event study) |

Update protocol: amend the relevant register, bump the version (patch = status/typo, minor = new
decision/gate result, major = repositioning), add a line to §8, commit as
`docs(control): <what changed> [D-###]`.

---

## 1. Product definition

**One sentence.** A daily, zero-cost read of Irish beverage shelf prices that separates regular
prices from promotions and benchmarks price-pack architecture against the sugar levy — framed in
Revenue Growth Management terms, with the strength of every claim stated explicitly.

| Field | Value |
|---|---|
| Primary audience | RGM, pricing and category teams at beverage manufacturers and retailers; hiring managers and consulting leads evaluating the author's work |
| Job to be done | "Show me how this portfolio is priced and promoted at the shelf, like-for-like, and what the tax does and does not explain." |
| RGM levers covered | Price setting · assortment and mix · promotion. **Not** trade investment (not observable at the shelf). |
| Differentiator | Regular-vs-promotional separation, levy benchmark with explicit claim limits, full daily history in git |

## 2. Locked decisions

| ID | Decision | Rationale |
|---|---|---|
| D-001 | Zero recurring cost; no paid proxies, no headless-browser farm | Portfolio longevity; documented Tesco 403 finding |
| D-002 | SuperValu IE as the primary source | Accessible at human rate; same analysis regardless of source |
| D-003 | Raw layer stores what the card shows; all derivations live in SQL views | Rule changes apply to the whole history; no backfills |
| D-004 | One row per retailer × SKU × day; latest scrape of the day wins | Idempotent re-runs; clean history |
| D-005 | The levy ratio is a benchmark, never presented as measured pass-through | The premium also reflects commercial choices; avoid causal overreach |
| D-006 | Beverages only until F4 | €/litre normalisation, levy and deposit logic are category-specific; depth over breadth |
| D-007 | Reference-price (30-day) analysis, if built, is presented as context, never as non-compliance findings about a named retailer | A promotion badge is not necessarily a price-reduction announcement; legal exposure |
| D-008 | No dbt, managed database or orchestration framework | ~10 views; SQL files + pytest cover the need |

## 3. Roadmap and gates

| Phase | Scope | Gate (evidence required) | Status |
|---|---|---|---|
| F0 Hardening | Delisted-SKU exclusion, promotion model, regular-price inference, levy benchmark, Diet Coke collection, idempotent ingest, quality gate, tests, docs | Spread reproducible from committed history; tests green in CI | **Done** (pending first CI run) |
| F1 Price truth review | Validate regular-price inference against 2–4 weeks of new data; decide handling of perma-promoted SKUs | Inference disagreements < 5% of promo SKU-days on manual check | Next |
| F2 Competitive scope | Pepsi / Pepsi Max, 7UP, Club, Fanta, Sprite, SuperValu own-label cola, Monster, Red Bull, Lucozade; brand → manufacturer map; sugar band per product | ≥ 80 active SKUs; full/zero pairs for ≥ 3 brands | Planned |
| F3 Second retailer | Retailer adapter interface; 1-hour feasibility spike per candidate before committing | Two retailers with matched SKUs on ≥ 10 formats | Planned |
| F4 Advanced sections | Assortment tracker (listings/delistings), pack-change detection, deposit-inclusive €/L (DRS €0.15/€0.25), 30-day reference-price context, reformulated brands as a quasi-control for the levy spread | Three quantified insights suitable for a case study | Planned |
| F5 AI layer | In-browser SQL (DuckDB-WASM) over the Parquet; weekly brief generated in CI and checked by a deterministic claim-strength guardrail | Brief contains no causal claim unsupported by the evidence rules | Planned |
| F6 Launch | Methodology page, case study, public post | Published | Planned |

## 4. Decision log

| ID | Date | Decision | Status |
|---|---|---|---|
| D-001 – D-008 | 2026-09-26 | Baseline adopted (see §2) | Active |

## 5. Open questions

| ID | Question | Resolves in |
|---|---|---|
| Q-001 | Does the SuperValu card price include the DRS deposit, or is it shown separately? | Next real fixture capture |
| Q-002 | What brand label do Diet Coke cards carry? (filter now matches brand or title) | First run after F0 |
| Q-003 | Does Budget 2027 change SSDT rates or thresholds? | 6 Oct 2026 |
| Q-004 | Which second retailer is reachable at human rate without anti-bot escalation? | F3 spike |

## 6. Risks

| ID | Risk | Mitigation |
|---|---|---|
| R-001 | SuperValu markup change breaks the parser | Quality gate blocks ingestion; failing CI emails the owner; `--capture-fixture` for diagnosis |
| R-002 | Regular-price inference wrong for perma-promoted SKUs | Flag `regular_is_inferred`; F1 manual review; dashboard note |
| R-003 | Misreading the levy ratio as pass-through | D-005; explicit note in dashboard and README |
| R-004 | Repository growth from daily rewrites (Parquet ~17 KB, cube.json ~340 KB) | Acceptable at current scope; revisit at F2/F3 scale (monthly Parquet partitions, slimmer cube) |

## 7. Kill / pivot criteria

- SuperValu blocks human-rate access for 7 consecutive days → pause collection, keep history, reassess source.
- F3 spikes find no second accessible retailer → stay single-retailer, deepen F2/F4.

## 8. Changelog

| Version | Date | Change |
|---|---|---|
| v1.0.0 | 2026-09-26 | Baseline: product definition, D-001–D-008, roadmap F0–F6 |
