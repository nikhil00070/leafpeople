#!/usr/bin/env python3
"""Build the candidate image pool for the article body-image curation page.

Writes the-leaf/image-pool.json — a clean list of GOOD plant photos to choose body images
from: the app's 68 plant-profile shots, the head-to-head ID shots, and the curated mood
photos. Deliberately EXCLUDES the iNaturalist stock heroes (the weak/irrelevant ones the
auto-sourcer used). Each entry: {src, genus, label}.
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERA = ("anthurium", "philodendron", "monstera", "hoya", "begonia")


def genus_of(base):
    for g in GENERA:
        if base.startswith(g):
            return g.capitalize()
    return "Other"


def label_of(base):
    return base.replace("lp-", "").replace("-", " ").replace("_", " ").strip().title()


def main():
    pool, seen = [], set()

    def add(src, suffix=""):
        base = os.path.splitext(os.path.basename(src))[0]
        if base in seen:
            return
        seen.add(base)
        pool.append({"src": src, "genus": genus_of(base), "label": label_of(base) + suffix})

    # app plant-profile photos (canonical, best) — one clean shot per species
    for f in sorted(glob.glob(os.path.join(ROOT, "images/plants/profiles/*"))):
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            add("/" + os.path.relpath(f, ROOT))
    # head-to-head ID shots
    for f in sorted(glob.glob(os.path.join(ROOT, "images/compare/lp-*.png"))):
        add("/" + os.path.relpath(f, ROOT), " · leaf")
    # curated mood / general foliage shots
    for f in sorted(glob.glob(os.path.join(ROOT, "images/plants/*"))):
        if os.path.isfile(f) and f.lower().endswith((".jpg", ".jpeg", ".png")):
            add("/" + os.path.relpath(f, ROOT))

    out = os.path.join(ROOT, "the-leaf", "image-pool.json")
    json.dump(pool, open(out, "w"), indent=2)
    by_genus = {}
    for e in pool:
        by_genus[e["genus"]] = by_genus.get(e["genus"], 0) + 1
    print(f"wrote {out} — {len(pool)} images:", by_genus)


if __name__ == "__main__":
    main()
