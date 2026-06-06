#!/usr/bin/env python3
"""
articledrip_seed.py — build the article drip queue for /articledrip.

The app's Stories section reveals one story at a time to a reader, dripping them in
over the first weeks after install (day 1, day 3, day 5 …). This generates the DEFAULT
order of that drip from the published + pending article manifests, so it can be reviewed
and re-ordered on the /articledrip page. The finalized order then drives the real drip.

Writes:
  articledrip/drip.json — every Stories article (the-leaf Understory + field-guide Field
                          Guide), in default drip order. The page lets you drag/re-order;
                          the chosen order is saved in localStorage (Phase 1, like /instagram).

Re-run any time to pick up newly added articles — the page appends anything new to the end
of your saved order, so a re-seed never disturbs an order you've already curated.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SECTIONS = [
    ("the-leaf", "Understory"),
    ("field-guide", "Field Guide"),
]


def load_manifest(section):
    path = os.path.join(ROOT, section, "manifest.json")
    try:
        d = json.loads(open(path).read())
    except Exception:
        return []
    return d if isinstance(d, list) else d.get("items", [])


def build():
    items = []
    seen = set()
    for section, label in SECTIONS:
        for a in load_manifest(section):
            slug = a.get("slug")
            if not slug or slug in seen:
                continue
            seen.add(slug)
            items.append({
                "slug": slug,
                "title": a.get("title", slug),
                "category": a.get("category", ""),
                "section": section,
                "section_label": label,
                "url": a.get("url", f"/{section}/{slug}"),
                "thumb": a.get("thumb", ""),
                "date": a.get("date", ""),
                "status": a.get("status", "published"),
            })

    # Default drip order = the Stories FEED order (exactly what the app shows via feed.json),
    # then anything not in the feed (pending/unpublished) appended after by date. Just the
    # starting point; /articledrip lets you reorder freely and remembers your sequence.
    feed_order = {}
    try:
        fd = json.loads(open(os.path.join(ROOT, "feed.json")).read())
        fitems = fd.get("items", fd) if isinstance(fd, dict) else fd
        feed_order = {a.get("slug"): i for i, a in enumerate(fitems) if a.get("slug")}
    except Exception:
        feed_order = {}
    items.sort(key=lambda a: (feed_order.get(a["slug"], 10_000), a.get("date", ""), a["title"]))

    out_dir = os.path.join(ROOT, "articledrip")
    os.makedirs(out_dir, exist_ok=True)
    json.dump(items, open(os.path.join(out_dir, "drip.json"), "w"), indent=2)

    from collections import Counter
    by_sec = Counter(a["section_label"] for a in items)
    by_status = Counter(a["status"] for a in items)
    print(f"Wrote articledrip/drip.json — {len(items)} stories")
    print(f"  sections: {dict(by_sec)}")
    print(f"  statuses: {dict(by_status)}")


if __name__ == "__main__":
    build()
