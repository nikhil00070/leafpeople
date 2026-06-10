#!/usr/bin/env python3
"""Pre-render Instagram-feed-compliant images for the post queue.

Instagram's content-publishing API only accepts feed images whose aspect ratio is
between 4:5 (0.80) and 1.91:1. Our plant photos are tall portraits (~0.63–0.75), so
the raw files 400 the publish call. This renders each post's image onto a 1080x1350
(exactly 4:5) canvas: the full photo is contained (never cropped) and the background is
a blurred, zoomed copy of the same photo, so the frame fills edge-to-edge with no flat
bars. Output lands in images/ig_ready/d{NN}.jpg — committed so it's public via Vercel,
which is what the Graph API fetches.

Usage:
  python3 pipeline/make_post_images.py           # all not-yet-posted days
  python3 pipeline/make_post_images.py 5 40       # days 5..40 inclusive
  python3 pipeline/make_post_images.py 4          # just day 4
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "instagram" / "posts.json"
OUT_DIR = ROOT / "images" / "ig_ready"
CANVAS = (1080, 1350)   # 4:5 — the tallest feed format IG allows


def render(src: Path, dst: Path):
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    # full-bleed: cover-crop to fill the whole 4:5 frame edge-to-edge, no bars, no blur.
    # centering biased slightly above middle so the plant stays and the crop favors the
    # bottom (usually the pot/background).
    out = ImageOps.fit(im, CANVAS, method=Image.LANCZOS, centering=(0.5, 0.45))
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, "JPEG", quality=90, optimize=True, progressive=True)


def main(argv):
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    if len(argv) == 1:
        days = {p["day"] for p in posts if p.get("day") == int(argv[0])}
    elif len(argv) == 2:
        lo, hi = int(argv[0]), int(argv[1])
        days = {d for d in range(lo, hi + 1)}
    else:
        days = {p["day"] for p in posts if p.get("status") != "posted"}

    made, skipped = 0, []
    for p in posts:
        if p.get("day") not in days or not p.get("image"):
            continue
        src = ROOT / p["image"].lstrip("/")
        if not src.exists():
            skipped.append(f"day {p['day']}: missing {p['image']}")
            continue
        dst = OUT_DIR / f"d{p['day']:02d}.jpg"
        render(src, dst)
        made += 1
    print(f"[ig-ready] rendered {made} image(s) to {OUT_DIR.relative_to(ROOT)}")
    for s in skipped:
        print(f"[ig-ready] SKIP {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
