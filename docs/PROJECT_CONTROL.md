# FMCG Price Intelligence — Project Control

> Single source of truth for scope, decisions, milestones and gates. A decision is real once it
> appears in the Decision log (§4). Nothing is deleted: superseded entries are marked and kept.

| Field | Value |
|---|---|
| Document version | `v1.5.0` |
| Owner | Gadiel Guadarrama |
| Last updated | 2026-10-06 |
| Current phase | F4b shipped → F4c EDLP vs high-low from ~25 Oct |
| Next external date | Finance Bill 2026 (confirms Budget tax measures); Budget watch window closes 19 Oct 2026 |

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
| D-009 | Master-brand chrome, product-specific surface: every Gadiel Analytics product shares the brand bar, monogram, byline and share card; each keeps its own content palette | Consistent ownership signal without re-skinning each product |
| D-010 | Licence: all rights reserved, source available for viewing and evaluation (`COPYRIGHT.md`) | Flagship commercial IP; consistent with Matchday Intelligence |
| D-011 | Tabbed information architecture with deep links; one topic per tab | Scales with F2–F4 without an ever-longer page; shareable links to specific evidence |
| D-012 | Consulting-report grammar: action titles computed from data with guards, numbered exhibits, source lines, one highlight colour | Premium consulting standard; findings change with evidence and never overstate it |
| D-013 | Competition = each hero brand against its direct rival, pack for pack, on price paid today; energy is an adjacent category | Answers the commercial question instead of listing the shelf |
| D-014 | Events are studied descriptively: fixed 14-day windows, regular prices, changes under €0.02/L ignored, never attributed | Keeps the Budget read honest and reproducible; ties to the claim-strength guardrail |
| D-015 | A before/after comparison excludes any pack whose offer, regular price or range changed inside either window, and says which | Prevents attributing a promotion or range change to an event |

## 3. Roadmap and gates

| Phase | Scope | Gate (evidence required) | Status |
|---|---|---|---|
| F0 Hardening | Delisted-SKU exclusion, promotion model, regular-price inference, levy benchmark, Diet Coke collection, idempotent ingest, quality gate, tests, docs | Spread reproducible from committed history; tests green in CI | **Done** — first CI run 2026-09-27: gate passed, 34 SKUs, 11 Diet Coke |
| F0.1 Brand | Brand bar, byline, share card, favicon, ownership, tabs, licence | Links render a branded preview on LinkedIn and X | **Done** |
| F1 Price truth review | Validate regular-price inference against 2–4 weeks of new data; decide handling of perma-promoted SKUs | Inference disagreements < 5% of promo SKU-days on manual check | Next |
| F2 Competitive scope | Pepsi / Pepsi Max, 7UP, Club, Fanta, Sprite, SuperValu own-label cola, Monster, Red Bull; brand → manufacturer map; sugar band per product | ≥ 80 active SKUs; full/zero pairs for ≥ 3 brands | **Shipped** — gate checked on first live run |
| F3 Redesign | Consulting-report dashboard, head-to-head competition | Nine exhibits render on desktop and phone with no errors | **Done** |
| F3b Second retailer | Retailer adapter interface; 1-hour feasibility spike per candidate before committing | Two retailers with matched SKUs on ≥ 10 formats | Planned |
| F4 Advanced sections | Assortment tracker (listings/delistings), pack-change detection, deposit-inclusive €/L (DRS €0.15/€0.25), 30-day reference-price context, reformulated brands as a quasi-control for the levy spread | Three quantified insights suitable for a case study | Planned |
| F5 AI layer | In-browser SQL (DuckDB-WASM) over the Parquet; weekly brief generated in CI and checked by a deterministic claim-strength guardrail | Brief contains no causal claim unsupported by the evidence rules | Planned |
| F6 Launch | Methodology page, case study, public post | Published | Planned |

## 4. Decision log

| ID | Date | Decision | Status |
|---|---|---|---|
| D-001 – D-008 | 2026-09-26 | Baseline adopted (see §2) | Active |
| D-009 | 2026-09-27 | Branding model (see §2) | Active |
| D-010, D-011 | 2026-09-27 | Licence; tabbed IA (see §2) | Active |
| D-012, D-013 | 2026-09-27 | Report grammar; head-to-head competition (see §2) | Active |
| D-014 | 2026-09-27 | Event-study rules (see §2) | Active |
| D-015 | 2026-10-06 | Confounder exclusion (see §2) | Active |

## 5. Open questions

| ID | Question | Resolves in |
|---|---|---|
| Q-001 | Does the SuperValu card price include the DRS deposit, or is it shown separately? | Next real fixture capture |
| Q-002 | ~~What brand label do Diet Coke cards carry?~~ **Resolved 2026-09-27: "Diet Coke".** | — |
| Q-003 | ~~Does Budget 2027 change the SSDT?~~ **6 Oct 2026: no change in the official summary**; confirm against the Finance Bill | Finance Bill |
| Q-004 | Which second retailer is reachable at human rate without anti-bot escalation? | F3 spike |
| Q-005 | ~~Repository licence?~~ **Resolved 2026-09-27: all rights reserved, source-available (D-010).** | — |
| Q-006 | Do the competitor brand labels and sugar terms hold on live cards? Check the run log's dropped-labels line | First run after F2 |

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
| v1.1.0 | 2026-09-27 | F0 gate passed; F0.1 branding; D-009; Q-002 resolved; Q-005 opened |
| v1.2.0 | 2026-09-27 | F2 shipped; D-010 licence; D-011 tabs; Q-005 resolved; Q-006 opened |
| v1.3.0 | 2026-09-27 | F2.1 hotfix and F3 redesign shipped; D-012, D-013 |
| v1.4.0 | 2026-09-27 | F4a Budget watch shipped; D-014; Q-003 procedure |
| v1.5.0 | 2026-10-06 | F4b shipped; D-015; Q-003 answered pending Finance Bill |
