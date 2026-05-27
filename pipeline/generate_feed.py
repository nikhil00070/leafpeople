#!/usr/bin/env python3
"""Build /feed.json — a combined, newest-first feed of every article, for the app.

Aggregates both section manifests into one public JSON the iOS app polls. Each item
links to the web article (`url`) and to its structured content (`data_url`,
the already-public <slug>/_data.json) so the app can render natively.
"""

import datetime as dt
import json

import common
import manifest_helpers

BASE = "https://leafpeople.app"
SECTIONS = {"the-leaf": "Understory", "field-guide": "Field Guide"}


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
    items.sort(key=lambda i: i.get("date", ""), reverse=True)
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
