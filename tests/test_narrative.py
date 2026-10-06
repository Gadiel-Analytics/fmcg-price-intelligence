import json
import re
from pathlib import Path

import pytest

import narrative as nv

CUBE = Path(__file__).resolve().parent.parent / "reports" / "cube.json"
CAUSAL = re.compile(r"\b(because|caused|causes|due to|driven by|led to|leads to|as a result|in response to|resulting)\b", re.I)


def test_formatting_helpers():
    assert nv.words(8) == "eight" and nv.words(14) == "14" and nv.Words(1) == "One"
    assert nv.spct(-0.27) == "−27%" and nv.spct(0.325) == "+33%" and nv.spct(0) == "0%"
    assert nv.pack_of({"format_key": "2x2 L PET"}) == "2 × 2 L bottles"
    assert nv.pack_of({"format_key": "1x330 ml Can"}) == "330 ml can"
    assert nv.offer_label("3 for €6.00") == "3 for €6"
    assert nv.offer_label("only €4.00 (Rewards)") == "Rewards price €4"
    assert nv.offer_label("3 for €10.00 (Rewards)") == "3 for €10 (Rewards)"
    assert nv.fmt_short("2026-09-30") == "30 Sept" and nv.fmt_date("2026-10-06") == "6 October 2026"


def _row(fk, full, zero, ratio, pct):
    return {"format_key": fk, "pack": fk.split("x", 1)[1].rsplit(" ", 1)[0], "pack_count": int(fk.split("x")[0]),
            "container": fk.rsplit(" ", 1)[1], "full_per_litre": full, "zero_per_litre": zero,
            "diet_per_litre": zero, "spread_per_litre": full - zero, "spread_pct": pct, "levy_ratio": ratio}


def test_headline_variants():
    spread = [_row("1x330 ml Can", 5.61, 4.70, 3.03, 19.4), _row("1x2 L PET", 2.10, 1.70, 1.33, 23.5)]
    cola = [{"hero": "Coca-Cola", "rival": "Pepsi", "gap": -0.2, "hero_promo": False, "format_key": "1x2 L PET",
             "pack": "2 L", "pack_count": 1, "container": "PET", "sugar_tier": "full"}]
    bs = [{"brand_family": "Pepsi", "premium_formats_today": 2, "parity_formats_today": 2, "sugar_premium_today": 0.0,
           "days_observed": 10}]
    n = nv.build({"sugar_tax_spread": spread, "head_to_head": cola, "brand_summary": bs})
    assert n["titles"]["headline"] == ("Coca-Cola charges a full-sugar premium on every pack; "
                                       "Pepsi does not, and undercuts it on every matched pack")
    assert n["titles"]["ex1"].startswith("The full-sugar premium exceeds the sugar levy on every pack, and triples it")
    empty = nv.build({})
    assert empty["titles"]["headline"] == "Coca-Cola price-pack architecture at SuperValu Ireland"
    assert empty["summary"]["messages"] == []


def test_change_message_reads_naturally():
    item = {"date": "2026-10-01", "brand": "Coca-Cola", "kind": "promo_change", "offer_from": "3 for €6.75",
            "offer_to": "3 for €6.00", "skus": 5, "formats": ["1x2 L PET"], "sugar": ["diet", "zero"], "prices": []}
    assert nv.change_message(item) == ("On 1 Oct, Coca-Cola moved its Zero Sugar and Diet Coke 2 L bottles "
                                       "from 3 for €6.75 to 3 for €6")


@pytest.mark.skipif(not CUBE.exists(), reason="no committed cube")
def test_no_causal_language_in_any_generated_text():
    n = nv.build(json.loads(CUBE.read_text(encoding="utf-8")))
    texts = list(n["titles"].values()) + [n["summary"]["headline"], n["summary"]["dek"]] + \
        [m["text"] for m in n["summary"]["messages"]] + [k["l"] for k in n["summary"]["kpis"]]
    offenders = [t for t in texts if CAUSAL.search(t)]
    assert offenders == []
