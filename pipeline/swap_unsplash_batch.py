#!/usr/bin/env python3
"""Swap in user-picked Unsplash heroes/bodies for batch-two rainforest articles, then re-render.

Resizes each Downloads file to 2400px long-edge, copies into images/source/stock/, rewrites
_data.json (hero/body + attribution + caption), re-renders index+preview, updates manifest thumb.
Idempotent per run. For 'keep_body', preserves the CURRENT hero image as a separate body file
first, so swapping the hero doesn't change the existing inset.
"""
import json, shutil, subprocess, pathlib
import common
from render import render

DL = pathlib.Path.home() / "Downloads"
STOCK = common.SITE_ROOT / "images" / "source" / "stock"
MANIFEST = common.SITE_ROOT / "the-leaf" / "manifest.json"

SWAPS = {
 "rainforest-philippines": {
   "hero_file": "jules-a-VCA83tddQfM-unsplash.jpg", "hero_attr": "Jules A / Unsplash",
   "keep_body": True,   # preserve current Palawan-lagoon inset, only swap the hero
 },
 "rainforest-new-guinea": {
   "hero_file": "amos-tade-SAUCDsjtPAY-unsplash.jpg", "hero_attr": "Amos Tade / Unsplash",
   "body_file": "asso-myron-n1LrwXzsnuU-unsplash.jpg", "body_attr": "Asso Myron / Unsplash",
   "body_caption": "Forested coast and island-studded bay, New Guinea.",
 },
 "rainforest-sumatra": {
   "hero_file": "timo-k-CPbGt4ZHI3Q-unsplash.jpg", "hero_attr": "Timo K / Unsplash",
   "body_file": "irfannur-diah-PquBsLA8tKM-unsplash.jpg", "body_attr": "Irfannur Diah / Unsplash",
   "body_caption": "Lake Toba fills an ancient volcanic caldera, northern Sumatra.",
 },
 "rainforest-madagascar": {
   "hero_file": "sandy-ravaloniaina-xFlKOFnxIIo-unsplash.jpg", "hero_attr": "Sandy Ravaloniaina / Unsplash",
   "body_file": "sandy-ravaloniaina-PQ4a3wTeF9s-unsplash.jpg", "body_attr": "Sandy Ravaloniaina / Unsplash",
   "body_caption": "A brown lemur in eastern Madagascar's rainforest.",
 },
 "rainforest-philippines-body": {   # second pass: swap the body inset, keep jules-a hero
   "slug": "rainforest-philippines",
   "keep_hero": True,
   "body_file": "rommel-paras-wrHnE3kMplg-unsplash.jpg", "body_attr": "Rommel Paras / Unsplash",
   "body_caption": "Karst lagoon at El Nido, Palawan, the Philippines.",
 },
 "rainforest-western-ghats": {
   "keep_hero": True,   # keep the PJeganathan Commons hero, only swap the body inset
   "body_file": "zoshua-colah-yCkFdegGv4M-unsplash.jpg", "body_attr": "Zoshua Colah / Unsplash",
   "body_caption": "Forested Western Ghats hills at golden hour.",
 },
}

def resize_into(src_name, dest):
    src = DL / src_name
    if not src.exists():
        raise SystemExit(f"missing Downloads file: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["sips", "-Z", "2400", str(src), "--out", str(dest)],
                   check=True, capture_output=True)

def apply(slug, cfg):
    slug = cfg.get("slug", slug)   # allow a config keyed differently than its target slug
    ddir = common.SITE_ROOT / "the-leaf" / slug
    art = json.load(open(ddir / "_data.json"))
    hero_rel = f"/images/source/stock/{slug}-hero.jpg"
    body_rel = f"/images/source/stock/{slug}-body.jpg"

    if cfg.get("keep_body"):
        # preserve the current hero image as the body's own file BEFORE overwriting the hero
        cur_hero = STOCK / f"{slug}-hero.jpg"
        shutil.copy(cur_hero, STOCK / f"{slug}-body.jpg")
        art["body_image"] = body_rel   # attribution + caption stay as-is
    elif cfg.get("body_file"):
        resize_into(cfg["body_file"], STOCK / f"{slug}-body.jpg")
        art["body_image"] = body_rel
        art["body_image_attribution"] = cfg["body_attr"]
        if cfg.get("body_caption"):
            art["body_image_caption"] = cfg["body_caption"]

    if cfg.get("keep_hero"):
        hero_rel = art["hero"]   # leave the existing hero + attribution untouched
    else:
        resize_into(cfg["hero_file"], STOCK / f"{slug}-hero.jpg")
        art["hero"] = hero_rel
        art["hero_attribution"] = cfg["hero_attr"]

    content = {k: v for k, v in art.items()
               if k not in ("hero", "body_image", "status", "hero_attribution",
                            "body_image_attribution", "slug", "og_image")}
    rk = dict(hero=hero_rel, og_image=hero_rel, body_image=art["body_image"], slug=slug,
              hero_attribution=art["hero_attribution"],
              body_image_attribution=art.get("body_image_attribution", ""), **content)
    (ddir / "index.html").write_text(render("leaf-canonical.html", gated=False, **rk), encoding="utf-8")
    (ddir / "preview.html").write_text(render("leaf-canonical.html", gated=True, **rk), encoding="utf-8")
    (ddir / "_data.json").write_text(json.dumps(art, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    m = json.load(open(MANIFEST))
    for e in m:
        if e["slug"] == slug:
            e["thumb"] = hero_rel
    json.dump(m, open(MANIFEST, "w"), indent=2, ensure_ascii=False)
    hero_note = "(kept)" if cfg.get("keep_hero") else cfg.get("hero_file", "")[:28]
    body_note = "(kept)" if cfg.get("keep_body") else cfg.get("body_file", "")[:28]
    print(f"  {slug}: hero={hero_note}  body={body_note}")

if __name__ == "__main__":
    import sys
    # keep_body swaps are NOT idempotent (re-running copies the new hero over the body),
    # so default to nothing and require explicit slugs.
    want = sys.argv[1:]
    if not want:
        raise SystemExit("pass slug(s) to swap, e.g. rainforest-madagascar")
    for slug in want:
        apply(slug, SWAPS[slug])
    print("done.")
