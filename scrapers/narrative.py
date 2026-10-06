"""
FMCG Price Intelligence — Narrative
===================================
Every headline, KPI, key message and exhibit title is computed here, once, from
the cube, with explicit guards. The dashboard and the case-study page render
these strings; they are pre-rendered into the HTML so search engines and link
previews read the findings, not a loading message. Tested in tests/test_narrative.py.

Wording rules: describe, never attribute. A change after an event is reported as
a change; a ratio to the levy is a benchmark, not a pass-through.
"""

from __future__ import annotations

import math
import re
import statistics
from datetime import date

FOCAL, RIVAL, MIN_DAYS = "Coca-Cola", "Pepsi", 14
_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight",
          "nine", "ten", "eleven", "twelve"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"]
_MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August",
                "September", "October", "November", "December"]


# --- formatting (mirrors the dashboard) -----------------------------------------

def words(n: int) -> str:
    return _WORDS[n] if 0 <= n < len(_WORDS) else str(n)


def Words(n: int) -> str:
    w = words(n)
    return w[:1].upper() + w[1:]


def plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def eur(v) -> str:
    return "—" if v is None else f"€{v:.2f}"


def pct0(v) -> str:
    return "—" if v is None else f"{_round_half_up(v * 100)}%"


def spct(v) -> str:
    if v is None:
        return "—"
    n = abs(_round_half_up(v * 100)) if v >= 0 else abs(-_round_half_up(-v * 100))
    sign = "+" if v > 0 else ("−" if v < 0 else "")
    return f"{sign}{n}%"


def fmt_date(s: str | None) -> str:
    if not s:
        return "—"
    d = date.fromisoformat(s[:10])
    return f"{d.day} {_MONTHS_LONG[d.month - 1]} {d.year}"


def fmt_short(s: str | None) -> str:
    if not s:
        return "—"
    d = date.fromisoformat(s[:10])
    return f"{d.day} {_MONTHS[d.month - 1]}"


def pack_of(r: dict) -> str:
    if r.get("pack"):
        n, size, ct = r["pack_count"], r["pack"], r["container"]
    else:
        m = re.match(r"^(\d+)x(.+) (\S+)$", r["format_key"])
        n, size, ct = int(m.group(1)), m.group(2), m.group(3)
    noun = "bottle" if ct == "PET" else ct.lower()
    return f"{n} × {size} {noun}s" if n > 1 else f"{size} {noun}"


def tier_name(brand: str, tier: str) -> str:
    if brand == FOCAL:
        return "Original" if tier == "full" else "Zero Sugar"
    if brand == RIVAL:
        return "Pepsi" if tier == "full" else "Pepsi Max"
    return "Regular" if tier == "full" else "No sugar"


def tier_pack(brand: str, r: dict) -> str:
    tier = r.get("sugar_tier") or ("full" if r.get("sugar_class") == "full" else "no_sugar")
    return f"{tier_name(brand, tier)} {pack_of(r)}"


def offer_label(o: str | None) -> str:
    if not o or o == "none":
        return "no promotion"
    if o == "badge":
        return "value badge"
    s = re.sub(r"€(\d+)\.00", r"€\1", o)
    s = re.sub(r"^only ", "price cut to ", s)
    if "(Rewards)" in s:
        rewards_price = s.startswith("price cut")
        s = s.replace(" (Rewards)", "").replace("price cut to ", "Rewards price ")
        s = s if rewards_price else s + " (Rewards)"
    return s


