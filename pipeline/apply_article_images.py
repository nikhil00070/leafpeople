#!/usr/bin/env python3
"""Apply chosen body images to Understory articles and re-render them.

Takes a JSON map {slug: image_src} (slug may be "the-leaf/<slug>" or bare "<slug>"), and for
each: sets body_image in _data.json, clears the needs-review flag, and re-renders index.html
(publishing reuses the baked HTML, so re-rendering matters). No Claude, no network — file ops
+ Jinja only.

    python pipeline/apply_article_images.py '{"anthurium-warocqueanum":"/images/plants/profiles/anthurium-veitchii.jpeg"}'
    SELECTIONS='{...}' python pipeline/apply_article_images.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from render import render  # noqa: E402

SKIP = {"hero", "body_image", "og_image", "slug", "hero_attribution", "hero_source_id",
        "body_image_attribution", "body_image_source_id", "image_needs_review"}


def apply_one(slug, body_image):
    slug = slug.split("/")[-1]
    d = os.path.join(ROOT, "the-leaf", slug)
    dp = os.path.join(d, "_data.json")
    if not os.path.exists(dp):
        print(f"  ! {slug}: no _data.json — skipping")
        return False
    if not os.path.exists(os.path.join(ROOT, body_image.lstrip("/"))):
        print(f"  ! {slug}: image {body_image} not found — skipping")
        return False
    data = json.load(open(dp))
    data["body_image"] = body_image
    data["body_image_attribution"] = "Leaf People"
    data.pop("body_image_source_id", None)
    data.pop("image_needs_review", None)
    ctx = {k: v for k, v in data.items() if k not in SKIP}
    html = render("leaf-canonical.html", hero=data.get("hero", ""),
                  og_image=data.get("hero", ""), body_image=body_image, **ctx)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(html)
    open(dp, "w", encoding="utf-8").write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"  ✓ {slug} -> {body_image}")
    return True


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SELECTIONS", "")
    try:
        sel = json.loads(raw)
    except Exception as e:
        print(f"bad selections JSON: {e}")
        return 2
    if not isinstance(sel, dict) or not sel:
        print("no selections — nothing to do")
        return 0
    n = sum(1 for s, src in sel.items() if apply_one(s, src))
    print(f"applied {n}/{len(sel)} body images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
