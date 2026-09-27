from pathlib import Path

import pytest

from scraper import (
    brand_matches, build_records, classify_container, classify_sugar,
    classify_variant, load_config, pack_count, parse_cards, total_litres,
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
    assert not brand_matches("Pepsi", "Pepsi Max Bottle (2 L)", config)
    assert not brand_matches("Jack Daniel's", "Jack Daniel's Whiskey & Coca-Cola Can", config)


def test_fixture_parse_and_filter(config):
    cards = parse_cards(FIXTURE.read_text(encoding="utf-8"))
    assert len(cards) == 6
    recs = build_records(cards, config, "q", "2026-01-01T00:00:00+00:00", "u", set(), 60)
    assert {r.sugar_class for r in recs} == {"full", "zero", "diet"}
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
