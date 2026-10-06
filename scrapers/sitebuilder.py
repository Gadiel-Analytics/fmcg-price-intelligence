"""
FMCG Price Intelligence — Site builder (sitebuilder.py)
==========================================================
Renders the public pages from site/*.html templates on every run:

  index.html               case study (Article), at the site root
  reports/dashboard.html   live dashboard (WebPage), pre-rendered with the day's findings
  sitemap.xml, robots.txt  crawl hints, using site.base_url

Findings come from scrapers/narrative.py, so crawlers and link previews read the
same headline the dashboard shows. Structured data (JSON-LD) describes the author,
Gadiel Analytics, The Analytics System, the dataset and each page.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _render(template: str, values: dict) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{(\w+)\}\}", out)
    if left:
        raise ValueError(f"unfilled placeholders: {sorted(set(left))}")
    return out


def _kpis_html(kpis: list[dict]) -> str:
    return "".join(f'<div class="k"><div class="kv">{_e(k["v"])}</div><div class="kl">{_e(k["l"])}</div></div>'
                   for k in kpis)


def _messages_html(messages: list[dict], dashboard_prefix: str = "") -> str:
    out = []
    for m in messages:
        href = f'{dashboard_prefix}#{m["section"]}'
        attrs = "" if dashboard_prefix else f' data-goto="{_e(m["section"])}" data-ex="{_e(m["ex"])}"'
        out.append(f'<li><p>{_e(m["text"])}.</p><a href="{_e(href)}"{attrs}>See {_e(m["label"].lower())}</a></li>')
    return "".join(out)


def _graph(cfg: dict, base: str, page: dict, cube: dict) -> dict:
    a, o, b = cfg["author"], cfg["organization"], cfg["book"]
    person = {
        "@type": "Person", "@id": f"{base}/#person", "name": a["name"],
        "honorificSuffix": a.get("honorific_suffix"), "jobTitle": a.get("job_title"),
        "description": " ".join((a.get("description") or "").split()) or None,
        "url": a.get("url"), "image": a.get("image"),
        "email": f'mailto:{a["email"]}' if a.get("email") else None,
        "address": {"@type": "PostalAddress", "addressLocality": a.get("locality"), "addressCountry": a.get("country")},
        "alumniOf": [{"@type": "EducationalOrganization", "name": n} for n in a.get("alumni_of") or []],
        "knowsAbout": a.get("knows_about"), "sameAs": a.get("same_as"),
        "worksFor": {"@id": f"{base}/#organization"},
    }
    org = {"@type": "Organization", "@id": f"{base}/#organization", "name": o["name"], "url": o["url"],
           "description": o.get("description"), "logo": f"{base}/reports/favicon.svg",
           "founder": {"@id": f"{base}/#person"}, "sameAs": o.get("same_as")}
    pub = b.get("publisher") or {}
    publisher = {"@type": "Organization", "@id": f"{base}/#publisher", "name": pub.get("name"),
                 "address": {"@type": "PostalAddress", "addressLocality": pub.get("locality"),
                             "addressCountry": pub.get("country")},
                 "sameAs": pub.get("same_as")} if pub.get("name") else None
    editions = [{"@type": "Book", "bookFormat": f"https://schema.org/{fmt}", "isbn": isbn}
                for fmt, isbn in (("Paperback", b.get("isbn_paperback")), ("EBook", b.get("isbn_ebook"))) if isbn]
    book = {"@type": "Book", "@id": f"{base}/#book", "name": b["name"], "alternativeHeadline": b.get("subtitle"),
            "url": b["url"], "image": b.get("image"), "author": {"@id": f"{base}/#person"},
            "publisher": {"@id": f"{base}/#publisher"} if publisher else None,
            "datePublished": b.get("date_published"), "isbn": b.get("isbn_paperback"),
            "workExample": editions, "sameAs": b.get("same_as"), "inLanguage": "en"}
    dataset = {
        "@type": "Dataset", "@id": f"{base}/#dataset",
        "name": "SuperValu Ireland soft-drink shelf prices, daily",
        "description": ("Daily shelf prices for Coca-Cola, Pepsi, Sprite, 7UP, Fanta, Club, Red Bull and Monster at "
                        "SuperValu Ireland: shown price, promotion mechanic, regular and promotional price per litre, "
                        "pack size and sugar tier. Collected at human rate from public search results."),
        "creator": {"@id": f"{base}/#person"}, "publisher": {"@id": f"{base}/#organization"},
        "temporalCoverage": f'{cube.get("first_run_date")}/..',
        "spatialCoverage": {"@type": "Place", "name": "Ireland"},
        "variableMeasured": ["shelf price (EUR)", "price per litre (EUR)", "promotion mechanic",
                             "regular price (EUR)", "pack size", "sugar tier"],
        "keywords": ["price intelligence", "revenue growth management", "sugar tax", "soft drinks", "Ireland",
                     "Coca-Cola", "Pepsi", "SuperValu"],
        "isAccessibleForFree": True,
        "license": f'{cfg["repository"]}/blob/main/COPYRIGHT.md',
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/vnd.apache.parquet",
                          "contentUrl": f'{cfg["repository"]}/raw/main/data/fmcg_prices.parquet'}],
        "dateModified": cube.get("last_run_date"),
    }
    website = {"@type": "WebSite", "@id": f"{base}/#website", "url": f"{base}/",
               "name": "FMCG Price Intelligence", "publisher": {"@id": f"{base}/#organization"},
               "author": {"@id": f"{base}/#person"}}
    node = {"@type": page["type"], "@id": page["url"] + "#page", "url": page["url"], "name": page["title"],
            "headline": page.get("headline", page["title"]), "description": page["description"],
            "isPartOf": {"@id": f"{base}/#website"}, "author": {"@id": f"{base}/#person"},
            "publisher": {"@id": f"{base}/#organization"}, "about": {"@id": f"{base}/#dataset"},
            "image": f"{base}/reports/og-image.png", "inLanguage": "en",
            "datePublished": page.get("published"), "dateModified": cube.get("last_run_date")}
    if page["type"] == "Article":
        node["mainEntityOfPage"] = page["url"]
    clean = lambda d: {k: v for k, v in d.items() if v not in (None, [], {})}
    person["address"] = clean(person["address"])
    if publisher:
        publisher["address"] = clean(publisher["address"])
    nodes = [website, person, org, book, publisher, dataset, node]
    return {"@context": "https://schema.org", "@graph": [clean(x) for x in nodes if x]}


def _head(cfg: dict, base: str, page: dict, cube: dict, icon: str) -> str:
    img = f"{base}/reports/og-image.png"
    ld = json.dumps(_graph(cfg, base, page, cube), ensure_ascii=False, indent=1).replace("</", "<\\/")
    return "\n".join([
        f'<title>{_e(page["title"])}</title>',
        f'<meta name="description" content="{_e(page["description"])}"/>',
        f'<meta name="author" content="{_e(cfg["author"]["name"])}"/>',
        '<meta name="robots" content="index, follow, max-image-preview:large"/>',
        '<meta name="theme-color" content="#0D1C2E"/>',
        f'<link rel="canonical" href="{_e(page["url"])}"/>',
        f'<link rel="icon" type="image/svg+xml" href="{_e(icon)}"/>',
        f'<link rel="author" href="{_e(cfg["author"]["url"])}"/>',
        '<meta property="og:type" content="' + ("article" if page["type"] == "Article" else "website") + '"/>',
        f'<meta property="og:site_name" content="{_e(cfg["organization"]["name"])}"/>',
        f'<meta property="og:title" content="{_e(page["title"])}"/>',
        f'<meta property="og:description" content="{_e(page["description"])}"/>',
        f'<meta property="og:url" content="{_e(page["url"])}"/>',
        f'<meta property="og:image" content="{_e(img)}"/>',
        '<meta property="og:image:width" content="1200"/>',
        '<meta property="og:image:height" content="630"/>',
        f'<meta property="og:image:alt" content="{_e(page["image_alt"])}"/>',
        *([f'<meta property="article:author" content="{_e(cfg["author"]["url"])}"/>',
           f'<meta property="article:published_time" content="{_e(page["published"])}"/>',
           f'<meta property="article:modified_time" content="{_e(cube.get("last_run_date"))}"/>']
          if page["type"] == "Article" else []),
        '<meta name="twitter:card" content="summary_large_image"/>',
        '<meta name="twitter:site" content="@gadielAnalytics"/>',
        '<meta name="twitter:creator" content="@gadielAnalytics"/>',
        f'<meta name="twitter:title" content="{_e(page["title"])}"/>',
        f'<meta name="twitter:description" content="{_e(page["description"])}"/>',
        f'<meta name="twitter:image" content="{_e(img)}"/>',
        f'<script type="application/ld+json">\n{ld}\n</script>',
    ])


def _desc(headline: str, lead: str, limit: int = 160) -> str:
    """Author and brand first, so truncation never cuts the name."""
    d = f"{lead} {headline}."
    if len(d) <= limit:
        return d
    return d[: limit - 1].rsplit(" ", 1)[0] + "…"


def build(config: dict, cube: dict, root: Path = ROOT) -> list[Path]:
    from narrative import fmt_date  # local import keeps site.py importable on its own
    cfg = config["site"]
    base = cfg["base_url"].rstrip("/")
    narr = cube.get("narrative") or {}
    summ, titles = narr.get("summary") or {}, narr.get("titles") or {}
    updated = fmt_date(cube.get("last_run_date"))
    published = cfg.get("case_study_published") or cube.get("last_run_date")
    headline = summ.get("headline") or "Coca-Cola price-pack architecture at SuperValu Ireland"
    alt = "FMCG Price Intelligence by Gadiel Analytics: Coca-Cola full-sugar premium against the sugar levy, by pack"
    written = []

    # dashboard
    dash_url = f"{base}/reports/dashboard.html"
    dash_page = {"type": "WebPage", "url": dash_url,
                 "title": "Coca-Cola vs Pepsi Price Dashboard, Ireland — Gadiel Analytics",
                 "description": _desc(headline, "Live dashboard by Gadiel Guadarrama, Gadiel Analytics:"),
                 "image_alt": alt}
    dv = {"head": _head(cfg, base, dash_page, cube, "favicon.svg"),
          "kicker": _e(summ.get("kicker", "SuperValu Ireland, carbonated soft drinks.")),
          "headline": _e(headline), "dek": _e(summ.get("dek", "")),
          "kpis_html": _kpis_html(summ.get("kpis") or []),
          "messages_html": _messages_html(summ.get("messages") or []), "updated": _e(updated)}
    for k in ["ex1", "exev", "ex2", "ex3", "ex4", "ex5", "ex6", "ex7", "ex8", "ex9"]:
        dv[f"t_{k}"] = _e(titles.get(k, ""))
    out = root / "reports" / "dashboard.html"
    out.write_text(_render((SITE_DIR / "dashboard.html").read_text(encoding="utf-8"), dv), encoding="utf-8")
    written.append(out)

    # case study
    cs_url = f"{base}/"
    cs_page = {"type": "Article", "url": cs_url, "published": published,
               "title": "Coca-Cola vs Pepsi Pricing in Ireland — Gadiel Guadarrama",
               "headline": "How Coca-Cola and Pepsi price soft drinks in Ireland",
               "description": _desc(headline, "Daily shelf-price study by Gadiel Guadarrama, Gadiel Analytics:"),
               "image_alt": alt}
    cv = {"head": _head(cfg, base, cs_page, cube, "reports/favicon.svg"), "headline": _e(headline),
          "kpis_html": _kpis_html(summ.get("kpis") or []),
          "messages_html": _messages_html(summ.get("messages") or [], "reports/dashboard.html"),
          "published": _e(fmt_date(published)), "updated": _e(updated)}
    out = root / "index.html"
    out.write_text(_render((SITE_DIR / "index.html").read_text(encoding="utf-8"), cv), encoding="utf-8")
    written.append(out)

    # crawl hints
    lastmod = cube.get("last_run_date") or ""
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, pr in ((cs_url, "1.0"), (dash_url, "0.9")):
        sm.append(f"  <url><loc>{_e(u)}</loc><lastmod>{_e(lastmod)}</lastmod><changefreq>daily</changefreq>"
                  f"<priority>{pr}</priority></url>")
    sm.append("</urlset>")
    (root / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    (root / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    written += [root / "sitemap.xml", root / "robots.txt"]
    return written
