#!/usr/bin/env python3
"""Rebuild sitemap.xml from the section manifests and the static top-level pages."""

import datetime as dt

import common
import manifest_helpers

BASE = "https://leafpeople.app"  # update to the production domain
TODAY = dt.date.today().isoformat()

STATIC = ["/", "/the-leaf", "/field-guide", "/privacy", "/support"]


def url(loc: str, lastmod: str) -> str:
    return f"  <url>\n    <loc>{BASE}{loc}</loc>\n    <lastmod>{lastmod}</lastmod>\n  </url>"


def main() -> int:
    entries = [url(p, TODAY) for p in STATIC]

    for section in ("the-leaf", "field-guide"):
        manifest = common.SITE_ROOT / section / "manifest.json"
        for item in manifest_helpers.load(manifest):
            # Skip pending (unreviewed) drafts — keep them out of SEO until human approves.
            if item.get("status", "published") != "published":
                continue
            entries.append(url(item["url"], item.get("date", TODAY)))

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
    (common.SITE_ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")
    print(f"[sitemap] wrote {len(entries)} urls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
