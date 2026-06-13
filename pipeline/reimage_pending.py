#!/usr/bin/env python3
"""Re-source on-topic photos for PENDING review-queue articles and re-render.

Field-guide articles already query by genus/species and get real plant photos.
The Understory editorial pieces have no species, so the sourcer fell back to the
abstract title → irrelevant or placeholder images. Here we assign each editorial
piece a fitting rare-aroid subject, re-source a real CC photo, update _data.json,
re-render index.html (publishing reuses the baked HTML, so this matters), and
refresh the manifest thumb. Runs sequentially so the site-wide source-id dedup
picks distinct photos. No Claude — images only.

    python reimage_pending.py                 # all pending in both sections
    python reimage_pending.py the-leaf/collector-burnout field-guide/anthurium-splendidum
"""

import json
import sys
from pathlib import Path

import common
import manifest_helpers
import source_images
from render import render

SITE = common.SITE_ROOT
PLACEHOLDER = source_images.PLACEHOLDER

# Editorial (Understory) pieces have no species — give each a distinct, photogenic
# rare aroid that fits the theme. "Genus species"; genus (first word) also drives
# the sourcer's genus-level fallback for the body image.
EDITORIAL_SUBJECT = {
    "repotting-mature-anthuriums":          "Anthurium veitchii",
    "fertilizer-for-slow-growers":          "Anthurium clarinervium",
    "the-post-flush-rest":                  "Philodendron gloriosum",
    "instagram-after-the-fomo":             "Anthurium crystallinum",
    "collector-burnout":                    "Monstera deliciosa",
    "heritage-clones-and-provenance":       "Philodendron melanochrysum",
    "meeting-the-grower-in-person":         "Anthurium regale",
    "the-serious-private-collection":       "Anthurium warocqueanum",
    "auctions-versus-dm-sales":             "Philodendron verrucosum",
    "the-broker-economy":                   "Anthurium magnificum",
    "tissue-culture-and-the-rarity-premium":"Monstera adansonii",
    "export-licenses-what-they-protect":    "Anthurium forgetii",
    "the-cuttings-resale-market":           "Philodendron hederaceum",
}


def pending(section: str) -> list:
    m = json.loads((SITE / section / "manifest.json").read_text(encoding="utf-8"))
    return [e["slug"] for e in m if e.get("status") == "pending"]


def reimage(section: str, slug: str) -> bool:
    post = SITE / section / slug
    data = json.loads((post / "_data.json").read_text(encoding="utf-8"))

    if section == "field-guide":
        genus, title = data.get("genus", ""), data.get("title", slug)
    else:
        subject = EDITORIAL_SUBJECT.get(slug)
        if not subject:
            print(f"  [skip] {slug}: no editorial subject mapped"); return False
        genus, title = subject.split()[0], subject

    print(f"[reimage] {section}/{slug}  ← '{title}'")
    res = source_images.source_for_article(section, slug, genus, title)
    hero = res.get("hero")
    if not hero or hero == PLACEHOLDER:
        print(f"  [fail] no usable photo found for '{title}' — left as-is")
        return False

    body = res.get("body_image") or hero
    # Merge image fields into the article data.
    data["hero"] = hero
    data["body_image"] = body
    for k in ("hero_attribution", "body_image_attribution",
              "hero_source_id", "body_image_source_id"):
        if res.get(k):
            data[k] = res[k]
    data.pop("image_needs_review", None) if not res.get("image_needs_review") else None

    # Re-render the draft HTML from the (text-unchanged) data + new images.
    ctx = {k: v for k, v in data.items() if k not in ("hero", "og_image", "body_image")}
    template = "leaf-canonical.html" if section == "the-leaf" else "guide-canonical.html"
    html = render(template, hero=hero, og_image=hero, body_image=body, **ctx)
    (post / "index.html").write_text(html, encoding="utf-8")

    (post / "_data.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Keep the manifest thumb in sync (listing + review thumbnails).
    manifest = SITE / section / "manifest.json"
    for e in (m := manifest_helpers.load(manifest)):
        if e.get("slug") == slug:
            e["thumb"] = hero
    manifest.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"  [ok] hero={hero}  body={body}")
    print(f"       {res.get('hero_attribution','')}")
    return True


def main() -> int:
    targets = []
    if len(sys.argv) > 1:
        for a in sys.argv[1:]:
            sec, sl = a.split("/", 1)
            targets.append((sec, sl))
    else:
        for sec in ("the-leaf", "field-guide"):
            targets += [(sec, s) for s in pending(sec)]

    ok = 0
    for sec, sl in targets:
        try:
            ok += 1 if reimage(sec, sl) else 0
        except Exception as e:
            print(f"  [error] {sec}/{sl}: {e}")
    print(f"\nDone: {ok}/{len(targets)} re-imaged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
