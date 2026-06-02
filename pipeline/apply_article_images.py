#!/usr/bin/env python3
"""Apply chosen hero/body images to Understory articles and re-render them.

Takes a JSON map {slug: {"hero": src, "body": src}} (either key optional; slug may be
"the-leaf/<slug>" or bare). For each chosen image:
  * local /images/... path  -> used as-is, attribution "Leaf People"
  * iNaturalist photo URL    -> downloaded to images/source/inat/<slug>[-hero].jpg, attributed
For the BODY a visible "📷 photographer" credit is appended to the caption (CC-BY). When the
HERO changes, the manifest thumbnail is updated too. Re-renders index.html.

No Claude. Network only when an iNat URL is chosen (to download it).

    python pipeline/apply_article_images.py '{"anthurium-crystalanium":{"body":"https://.../large.jpg"}}'
    SELECTIONS='{...}' python pipeline/apply_article_images.py
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from render import render  # noqa: E402

SKIP = {"hero", "body_image", "og_image", "slug", "hero_attribution", "hero_source_id",
        "body_image_attribution", "body_image_source_id", "image_needs_review"}
MANIFEST = os.path.join(ROOT, "the-leaf", "manifest.json")


def inat_map():
    try:
        data = json.load(open(os.path.join(ROOT, "the-leaf", "inat-options.json")))
    except Exception:
        return {}
    return {o["src"]: o for opts in data.values() for o in opts}


def download(url, dest_rel):
    dest = os.path.join(ROOT, dest_rel.lstrip("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "leafpeople-curation"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest_rel


def base_caption(cap):
    return (cap or "").split(" — \U0001F4F7")[0]


def resolve(slug, src, imap, suffix):
    """Return (local_src, attribution) for a chosen image, downloading iNat URLs."""
    if src.startswith("http"):
        meta = imap.get(src, {})
        local = download(src, f"/images/source/inat/{slug}{suffix}.jpg")
        attrib = meta.get("label", "iNaturalist")
        return local, f"{attrib} / iNaturalist ({meta.get('license', 'CC').upper()})", attrib
    if not os.path.exists(os.path.join(ROOT, src.lstrip("/"))):
        raise FileNotFoundError(src)
    return src, "Leaf People", ""


def update_manifest_thumb(slug, hero):
    try:
        m = json.load(open(MANIFEST))
    except Exception:
        return
    for e in m:
        if e.get("slug") == slug:
            e["thumb"] = hero
    open(MANIFEST, "w", encoding="utf-8").write(json.dumps(m, indent=2, ensure_ascii=False) + "\n")


def apply_one(slug, sel, imap):
    slug = slug.split("/")[-1]
    d = os.path.join(ROOT, "the-leaf", slug)
    dp = os.path.join(d, "_data.json")
    if not os.path.exists(dp):
        print(f"  ! {slug}: no _data.json — skipping")
        return False
    data = json.load(open(dp))
    changed = []

    if sel.get("body"):
        try:
            local, attrib_full, name = resolve(slug, sel["body"], imap, "")
        except Exception as e:
            print(f"  ! {slug}: body image failed ({e})")
        else:
            data["body_image"] = local
            data["body_image_attribution"] = attrib_full
            data.pop("body_image_source_id", None)
            cap = base_caption(data.get("body_image_caption", ""))
            data["body_image_caption"] = (f"{cap} — \U0001F4F7 {name}".strip(" —") if name else cap)
            changed.append("body")

    if sel.get("hero"):
        try:
            local, attrib_full, _ = resolve(slug, sel["hero"], imap, "-hero")
        except Exception as e:
            print(f"  ! {slug}: hero image failed ({e})")
        else:
            data["hero"] = local
            data["hero_attribution"] = attrib_full
            data.pop("hero_source_id", None)
            update_manifest_thumb(slug, local)
            changed.append("hero")

    if not changed:
        return False
    data.pop("image_needs_review", None)
    ctx = {k: v for k, v in data.items() if k not in SKIP}
    html = render("leaf-canonical.html", hero=data.get("hero", ""),
                  og_image=data.get("hero", ""), body_image=data.get("body_image", ""), **ctx)
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(html)
    open(dp, "w", encoding="utf-8").write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"  ✓ {slug}: {'+'.join(changed)}")
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
    imap = inat_map()
    n = 0
    for slug, choice in sel.items():
        if isinstance(choice, str):       # back-compat: bare string == body
            choice = {"body": choice}
        if isinstance(choice, dict) and apply_one(slug, choice, imap):
            n += 1
    print(f"applied {n}/{len(sel)} articles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
