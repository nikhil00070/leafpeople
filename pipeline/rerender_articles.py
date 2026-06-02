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

SECTIONS = {"the-leaf": "leaf-canonical.html", "field-guide": "guide-canonical.html"}
SKIP = {"hero", "og_image", "body_image", "slug"}


def main():
    n = 0
    for sec, tpl in SECTIONS.items():
        for dp in sorted(glob.glob(os.path.join(ROOT, sec, "*", "_data.json"))):
            data = json.load(open(dp))
            ctx = {k: v for k, v in data.items() if k not in SKIP}
            html = render(tpl, hero=data.get("hero", ""), og_image=data.get("hero", ""),
                          body_image=data.get("body_image", ""), **ctx)
            open(os.path.join(os.path.dirname(dp), "index.html"), "w", encoding="utf-8").write(html)
            n += 1
    print(f"re-rendered {n} articles")


if __name__ == "__main__":
    main()
