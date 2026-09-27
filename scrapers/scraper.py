"""
FMCG Price Intelligence — Scraper Core · SuperValu Ireland (CSD & energy)
==========================================================
Fetches public search-results pages from SuperValu (shop.supervalu.ie) and
extracts RGM-relevant price signals from each product card, with normalised
price-per-litre so the Sugar-Tax spread compares like-for-like.

Why SuperValu over Tesco: Tesco fronts its store with Akamai-class anti-bot that
returns HTTP 403 to non-browser TLS fingerprints even via curl_cffi. SuperValu
serves fully-rendered product cards to a Chrome-impersonated request — real data
at zero cost and low maintenance.

Design:
- curl_cffi Chrome impersonation (TLS/JA3).
- Card parsing keyed on stable `data-testid` attributes.
- Pack-aware normalisation: detects multipacks (Twin Pack, N Pack), computes total
  litres and EUR/litre so multipacks and singles are comparable.
- Brand resolution from config (brand label first, title as fallback), with
  per-brand sugar terms and guards; non-drinks (no stated volume) are skipped.
- Search-query driven; compliance-by-design (human-rate delays, honest UA,
  per-run SKU cap, provenance incl. the originating search query).

Raw promotion text is stored as-is; it is parsed into mechanics in SQL
(sql/01_observations.sql) so the whole history benefits from parser changes.
"""

from __future__ import annotations

import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import yaml
from bs4 import BeautifulSoup

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "catalog.yaml"
IMPERSONATE_PROFILE = "chrome"

PACK_RE = re.compile(r"\(([^)]+)\)")
PRICE_RE = re.compile(r"€\s?(\d+\.\d{2})")
PACKCOUNT_RE = re.compile(r"(\d+)\s*Pack", re.IGNORECASE)
TWIN_RE = re.compile(r"Twin\s*Pack", re.IGNORECASE)
SIZE_RE = re.compile(r"([\d.]+)\s*(ml|l)\b", re.IGNORECASE)


@dataclass
class PriceRecord:
    """One scraped observation — a row in the fact table."""
    scraped_at: str
    retailer: str
    market: str
    currency: str
    product_id: str
    brand: str
    variant: str
    sugar_class: str
    pack: str               # the unit size as shown, e.g. "330 ml"
    container: str
    title: str | None
    base_price: float | None       # the price shown on the card (may be a promo price)
    unit_price: float | None       # base_price normalised to EUR/litre (total pack)
    unit_price_basis: str | None   # "litre"
    clubcard_price_text: str | None  # raw promotion badge text (legacy column name)
    deposit: float | None
    sugar_g_per_serving: float | None
    source_url: str
    status: str
    pack_count: int = 1
    total_litres: float | None = None
    is_flavoured: bool = False
    search_query: str | None = None


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# --- Classification ----------------------------------------------------------

def _norm(text: str | None) -> str:
    return re.sub(r"[-\s]+", " ", (text or "").lower()).strip()


CAFFEINE_PHRASES = re.compile(r"caffeine\s*free|zero\s*caffeine", re.IGNORECASE)


def classify_sugar(name: str, brand_cfg: dict | None = None) -> str:
    """full | zero | diet. Brand-specific `zero_terms` extend the defaults."""
    n = CAFFEINE_PHRASES.sub(" ", name.lower())
    extra = [t.lower() for t in (brand_cfg or {}).get("zero_terms", [])]
    if "zero sugar" in n or "no sugar" in n or re.search(r"\bzero\b", n):
        return "zero"
    if any(re.search(rf"\b{re.escape(t)}\b", n) for t in extra):
        return "zero"
    if "diet" in n or "light" in n:
        return "diet"
    return "full"


def classify_variant(name: str, brand_cfg: dict | None = None) -> str:
    """Coca-Cola keeps its named variants; other brands get a sugar-tier label."""
    family = (brand_cfg or {}).get("family", "Coca-Cola")
    n = name.lower()
    sugar = classify_sugar(name, brand_cfg)
    if family != "Coca-Cola":
        return {"zero": "No sugar", "diet": "Diet"}.get(sugar, "Regular")
    if "cherry" in n:
        return "Cherry"
    if "vanilla" in n:
        return "Vanilla"
    if sugar == "zero":
        return "Zero Sugar"
    if "diet" in n:
        return "Diet Coke"
    return "Original"


