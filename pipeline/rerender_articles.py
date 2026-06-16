#!/usr/bin/env python3
"""Re-render all article HTML from their _data.json (no API, no network).

Picks up template changes — notably the "📷 credit" lines now shown for any image whose
attribution isn't "Leaf People". Owned images show no credit. Run after editing a template.

    python pipeline/rerender_articles.py
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from render import render  # noqa: E402
import seo_links  # noqa: E402

SECTIONS = {"the-leaf": "leaf-canonical.html", "field-guide": "guide-canonical.html"}
SKIP = {"hero", "og_image", "body_image", "slug"}


def main():
    link_map = seo_links.build_link_map()
    n, linked_total = 0, 0
    for sec, tpl in SECTIONS.items():
        for dp in sorted(glob.glob(os.path.join(ROOT, sec, "*", "_data.json"))):
            data = json.load(open(dp))
            ctx = {k: v for k, v in data.items() if k not in SKIP}
            d = os.path.dirname(dp)
            slug = os.path.basename(d)
            self_url = f"/{sec}/{slug}"
            kw, about, mentions = seo_links.article_entities(slug, sec, data, link_map)
            common = dict(hero=data.get("hero", ""), og_image=data.get("hero", ""),
                          body_image=data.get("body_image", ""), slug=slug,
                          keywords=kw, about=about, mentions=mentions, **ctx)  # slug drives canonical/JSON-LD URLs
            # Full article (subscribers) + paywalled preview (everyone else / crawlers). After
            # rendering, auto-link first-mention species to their canonical pages (SEO/AEO).
            for fn, gated in (("index.html", False), ("preview.html", True)):
                html, linked = seo_links.linkify_html(render(tpl, gated=gated, **common), self_url, link_map)
                open(os.path.join(d, fn), "w", encoding="utf-8").write(html)
                if not gated:
                    linked_total += len(linked)
            n += 1
    print(f"re-rendered {n} articles (full + preview); {linked_total} in-body species links added")


if __name__ == "__main__":
    main()