def change_text(i: dict) -> str:
    packs = list(dict.fromkeys(pack_of({"format_key": f}) for f in i["formats"]))
    sn = ({"full": "Original", "zero": "Zero Sugar", "diet": "Diet Coke"} if i["brand"] == FOCAL
          else {"full": "regular", "zero": "no sugar", "diet": "diet"})
    sug = list(dict.fromkeys(sn.get(k, k) for k in (i.get("sugar") or [])))
    what = (" and ".join(packs) if len(packs) <= 2 else f"{len(packs)} pack sizes") + \
           (f", {' and '.join(sug)}" if sug and len(sug) < 3 else "")
    k = i["kind"]
    if k == "promo_change":
        return f"{what}: offer changed from {offer_label(i['offer_from'])} to {offer_label(i['offer_to'])}"
    if k == "promo_start":
        return f"{what}: promotion started, {offer_label(i['offer_to'])}"
    if k == "promo_end":
        return f"{what}: promotion ended (was {offer_label(i['offer_from'])})"
    if k == "price_change":
        p = i["prices"][0]
        return (f"{what}: regular price {i['direction']} from {eur(p[0])} to {eur(p[1])}" if i["skus"] == 1
                else f"{what}: regular price {i['direction']} on {i['skus']} SKUs")
    if k == "listed":
        return f"{what}: new listing"
    if k == "relisted":
        return f"{what}: listed again after a gap"
    if k == "delisted":
        d = date.fromordinal(date.fromisoformat(i["date"]).toordinal() - 1).isoformat()
        return f"{what}: not seen since {fmt_short(d)}"
    return what


def change_message(i: dict) -> str:
    """One readable sentence for the most relevant focal-brand change."""
    sn = {"full": "Original", "zero": "Zero Sugar", "diet": "Diet Coke"}
    sug = " and ".join(dict.fromkeys(sn.get(k, k) for k in sorted(i.get("sugar") or [], key=lambda k: "fzd".index(k[0]))))
    packs = list(dict.fromkeys(pack_of({"format_key": f}) for f in i["formats"]))
    pk = packs[0] if len(packs) == 1 else f"{len(packs)} pack sizes"
    if len(packs) == 1 and i["skus"] > 1 and not pk.endswith("s"):
        pk += "s"
    subject = f"its {sug + ' ' if sug else ''}{pk}"
    d = fmt_short(i["date"])
    if i["kind"] == "promo_change":
        return f"On {d}, {FOCAL} moved {subject} from {offer_label(i['offer_from'])} to {offer_label(i['offer_to'])}"
    if i["kind"] == "promo_start":
        return f"On {d}, {FOCAL} started a promotion on {subject}: {offer_label(i['offer_to'])}"
    if i["kind"] == "price_change":
        p = i["prices"][0]
        return (f"On {d}, {FOCAL} {'raised' if i['direction'] == 'up' else 'cut'} the regular price of {subject}"
                + (f" from {eur(p[0])} to {eur(p[1])}" if i["skus"] == 1 else ""))
    return f"On {d}, {change_text(i)}"


# --- analysis -------------------------------------------------------------------

def _inversions(latest: list[dict]) -> list[dict]:
    rows = [r for r in latest if (r.get("brand_family") or FOCAL) == FOCAL and r.get("is_core")
            and r.get("regular_ppl") is not None and r.get("sugar_class") in ("full", "zero")]
    groups: dict = {}
    for r in rows:
        groups.setdefault(f"{r['container']}|{r['sugar_class']}", []).append(r)
    out = []
    for g in groups.values():
        for big in g:
            smaller = [s for s in g if s["total_litres"] < big["total_litres"] - 1e-6
                       and s["regular_ppl"] < big["regular_ppl"] * 0.99]
            if smaller:
                s = sorted(smaller, key=lambda x: x["regular_ppl"])[0]
                out.append({"big": big, "small": s, "excess": big["regular_ppl"] / s["regular_ppl"] - 1})
    return sorted(out, key=lambda v: -v["excess"])


