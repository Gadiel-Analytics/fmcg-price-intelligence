# Compliance & Data Provenance

> Compliance-by-design statement for the FMCG Price Intelligence PoC.
> Maintained as a first-class project artifact, not an afterthought.

## Scope of collection

| Dimension | Decision | Rationale |
|---|---|---|
| **Data type** | Public product attributes & shelf prices only | Factual, non-personal — lowest legal-risk category |
| **Personal data** | None collected | Keeps project fully outside GDPR subject-data scope |
| **Source** | `shop.supervalu.ie` public search-results pages | Publicly accessible without authentication |
| **Volume** | ~28 SKUs, once daily | Traffic indistinguishable from a single human shopper |
| **Purpose** | Price-monitoring / market research / portfolio demonstration | Recognised legitimate-interest use case |

## Operating principles

1. **Human-rate access** — sequential requests, randomised 3–7s delay, daily cadence only.
2. **Identify honestly** — descriptive User-Agent with project contact.
3. **No authentication bypass** — only publicly rendered, non-logged-in search results.
4. **Hard result cap** — `max_skus_per_run` ceiling enforced in code; the run refuses to exceed it.
5. **Provenance logged** — every row records source domain, search query, source URL and UTC timestamp.
6. **No redistribution of copyrighted descriptive text** — we retain numeric/price facts and
   structured attributes (pack, container, sugar class) for analysis, not the retailer's prose copy.

## On TLS impersonation

The scraper uses `curl_cffi` with a Chrome TLS/JA3 profile. This presents a browser-grade
network fingerprint so that public pages render as they would for a normal shopper. It is used
solely to access **publicly available, non-authenticated** content at human rate — not to evade
authentication, paywalls, or access controls, none of which are touched. No login, no account,
no protected route is ever requested.

## Source selection & access posture

Tesco Ireland (the initial candidate) returned HTTP 403 to automated access even with browser-grade
TLS impersonation, indicating Akamai-class bot detection. Rather than escalate to paid proxies or a
headless-browser arms race, the project moved to SuperValu Ireland, which serves public product data
to a standard browser-equivalent request. This is a deliberate choice to operate only where access is
straightforward and low-impact.

## Legal posture (informational, not legal advice)

Public, non-personal, factual price data collected at human rate for market-research purposes sits in
the lowest-risk band under both EU and US frameworks. This is a non-commercial, personal portfolio
project. This document is a good-faith compliance statement and does not constitute legal advice.

_Last reviewed: 2026-06-04_