def is_flavoured(name: str) -> bool:
    n = name.lower()
    return ("cherry" in n) or ("vanilla" in n)


def classify_container(name: str, pack: str | None) -> str:
    blob = f"{name} {pack or ''}".lower()
    if re.search(r"\bcans?\b", blob):
        return "Can"
    if "glass" in blob:
        return "Glass"
    return "PET"


def pack_count(name: str) -> int:
    if TWIN_RE.search(name):
        return 2
    m = PACKCOUNT_RE.search(name)
    return int(m.group(1)) if m else 1


def unit_size_litres(name: str) -> float | None:
    m = SIZE_RE.search(name)
    if not m:
        return None
    val = float(m.group(1))
    if m.group(2).lower() == "ml":
        return val if val < 50 else val / 1000   # "1.75 ml" is a retailer typo for 1.75 L
    return val


def total_litres(name: str) -> float | None:
    us = unit_size_litres(name)
    return round(us * pack_count(name), 4) if us else None


def price_per_litre(name: str, price: float | None) -> float | None:
    tl = total_litres(name)
    return round(price / tl, 2) if (tl and price) else None


def resolve_brand(card_brand: str | None, title: str, config: dict) -> dict | None:
    """Return the configured brand entry for a card, or None to drop it.
    The brand label decides when present; the title is only a fallback."""
    excluded = [_norm(t) for t in config.get("exclude_title_terms", [])]
    ntitle = _norm(title)
    if any(t in ntitle for t in excluded):
        return None
    brands = config.get("brands") or []
    if not brands:
        return {}
    target = _norm(card_brand) if card_brand else ntitle
    for b in brands:
        if any(_norm(term) in target for term in b.get("match", [])):
            guard = [_norm(t) for t in b.get("title_must_contain", [])]
            if guard and not any(g in ntitle for g in guard):
                continue
            return b
    return None


def brand_matches(card_brand: str | None, title: str, config: dict) -> bool:
    return resolve_brand(card_brand, title, config) is not None


# --- Card parsing ------------------------------------------------------------

def parse_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    for card in soup.find_all(attrs={"data-testid": re.compile(r"^ProductCardWrapper-")}):
        sku = card["data-testid"].replace("ProductCardWrapper-", "")
        title_p = card.find("p", attrs={"aria-hidden": "true"})
        raw = title_p.get_text(strip=True) if title_p else ""
        price_m = PRICE_RE.search(raw)
        price = float(price_m.group(1)) if price_m else None
        name = raw.split(",")[0].strip() if "," in raw else raw
        pack_m = PACK_RE.search(name)
        pack = pack_m.group(1).strip() if pack_m else None
        brand_el = card.find(attrs={"data-testid": "ProductCardAQABrand"})
        brand = brand_el.get_text(strip=True) if brand_el else None
        promo = None
        promo_el = card.find(attrs={"data-testid": re.compile(r"^promotionBadge-")})
        if promo_el:
            promo = promo_el.get("title") or promo_el.get_text(strip=True)
        link = card.find("a", href=True)
        url = link["href"] if link else None
        cards.append({"sku": sku, "brand": brand, "name": name, "pack": pack,
                      "base_price": price, "promo": promo, "url": url})
    return cards


def build_records(cards: list[dict], config: dict, query: str, now: str,
                  page_url: str, seen: set[str], budget: int,
                  dropped: dict[str, int] | None = None) -> list[PriceRecord]:
    """Turn parsed cards into records. `budget` = SKUs still allowed this run.
    `dropped` (optional) counts brand labels rejected by the brand filter,
    which the run log prints to help tune `brands` in the catalog."""
    retailer = config["retailer"]
    out: list[PriceRecord] = []
    for c in cards:
        if len(out) >= budget:
            break
        if c["sku"] in seen or c["base_price"] is None:
            continue
        name = c["name"]
        if total_litres(name) is None:   # not a drink with a stated volume
            continue
        b = resolve_brand(c["brand"], name, config)
        if b is None:
            if dropped is not None:
                key = c["brand"] or "(no brand label)"
                dropped[key] = dropped.get(key, 0) + 1
            continue
        seen.add(c["sku"])
        out.append(PriceRecord(
            scraped_at=now, retailer=retailer["code"], market=retailer["market"],
            currency=retailer["currency"], product_id=c["sku"],
            brand=c["brand"] or b.get("family", "Unknown"),
            variant=classify_variant(name, b),
            sugar_class=classify_sugar(name, b),
            pack=c["pack"] or "Unknown",
            container=classify_container(name, c["pack"]),
            title=name, base_price=c["base_price"],
            unit_price=price_per_litre(name, c["base_price"]),
            unit_price_basis="litre",
            clubcard_price_text=c["promo"], deposit=None,
            sugar_g_per_serving=None,
            source_url=c["url"] or page_url, status="OK",
            pack_count=pack_count(name),
            total_litres=total_litres(name),
            is_flavoured=is_flavoured(name),
            search_query=query,
        ))
    return out


