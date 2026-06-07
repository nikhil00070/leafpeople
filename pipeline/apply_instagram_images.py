#!/usr/bin/env python3
"""
apply_instagram_images.py — persist the /instagram picker's curated image choices
into instagram/posts.json so the auto-poster (post_to_instagram.py) posts your
hand-picked images instead of the seeded defaults.

Triggered by the apply-instagram-images.yml workflow (via /api/apply-ig-images),
which passes a JSON map {post_id: image_src} as argv[1]. Mirrors
apply_article_images.py. Writes with indent=2 (no ensure_ascii) to match the
seed's format, so the diff is only the image fields that actually changed.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
POSTS = os.path.join(ROOT, "instagram", "posts.json")


def main():
    if len(sys.argv) < 2:
        print("usage: apply_instagram_images.py '<selections-json>'")
        sys.exit(1)
    try:
        sel = json.loads(sys.argv[1])
    except Exception as e:
        print(f"bad selections JSON: {e}")
        sys.exit(1)
    try:
        pos = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    except Exception as e:
        print(f"bad positions JSON: {e}")
        pos = {}
    if not isinstance(sel, dict):
        sel = {}
    if not isinstance(pos, dict):
        pos = {}
    if not sel and not pos:
        print("no selections or positions — nothing to do")
        return

    posts = json.loads(open(POSTS).read())
    by_id = {p.get("id"): p for p in posts}

    applied, framed, missing = 0, 0, 0
    for pid, src in sel.items():
        post = by_id.get(pid)
        if not post:
            missing += 1
            continue
        if isinstance(src, str) and src and post.get("image") != src:
            post["image"] = src
            applied += 1
    for pid, p in pos.items():
        post = by_id.get(pid)
        if not post:
            continue
        if isinstance(p, str) and p and post.get("imgPos") != p:
            post["imgPos"] = p
            framed += 1

    json.dump(posts, open(POSTS, "w"), indent=2)
    print(f"applied {applied} image choice(s) + {framed} framing(s) across {len(posts)} posts"
          f"{f' ({missing} unknown id(s) skipped)' if missing else ''}")


if __name__ == "__main__":
    main()
