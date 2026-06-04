"""
FMCG Price Intelligence — Scraper Core (M1) · SuperValu Ireland
===============================================================
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
  litres and €/litre so multipacks and singles are comparable.
- Flavour + caffeine flags keep Cherry/Vanilla out of the core spread.
- Search-query driven; compliance-by-design (human-rate delays, honest UA, cap).
"""

from __future__ import annotations

import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "catalog.yaml"
IMPERSONATE_PROFILE = "chrome"

PACK_RE = re.compile(r"\(([^)]+)\)")
PRICE_RE = re.compile(r"€\s?(\d+\.\d{2})")
PACKCOUNT_RE = re.compile(r"(\d+)\s*Pack", re.IGNORECASE)
TWIN_RE = re.compile(r"Twin\s*Pack", re.IGNORECASE)
SIZE_RE = re.compile(r"([\d.]+)\s*(ml|l)\b", re.IGNORECASE)


@dataclass
class PriceRecord:
    """One scraped observation — a row in the fact table / data cube."""
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
    base_price: float | None
    unit_price: float | None       # NORMALISED €/litre (total pack)
    unit_price_basis: str | None   # "litre"
    clubcard_price_text: str | None
    deposit: float | None
    sugar_g_per_serving: float | None
    source_url: str
    status: str
    # extra dimensions for richer RGM analysis
    pack_count: int = 1
    total_litres: float | None = None
    is_flavoured: bool = False


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# --- Classification ----------------------------------------------------------

def classify_sugar(name: str) -> str:
    n = name.lower()
    if "zero" in n or "no sugar" in n:
        return "zero"
    if "diet" in n or "light" in n:
        return "diet"
    return "full"


def classify_variant(name: str) -> str:
    """Plain 'Coca-Cola Bottle/Can' (no modifier) is the Original."""
    n = name.lower()
    if "cherry" in n:
        return "Cherry"
    if "vanilla" in n:
        return "Vanilla"
    if "zero" in n:
        return "Zero Sugar"
    if "diet" in n:
        return "Diet Coke"
    return "Original"


def is_flavoured(name: str) -> bool:
    n = name.lower()
    return ("cherry" in n) or ("vanilla" in n)


def classify_container(name: str, pack: str | None) -> str:
    blob = f"{name} {pack or ''}".lower()
    if "can" in blob:
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
    return val / 1000 if m.group(2).lower() == "ml" else val


def total_litres(name: str) -> float | None:
    us = unit_size_litres(name)
    return round(us * pack_count(name), 4) if us else None


def price_per_litre(name: str, price: float | None) -> float | None:
    tl = total_litres(name)
    return round(price / tl, 2) if (tl and price) else None


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


# --- Scrape orchestration ----------------------------------------------------

def scrape(config: dict) -> list[PriceRecord]:
    retailer = config["retailer"]
    comp = config["compliance"]
    queries = config["search_queries"]
    brand_filter = [b.lower() for b in config.get("brand_filter", [])]

    delay_lo, delay_hi = comp["request_delay_seconds"]
    headers = {
        "User-Agent": comp["user_agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IE,en;q=0.9",
    }
    records: list[PriceRecord] = []
    seen: set[str] = set()

    with cffi_requests.Session(impersonate=IMPERSONATE_PROFILE, timeout=30) as client:
        for qi, q in enumerate(queries):
            url = retailer["search_url"].format(rsid=retailer["rsid"], query=q.replace(" ", "%20"))
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                resp = client.get(url, headers=headers)
                if resp.status_code != 200:
                    records.append(_blank(retailer, now, q, url, f"HTTP_{resp.status_code}"))
                    continue
                cards = parse_cards(resp.text)
            except Exception as exc:  # noqa: BLE001
                records.append(_blank(retailer, now, q, url, f"PARSE_ERROR:{type(exc).__name__}"))
                continue

            kept = 0
            for c in cards:
                if c["sku"] in seen:
                    continue
                if brand_filter and (c["brand"] or "").lower() not in brand_filter:
                    continue
                if c["base_price"] is None:
                    continue
                seen.add(c["sku"])
                kept += 1
                if kept > comp["max_skus_per_run"]:
                    break
                name = c["name"]
                records.append(PriceRecord(
                    scraped_at=now, retailer=retailer["code"], market=retailer["market"],
                    currency=retailer["currency"], product_id=c["sku"],
                    brand=c["brand"] or "Unknown",
                    variant=classify_variant(name),
                    sugar_class=classify_sugar(name),
                    pack=c["pack"] or "Unknown",
                    container=classify_container(name, c["pack"]),
                    title=name, base_price=c["base_price"],
                    unit_price=price_per_litre(name, c["base_price"]),
                    unit_price_basis="litre",
                    clubcard_price_text=c["promo"], deposit=None,
                    sugar_g_per_serving=None,
                    source_url=c["url"] or url, status="OK",
                    pack_count=pack_count(name),
                    total_litres=total_litres(name),
                    is_flavoured=is_flavoured(name),
                ))

            if qi < len(queries) - 1:
                time.sleep(random.uniform(delay_lo, delay_hi))

    return records


def _blank(retailer, now, query, url, status) -> PriceRecord:
    return PriceRecord(
        scraped_at=now, retailer=retailer["code"], market=retailer["market"],
        currency=retailer["currency"], product_id=f"query:{query}", brand="-",
        variant="-", sugar_class="-", pack="-", container="-", title=None,
        base_price=None, unit_price=None, unit_price_basis=None,
        clubcard_price_text=None, deposit=None, sugar_g_per_serving=None,
        source_url=url, status=status,
    )


def main() -> int:
    config = load_config()
    records = scrape(config)
    ok = sum(1 for r in records if r.status == "OK")
    print(f"Scraped {len(records)} rows — {ok} OK")
    for r in sorted([x for x in records if x.status == "OK"], key=lambda x: (x.sugar_class, x.unit_price or 0)):
        flav = " [flavoured]" if r.is_flavoured else ""
        print(f"  [{r.sugar_class:>4}] {r.variant:>10} x{r.pack_count:>2} {r.pack:>7} "
              f"EUR{r.base_price:>6} = EUR{r.unit_price}/L{flav}  promo={r.clubcard_price_text}")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