def build(cube: dict) -> dict:
    """Return {'titles': {...}, 'summary': {...}} for the cube."""
    a: dict = {}
    spread = sorted(cube.get("sugar_tax_spread") or [], key=lambda r: -r["levy_ratio"])
    above = [r for r in spread if r["levy_ratio"] >= 1]
    all_positive = bool(spread) and all(r["spread_per_litre"] > 0 for r in spread)
    h2h = cube.get("head_to_head") or []
    cola = [r for r in h2h if r["hero"] == FOCAL and r["rival"] == RIVAL]
    cola_cheaper = [r for r in cola if r["gap"] < 0]
    cola_ahead = [r for r in cola if r["gap"] > 0]
    flav = [r for r in h2h if r["hero"] != FOCAL and not r.get("adjacent")]
    bs = cube.get("brand_summary") or []
    by_brand = {b["brand_family"]: b for b in bs}
    rv = by_brand.get(RIVAL)
    rival_parity = ({"n": rv["parity_formats_today"], "m": rv["premium_formats_today"]}
                    if rv and rv.get("premium_formats_today") else None)
    competitor_days = max([0] + [b.get("days_observed") or 0 for b in bs if b["brand_family"] != FOCAL])
    pr = [r for r in (cube.get("promo_summary") or []) if r.get("active")
          and (r.get("brand_family") or FOCAL) == FOCAL and r["days_observed"] >= MIN_DAYS]
    perma = sorted([r for r in pr if r["promo_share"] >= 0.9],
                   key=lambda r: (-r["promo_share"], -r["days_observed"], len(r["title"])))
    inversions = _inversions(cube.get("latest") or [])
    t2 = [r for r in (cube.get("trend") or []) if r["format_key"] == "1x2 L PET"
          and r["sugar_class"] in ("full", "zero")]

    def below(k):
        s = [r for r in t2 if r["sugar_class"] == k]
        return len(s), len([r for r in s if r["effective_ppl"] < r["regular_ppl"] - 0.005])

    en = [r for r in (cube.get("latest") or []) if r.get("segment") == "Energy" and r.get("is_core")
          and r.get("effective_ppl") is not None]

    def med(f):
        v = [r["effective_ppl"] for r in en if r["brand_family"] == f]
        return statistics.median(v) if v else None

    evs = [e for e in (cube.get("events") or []) if e.get("kind") == "policy"]
    ev = next((e for e in evs if e["status"] != "upcoming" and e["post_days"] > 0), None) or \
        next((e for e in sorted(evs, key=lambda e: e["days_to"]) if e["status"] == "upcoming"), None)

    t: dict = {}
    if spread:
        top, r = spread[0], spread[0]["levy_ratio"]
        tail = (f", and triples it on the {pack_of(top)}" if r >= 2.95 else
                f", and doubles it on the {pack_of(top)}" if r >= 1.95 else
                f", peaking at {r:.2f}× on the {pack_of(top)}")
        t["ex1"] = ("The full-sugar premium sits below the sugar levy on every pack" if not above else
                    f"The full-sugar premium exceeds the sugar levy on every pack{tail}" if len(above) == len(spread) else
                    f"The full-sugar premium exceeds the sugar levy on {words(len(above))} of {words(len(spread))} packs{tail}")
    if cola:
        s = f"{RIVAL} is cheaper than {FOCAL} on {words(len(cola_cheaper))} of {words(len(cola))} matched packs"
        if len(cola_ahead) == 1:
            e = cola_ahead[0]
            s += f"; only the {'promoted ' if e['hero_promo'] else ''}{tier_pack(FOCAL, e)} puts {FOCAL} ahead"
        elif len(cola_ahead) > 1:
            s += f"; {FOCAL} is cheaper on the other {words(len(cola_ahead))}"
        t["ex6"] = s
    prem = [b for b in bs if (b.get("premium_formats_today") or 0) > 0 and b.get("sugar_premium_today") is not None]
    if prem:
        strong = [b for b in prem if b["sugar_premium_today"] >= 0.05]
        if len(strong) == 1:
            tail = (f", against {spct(rv['sugar_premium_today'])} for {RIVAL}"
                    if rv and rv["brand_family"] != strong[0]["brand_family"] and rv.get("sugar_premium_today") is not None else "")
            t["ex7"] = (f"{strong[0]['brand_family']} is the only brand pricing full sugar clearly above no sugar: "
                        f"a median {spct(strong[0]['sugar_premium_today'])} per litre{tail}")
        elif len(strong) > 1:
            t["ex7"] = f"{', '.join(b['brand_family'] for b in strong)} price full sugar clearly above no sugar"
        else:
            t["ex7"] = "No brand prices full sugar clearly above no sugar at today's prices"
    if flav:
        groups: dict = {}
        for r in flav:
            groups.setdefault(f"{r['hero']}|{r['rival']}", []).append(r)
        t["ex8"] = "; ".join(f"{k.split('|')[1]} is cheaper than {k.split('|')[0]} on "
                             f"{words(len([x for x in g if x['gap'] < 0]))} of {words(len(g))} packs"
                             for k, g in groups.items())
    rb, mo = med("Red Bull"), med("Monster")
    if rb and mo:
        t["ex9"] = f"Red Bull costs about {rb / mo:.1f}× Monster per litre at the median price"
    if perma:
        fmts = list(dict.fromkeys(r["format_key"] for r in perma))
        one = len(perma) == 1
        fp = pack_of({"format_key": fmts[0]}) if len(fmts) == 1 else None
        t["ex4"] = (f"{Words(len(perma))} {FOCAL} {plural(len(perma), 'SKU')} {'was' if one else 'were'} on promotion "
                    f"on at least 90% of days" + ((f", a {fp}" if one else f", all of them {fp}s") if fp else ""))
    elif pr:
        t["ex4"] = f"{FOCAL} promotions are occasional: no SKU was on promotion on more than 90% of days"
    fn, fb = below("full")
    zn, zb = below("zero")
    if fn:
        t["ex5"] = (f"Shoppers could buy the 2 L Original below its regular price on {fb} of {fn} days, "
                    f"and the 2 L Zero Sugar on {zb} of {zn}")
    full_cc = [r for r in (cube.get("latest") or []) if (r.get("brand_family") or FOCAL) == FOCAL
               and r.get("is_core") and r.get("sugar_class") == "full" and r.get("regular_ppl") is not None]
    if len(full_cc) > 1:
        hi = full_cc[0]
        lo = full_cc[0]
        for r in full_cc:
            hi = r if r["regular_ppl"] > hi["regular_ppl"] else hi
            lo = r if r["regular_ppl"] < lo["regular_ppl"] else lo
        art = lambda r: "" if r["pack_count"] > 1 else "a "
        t["ex2"] = (f"Pack size cuts the Original price per litre by {pct0(1 - lo['regular_ppl'] / hi['regular_ppl'])}, "
                    f"from {eur(hi['regular_ppl'])} for {art(hi)}{pack_of(hi)} to {eur(lo['regular_ppl'])} for {art(lo)}{pack_of(lo)}")
    n_inv = len(inversions)
    t["ex3"] = (f"{Words(n_inv)} {FOCAL} {plural(n_inv, 'pack')} {'costs' if n_inv == 1 else 'cost'} more per litre "
                f"than a smaller pack of the same range" if n_inv else
                f"No {FOCAL} pack costs more per litre than a smaller pack of the same range")
    if ev and ev.get("rows"):
        if ev["status"] == "upcoming":
            lo, hi, dd = min(r["prem_pre"] for r in ev["rows"]), max(r["prem_pre"] for r in ev["rows"]), ev["days_to"]
            lead = "On the day of" if dd == 0 else f"{Words(dd)} {plural(dd, 'day')} before"
            t["exev"] = (f"{lead} {ev['label']}, the full-sugar premium runs from {eur(lo)} to {eur(hi)} per litre "
                         f"across {words(len(ev['rows']))} Coca-Cola packs")
        else:
            ok = [r for r in ev["rows"] if r.get("delta") is not None]
            ch = [r for r in ok if abs(r["delta"]) >= 0.02]
            up = len([r for r in ch if r["delta"] > 0])
            dn = len(ch) - up
            levy_tail = "; no change to the levy was announced" if ev.get("levy_changed") is False else ""
            days = f"{words(ev['post_days'])} {plural(ev['post_days'], 'day')}"
            t["exev"] = (f"{ev['label']}: no post-event prices yet" if not ok else
                         f"In the {days} since {ev['label']}, no Coca-Cola pack changed its full-sugar premium{levy_tail}" if not ch else
                         f"The full-sugar premium {'rose' if dn == 0 else 'fell' if up == 0 else 'moved'} on "
                         f"{words(len(ch))} of {words(len(ok))} Coca-Cola packs in the {days} since {ev['label']}")
    # headline
    if all_positive:
        h = f"{FOCAL} charges a full-sugar premium on every pack"
    elif spread:
        h = (f"{FOCAL} charges a full-sugar premium on {words(len([r for r in spread if r['spread_per_litre'] > 0]))} "
             f"of {words(len(spread))} packs")
    else:
        h = f"{FOCAL} price-pack architecture at SuperValu Ireland"
    share = rival_parity["n"] / rival_parity["m"] if rival_parity and rival_parity["m"] else 0
    b = f"{RIVAL} does not" if share == 1 else (f"{RIVAL} largely does not" if share >= 0.75 else "")
    cpart = ""
    if cola:
        n, m = len(cola_cheaper), len(cola)
        cpart = ("undercuts it on every matched pack" if n == m else
                 "undercuts it on all but one matched pack" if n == m - 1 else
                 f"undercuts it on {words(n)} of {words(m)} matched packs" if n > m / 2 else "")
    if b:
        h += f"; {b}" + (f", and {cpart}" if cpart else "")
    elif cpart:
        h += f"; {RIVAL} {cpart}"
    t["headline"] = h

    # summary block
    kpis = []
    if spread:
        lo, hi = min(r["spread_pct"] for r in spread), max(r["spread_pct"] for r in spread)
        kpis.append({"v": f"+{_round_half_up(lo)}% to +{_round_half_up(hi)}%",
                     "l": f"{FOCAL} full-sugar premium over Zero Sugar per litre, across {len(spread)} packs"})
    k = cube.get("kpis") or {}
    if rival_parity:
        kpis.append({"v": f"{rival_parity['n']} of {rival_parity['m']}",
                     "l": "pack sizes where Pepsi and Pepsi Max cost the same today"})
    elif k.get("levy_ratio_min") is not None:
        kpis.append({"v": f"{k['levy_ratio_min']:.2f}×–{k['levy_ratio_max']:.2f}×",
                     "l": "full-sugar premium as a multiple of the sugar levy"})
    if cola:
        kpis.append({"v": f"{len(cola_cheaper)} of {len(cola)}",
                     "l": f"matched cola packs where {RIVAL} is cheaper at today's price"})
    else:
        kpis.append({"v": pct0(k.get("promo_share_sku_days")), "l": f"of {FOCAL} SKU-days on promotion"})
    if perma:
        p = perma[0]
        on = _round_half_up(p["promo_share"] * p["days_observed"])
        kpis.append({"v": f"{on} of {p['days_observed']}",
                     "l": f"days the {FOCAL} {tier_pack(FOCAL, p)} was on promotion"})
    msgs = [[t.get("ex1"), "sugar-tax", "ex-1", "Exhibit 1"], [t.get("exev"), "sugar-tax", "ex-ev", "Exhibit 2"],
            [t.get("ex6"), "competition", "ex-6", "Exhibit 7"], [t.get("ex7"), "competition", "ex-7", "Exhibit 8"],
            [t.get("ex4"), "promotions", "ex-4", "Exhibit 5"],
            [t.get("ex3") if inversions else None, "pack-architecture", "ex-3", "Exhibit 4"],
            [t.get("ex9"), "competition", "ex-9", "Exhibit 10"]]
    msgs = [m for m in msgs if m[0]]
    fc = next((i for i in ((cube.get("change_feed") or {}).get("items") or []) if i["brand"] == FOCAL
               and i["kind"] in ("promo_change", "price_change", "promo_start")), None)
    if fc:
        msgs.insert(2, [change_message(fc), "summary", "changes", "What changed"])
    dek = ("Shelf prices read every day, split into regular and promotional prices, normalised per litre "
           "and matched pack for pack.")
    if competitor_days:
        dek += (f" Competitor prices cover {competitor_days} {plural(competitor_days, 'day')} so far, so the "
                f"competitive read is a first snapshot that firms up as history builds.")
    summary = {
        "kicker": (f"SuperValu Ireland, carbonated soft drinks. Daily since {fmt_date(cube.get('first_run_date'))}; "
                   f"updated {fmt_date(cube.get('last_run_date'))}."),
        "headline": t["headline"], "dek": dek, "kpis": kpis[:4],
        "messages": [{"text": m[0], "section": m[1], "ex": m[2], "label": m[3]} for m in msgs],
    }
    return {"titles": t, "summary": summary}
