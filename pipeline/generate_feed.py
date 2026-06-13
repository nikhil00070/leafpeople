#!/usr/bin/env python3
"""Build /feed.json — the combined feed of every article, for the app.

Aggregates both section manifests into one public JSON the iOS app polls. Each item
links to the web article (`url`) and to its structured content (`data_url`,
the already-public <slug>/_data.json) so the app can render natively.

ORDER = the curated drip order in articledrip/drip.json (the source of truth for the
sequence stories drip onto the phone's Stories tab). Anything not yet in that list is
appended newest-first at the end, so a freshly-approved article can't jump the queue.
"""

import datetime as dt
import json

import common
import manifest_helpers

BASE = "https://leafpeople.app"
SECTIONS = {"the-leaf": "Understory", "field-guide": "Field Guide"}


def _drip_order() -> dict:
    """slug -> position from articledrip/drip.json (the curated drip sequence)."""
    try:
        drip = json.loads((common.SITE_ROOT / "articledrip" / "drip.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {d["slug"]: i for i, d in enumerate(drip) if d.get("slug")}


def main() -> int:
    items = []
    for path, label in SECTIONS.items():
        for it in manifest_helpers.load(common.SITE_ROOT / path / "manifest.json"):
            # Skip pending (unreviewed) drafts — the iOS feed shouldn't show them.
            if it.get("status", "published") != "published":
                continue
            url = f"{BASE}{it['url']}"
            items.append({
                "id": f"{path}/{it['slug']}",
                "section": path,
                "section_label": label,
                "slug": it["slug"],
                "title": it["title"],
                "category": it.get("category", label),
                "description": it.get("description", ""),
                "date": it.get("date", ""),
                "url": url,
                "data_url": f"{url}/_data.json",
                "image": f"{BASE}{it['thumb']}" if it.get("thumb") else None,
            })
    items.sort(key=lambda i: i.get("date", ""), reverse=True)   # baseline for the un-listed tail
    order = _drip_order()
    if order:
        BIG = 10 ** 9
        items.sort(key=lambda i: order.get(i["slug"], BIG))     # stable: drip order wins; rest keep newest-first
    feed = {
        "site": BASE,
        "title": "Leaf People — Stories",
        "updated": dt.date.today().isoformat(),
        "count": len(items),
        "items": items,
    }
    (common.SITE_ROOT / "feed.json").write_text(
        json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[feed] wrote {len(items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
