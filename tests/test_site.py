import json
import re

import sitebuilder


def _cfg(base="https://example.test/fmcg"):
    return {"site": {"base_url": base, "case_study_published": "2026-10-06", "repository": "https://github.com/x/y",
                     "author": {"name": "Gadiel Guadarrama", "honorific_suffix": "M.Sc.", "job_title": "Architect",
                                "url": "https://gadielanalytics.com/about/", "email": "hello@gadielanalytics.com",
                                "locality": "Dublin", "country": "IE", "same_as": ["https://github.com/x"],
                                "knows_about": ["Pricing analytics"]},
                     "organization": {"name": "Gadiel Analytics", "url": "https://gadielanalytics.com/",
                                      "same_as": []},
                     "book": {"name": "The Analytics System", "url": "https://theanalyticssystem.com/"}}}


def _cube(headline="Coca-Cola <b>charges</b> a premium"):
    return {"first_run_date": "2026-06-04", "last_run_date": "2026-10-06",
            "narrative": {"titles": {"ex1": "Title one"},
                          "summary": {"kicker": "K", "headline": headline, "dek": "D",
                                      "kpis": [{"v": "8 of 10", "l": "packs"}],
                                      "messages": [{"text": "M", "section": "sugar-tax", "ex": "ex-1",
                                                    "label": "Exhibit 1"}]}}}


def test_build_pages(tmp_path):
    (tmp_path / "reports").mkdir()
    files = sitebuilder.build(_cfg(), _cube(), root=tmp_path)
    assert {f.name for f in files} == {"dashboard.html", "index.html", "sitemap.xml", "robots.txt"}
    for name in ("index.html", "reports/dashboard.html"):
        s = (tmp_path / name).read_text(encoding="utf-8")
        assert "{{" not in s
        assert "&lt;b&gt;charges&lt;/b&gt;" in s and "<b>charges</b>" not in s      # escaped
        ld = json.loads(re.search(r'<script type="application/ld\+json">\n(.*?)\n</script>', s, re.S)
                        .group(1).replace("<\\/", "</"))
        types = [n["@type"] for n in ld["@graph"]]
        assert {"Person", "Organization", "Book", "Dataset", "WebSite"} <= set(types)
        person = next(n for n in ld["@graph"] if n["@type"] == "Person")
        assert person["name"] == "Gadiel Guadarrama" and person["address"]["addressLocality"] == "Dublin"
        assert 'rel="canonical" href="https://example.test/fmcg/' in s
    sm = (tmp_path / "sitemap.xml").read_text()
    assert sm.count("<loc>") == 2 and "https://example.test/fmcg/reports/dashboard.html" in sm
    assert "Sitemap: https://example.test/fmcg/sitemap.xml" in (tmp_path / "robots.txt").read_text()


def test_description_keeps_author_name():
    d = sitebuilder._desc("x" * 300, "Daily study by Gadiel Guadarrama, Gadiel Analytics:")
    assert d.startswith("Daily study by Gadiel Guadarrama, Gadiel Analytics:") and len(d) <= 160


def test_graph_uses_official_identity():
    from scraper import load_config
    cfg = load_config()["site"]
    g = {n["@type"] if n["@id"].split("#")[1] != "publisher" else "Publisher": n
         for n in sitebuilder._graph(cfg, "https://example.test", {"type": "Article", "url": "https://example.test/",
                                                                    "title": "t", "description": "d"},
                                     {"first_run_date": "2026-06-04", "last_run_date": "2026-10-06"})["@graph"]}
    person, org, book = g["Person"], g["Organization"], g["Book"]
    assert "one of the world's largest FMCG beverage ecosystems" in person["description"]
    assert {a["name"] for a in person["alumniOf"]} >= {"UCD Michael Smurfit Graduate Business School"}
    assert not any("linkedin.com/in/" in u or "x.com" in u for u in person["sameAs"])   # no personal profiles
    assert "https://www.linkedin.com/company/gadielanalytics" in org["sameAs"]
    assert book["isbn"] == "978-1-0666557-1-7" and book["datePublished"] == "2026-10-20"
    assert g["Publisher"]["name"] == "Wyckham House"
