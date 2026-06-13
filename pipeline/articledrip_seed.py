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


DRIP_PATH = os.path.join(ROOT, "articledrip", "drip.json")


def _item(a, section, label):
    slug = a.get("slug")
    return {
        "slug": slug,
        "title": a.get("title", slug),
        "category": a.get("category", ""),
        "section": section,
        "section_label": label,
        "url": a.get("url", f"/{section}/{slug}"),
        "thumb": a.get("thumb", ""),
        "date": a.get("date", ""),
        "status": a.get("status", "published"),
    }


def build():
    """Sync articledrip/drip.json with the manifests, PRESERVING the curated order.

    drip.json is the source of truth for the drip sequence, so re-running this never
    reshuffles it. We keep the existing order, refresh each entry's metadata/status from
    the manifest, drop anything rejected/deleted, and APPEND newly-approved articles at
    the end (oldest-first) so they fall to the back of the queue — never jumping the line.
    publish.py calls this on every approval so new articles always flow onto /articledrip.
    """
    # current articles, keyed by slug (slugs are unique across sections — the page assumes this too)
    current = {}
    for section, label in SECTIONS:
        for a in load_manifest(section):
            slug = a.get("slug")
            if not slug or slug in current:
                continue
            current[slug] = _item(a, section, label)

    try:
        existing = json.loads(open(DRIP_PATH).read())
    except Exception:
        existing = []

    result, seen = [], set()
    for a in existing:                              # keep order, refresh from manifest, drop removed
        slug = a.get("slug")
        if slug in current and slug not in seen:
            result.append(current[slug])
            seen.add(slug)
    new = sorted((s for s in current if s not in seen),
                 key=lambda s: (current[s].get("date", ""), current[s]["title"]))
    for s in new:                                   # append newcomers at the back of the queue
        result.append(current[s])

    os.makedirs(os.path.dirname(DRIP_PATH), exist_ok=True)
    json.dump(result, open(DRIP_PATH, "w"), indent=2)

    from collections import Counter
    by_sec = Counter(a["section_label"] for a in result)
    by_status = Counter(a["status"] for a in result)
    print(f"Wrote articledrip/drip.json — {len(result)} stories ({len(new)} newly appended)")
    print(f"  sections: {dict(by_sec)}")
    print(f"  statuses: {dict(by_status)}")


if __name__ == "__main__":
    build()
