#!/usr/bin/env python3
"""Apply a curated drip order to articledrip/drip.json.

Triggered by the /articledrip "Save order" button (via /api/apply-drip-order →
apply-drip-order.yml). Takes a JSON ORDER = the ordered list of slugs the user arranged
on the page, and rewrites drip.json's array into that exact sequence. drip.json is the
source of truth for the drip, and generate_feed.py builds feed.json (the phone's Stories
feed) in this order — so saving the order here is what re-sequences the live drip.

Items present in drip.json but missing from the posted order are kept and appended at the
end (a safety net; the page normally sends the full list). Unknown slugs are ignored.

    python pipeline/apply_drip_order.py '["anthurium-warocqueanum","monstera-obliqua", ...]'
    ORDER='[{"slug":"..."}, ...]' python pipeline/apply_drip_order.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DRIP_PATH = os.path.join(ROOT, "articledrip", "drip.json")


def main(argv) -> int:
    raw = (argv[0] if argv else os.environ.get("ORDER", "")).strip()
    if not raw:
        print("ERROR: no ORDER provided (argv or ORDER env)", file=sys.stderr)
        return 2
    try:
        posted = json.loads(raw)
    except Exception as e:
        print(f"ERROR: ORDER is not valid JSON: {e}", file=sys.stderr)
        return 2

    # Accept ["slug", ...] or [{"slug": "..."}, ...]
    order = []
    for x in posted:
        slug = x.get("slug") if isinstance(x, dict) else x
        if isinstance(slug, str) and slug:
            order.append(slug)
    if not order:
        print("ERROR: ORDER had no usable slugs", file=sys.stderr)
        return 2

    drip = json.loads(open(DRIP_PATH).read())
    by_slug = {a.get("slug"): a for a in drip if a.get("slug")}

    result, seen = [], set()
    for slug in order:                       # the curated sequence
        a = by_slug.get(slug)
        if a and slug not in seen:
            result.append(a)
            seen.add(slug)
    for a in drip:                           # safety: keep anything the page didn't send
        slug = a.get("slug")
        if slug and slug not in seen:
            result.append(a)
            seen.add(slug)

    json.dump(result, open(DRIP_PATH, "w"), indent=2)
    print(f"[drip-order] wrote articledrip/drip.json — {len(result)} stories "
          f"({len(order)} from posted order, {len(result) - len(seen & set(order))} appended)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
