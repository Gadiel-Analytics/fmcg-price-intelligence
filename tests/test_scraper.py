from pathlib import Path

import pytest

from scraper import (
    brand_matches, build_records, classify_container, classify_sugar,
    classify_variant, load_config, pack_count, parse_cards, resolve_brand, total_litres,
)

FIXTURE = Path(__file__).resolve().parent.parent / "scrapers" / "fixtures" / "supervalu_search_synthetic.html"


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.mark.parametrize("title,sugar,variant", [
    ("Coca-Cola Can (330 ml)", "full", "Original"),
    ("Coca-Cola Zero Sugar Bottle (2 L)", "zero", "Zero Sugar"),
    ("Coca-Cola Zero Sugar Zero Caffeine Can 4 Pack (330 ml)", "zero", "Zero Sugar"),
    ("Coca-Cola Zero Sugar Cherry Bottle (2 L)", "zero", "Cherry"),
    ("Diet Coke Can (330 ml)", "diet", "Diet Coke"),
])
def test_classification(title, sugar, variant):
    assert classify_sugar(title) == sugar
    assert classify_variant(title) == variant


@pytest.mark.parametrize("title,count,litres,container", [
    ("Coca-Cola Original Bottle Twin Pack (2 L)", 2, 4.0, "PET"),
    ("Coca-Cola Can 12 Pack (330 ml)", 12, 3.96, "Can"),
    ("Coca-Cola Original Cans 8 Pack (330 ml)", 8, 2.64, "Can"),
    ("Coca-Cola Bottle (1 L)", 1, 1.0, "PET"),
])
def test_pack_normalisation(title, count, litres, container):
    assert pack_count(title) == count
    assert total_litres(title) == litres
    assert classify_container(title, None) == container


def test_brand_matching(config):
    assert brand_matches("Coca-Cola", "Coca-Cola Can (330 ml)", config)
    assert brand_matches("Diet Coke", "Diet Coke Can (330 ml)", config)      # was silently dropped before
    assert brand_matches(None, "Diet Coke Can (330 ml)", config)             # title fallback
    assert not brand_matches("Jack Daniel's", "Jack Daniel's Whiskey & Coca-Cola Can", config)
    assert not brand_matches("Schweppes", "Schweppes Tonic Water (1 L)", config)


@pytest.mark.parametrize("label,title,family,sugar", [
    ("Pepsi", "Pepsi Max Bottle (2 L)", "Pepsi", "zero"),
    ("Pepsi", "Pepsi Bottle (2 L)", "Pepsi", "full"),
    ("Pepsi", "Pepsi Diet Can (330 ml)", "Pepsi", "diet"),
    ("7UP", "7UP Free Bottle (2 L)", "7UP", "zero"),
    ("Diet Coke", "Diet Coke Caffeine Free Bottle (2 L)", "Coca-Cola", "diet"),
    ("Monster", "Monster Energy Ultra White Can (500 ml)", "Monster", "zero"),
    ("Red Bull", "Red Bull Sugarfree Energy Drink Can (250 ml)", "Red Bull", "zero"),
    ("Club", "Club Orange Bottle (2 L)", "Club", "full"),
    ("SuperValu", "SuperValu Cola Bottle (2 L)", "SuperValu own-label", "full"),
])
def test_competitor_resolution(config, label, title, family, sugar):
    b = resolve_brand(label, title, config)
    assert b is not None and b["family"] == family
    assert classify_sugar(title, b) == sugar


def test_guards_drop_off_category_items(config):
    assert resolve_brand("SuperValu", "SuperValu Sparkling Water (2 L)", config) is None
    assert resolve_brand("Club", "Club Milk Biscuits 8 Pack", config) is None


def test_fixture_parse_and_filter(config):
    cards = parse_cards(FIXTURE.read_text(encoding="utf-8"))
    assert len(cards) == 8
    dropped: dict[str, int] = {}
    recs = build_records(cards, config, "q", "2026-01-01T00:00:00+00:00", "u", set(), 60, dropped)
    assert {r.sugar_class for r in recs} == {"full", "zero", "diet"}
    assert {r.product_id for r in recs} >= {"9000000003"}          # Pepsi Max now collected
    assert "9000000004" not in {r.product_id for r in recs}        # biscuits: no volume
    assert dropped == {"Jack Daniel's": 1, "Schweppes": 1}
    assert all(r.search_query == "q" for r in recs)
    two_l = next(r for r in recs if r.product_id == "1009117003")
    assert two_l.base_price == 4.20 and two_l.unit_price == 2.10
    assert two_l.clubcard_price_text == "2 for €6.50"


def test_per_run_cap_is_global(config):
    cards = parse_cards(FIXTURE.read_text(encoding="utf-8"))
    seen: set[str] = set()
    first = build_records(cards, config, "q1", "t", "u", seen, 2)
    second = build_records(cards, config, "q2", "t", "u", seen, 0)
    assert len(first) == 2 and second == []


def test_ml_typo_read_as_litres():
    assert total_litres("Fanta Crimson Cherry Bottle (1.75 ml)") == 1.75
    assert total_litres("Coca-Cola Can (330 ml)") == 0.33