# --- Scrape orchestration ----------------------------------------------------

def search_url(config: dict, query: str) -> str:
    r = config["retailer"]
    return r["search_url"].format(rsid=r["rsid"], query=quote(query))


def request_headers(config: dict) -> dict:
    return {
        "User-Agent": config["compliance"]["user_agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IE,en;q=0.9",
    }


def scrape(config: dict) -> list[PriceRecord]:
    from curl_cffi import requests as cffi_requests  # network-only dependency

    comp = config["compliance"]
    queries = config["search_queries"]
    delay_lo, delay_hi = comp["request_delay_seconds"]
    cap = int(comp["max_skus_per_run"])
    records: list[PriceRecord] = []
    seen: set[str] = set()
    dropped: dict[str, int] = {}

    with cffi_requests.Session(impersonate=IMPERSONATE_PROFILE, timeout=30) as client:
        for qi, q in enumerate(queries):
            url = search_url(config, q)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            ok_so_far = sum(1 for r in records if r.status == "OK")
            if ok_so_far >= cap:
                print(f"Per-run SKU cap ({cap}) reached; skipping remaining queries.")
                break
            try:
                resp = client.get(url, headers=request_headers(config))
                if resp.status_code != 200:
                    records.append(_blank(config, now, q, url, f"HTTP_{resp.status_code}"))
                    continue
                cards = parse_cards(resp.text)
            except Exception as exc:  # noqa: BLE001
                records.append(_blank(config, now, q, url, f"PARSE_ERROR:{type(exc).__name__}"))
                continue
            records.extend(build_records(cards, config, q, now, url, seen, cap - ok_so_far, dropped))
            if qi < len(queries) - 1:
                time.sleep(random.uniform(delay_lo, delay_hi))

    if dropped:
        top = sorted(dropped.items(), key=lambda kv: -kv[1])[:15]
        print("Brand labels dropped by the brand filter: "
              + ", ".join(f"{k} ({v})" for k, v in top))
    return records


def fetch_html(config: dict, query: str) -> str:
    """Single live fetch — used to capture a real parser fixture."""
    from curl_cffi import requests as cffi_requests
    with cffi_requests.Session(impersonate=IMPERSONATE_PROFILE, timeout=30) as client:
        resp = client.get(search_url(config, query), headers=request_headers(config))
        resp.raise_for_status()
        return resp.text


def _blank(config, now, query, url, status) -> PriceRecord:
    retailer = config["retailer"]
    return PriceRecord(
        scraped_at=now, retailer=retailer["code"], market=retailer["market"],
        currency=retailer["currency"], product_id=f"query:{query}", brand="-",
        variant="-", sugar_class="-", pack="-", container="-", title=None,
        base_price=None, unit_price=None, unit_price_basis=None,
        clubcard_price_text=None, deposit=None, sugar_g_per_serving=None,
        source_url=url, status=status, search_query=query,
    )


def print_records(records: list[PriceRecord]) -> None:
    ok = [x for x in records if x.status == "OK"]
    for r in sorted(ok, key=lambda x: (x.sugar_class, x.unit_price or 0)):
        flav = " [flavoured]" if r.is_flavoured else ""
        print(f"  [{r.sugar_class:>4}] {r.variant:>10} x{r.pack_count:>2} {r.pack:>7} "
              f"EUR{r.base_price:>6} = EUR{r.unit_price}/L{flav}  promo={r.clubcard_price_text}")


def main() -> int:
    config = load_config()
    records = scrape(config)
    ok = sum(1 for r in records if r.status == "OK")
    print(f"Scraped {len(records)} rows — {ok} OK")
    print_records(records)
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
