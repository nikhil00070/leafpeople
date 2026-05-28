#!/usr/bin/env python3
"""Source two unique, on-topic photos for a freshly-generated article.

The problem this solves: the old common.assign_hero() picked from a tiny generic
pool by md5 hash, so new cron articles got mismatched, duplicated images (a Hoya
article showing a Monstera, the same photo on five articles). This sources photos
that actually match the article's subject AND are globally unique across the site.

Strategy:
  1. Determine the iNaturalist query from the article's genus + species (parsed
     from the title). e.g. "Anthurium clarinervium: The ID Gold Standard" → query
     "Anthurium clarinervium".
  2. Query iNat for CC-BY / CC0 photos of that subject (species first, genus
     fallback).
  3. Score candidates by colorfulness x resolution (favor bright, sharp shots).
  4. Pick the top two photo_ids NOT already used anywhere on the site (tracked via
     hero_inat_id / body_image_inat_id stored in every _data.json).
  5. Download, resize to 1800px, save to /images/source/stock/<slug>-hero|body.jpg.

If iNat can't supply two unique usable photos, the article is flagged
"image_needs_review": true in its _data.json and falls back to brand placeholders,
so the human catches it on /review instead of a silent mismatch shipping.
"""

import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

import common

SITE = common.SITE_ROOT
STOCK = SITE / "images" / "source" / "stock"
PLACEHOLDER = "/images/source/p50.jpg"  # brand book-cover shot, obvious stand-in


def used_inat_ids() -> set:
    """Every iNat photo_id already deployed, for global uniqueness."""
    used = set()
    for section in ("the-leaf", "field-guide"):
        for d in (SITE / section).glob("*/_data.json"):
            try:
                dat = json.loads(d.read_text(encoding="utf-8"))
            except Exception:
                continue
            for k in ("hero_inat_id", "body_image_inat_id"):
                if dat.get(k):
                    used.add(int(dat[k]))
    return used


def derive_subject(genus: str, title: str) -> tuple:
    """Return (species_query, genus_query). Parse a species epithet that follows
    the genus in the title, e.g. 'Anthurium clarinervium ...' → ('Anthurium
    clarinervium', 'Anthurium')."""
    genus = (genus or "").strip()
    species_q = genus
    if genus and title:
        m = re.search(rf"{re.escape(genus)}\s+([a-z][a-z\-]+)", title)
        if m:
            species_q = f"{genus} {m.group(1)}"
    return species_q or title, genus or title


def _query(subject: str, per_page: int = 24) -> list:
    url = ("https://api.inaturalist.org/v1/observations"
           f"?taxon_name={urllib.parse.quote(subject)}"
           "&photo_license=cc0,cc-by&order=desc&order_by=votes"
           f"&per_page={per_page}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "leafpeople-img-sourcing"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except Exception:
        return []
    out = []
    seen = set()
    for obs in data.get("results", []):
        for ph in obs.get("photos", []):
            pid = ph.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            u = (ph.get("url") or "").replace("square", "large")
            if u:
                out.append({"photo_id": pid, "url": u,
                            "attribution": ph.get("attribution", "")})
    return out


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "leafpeople-img-sourcing"})
        with urllib.request.urlopen(req, timeout=30) as r:
            dest.write_bytes(r.read())
        return dest.stat().st_size > 0
    except Exception:
        return False


def _score(path: Path) -> float:
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        w, h = im.size
        sat = im.resize((96, 96)).convert("HSV").split()[1].getdata()
        return sum(sat) / len(sat) * math.sqrt(w * h)
    except Exception:
        return 0.0


def _clean_attr(a: str) -> str:
    if not a:
        return ""
    return a.replace("(c) ", "").split(",")[0].strip() + " / iNaturalist (CC BY 4.0)"


def source_for_article(section: str, slug: str, genus: str, title: str) -> dict:
    """Pick + download hero & body. Returns dict of fields to merge into _data.json."""
    from PIL import Image

    STOCK.mkdir(parents=True, exist_ok=True)
    used = used_inat_ids()
    species_q, genus_q = derive_subject(genus, title)

    # Gather candidates: species query first, then genus, dedup by photo_id
    cands, seen = [], set()
    for q in (species_q, genus_q):
        if not q:
            continue
        for c in _query(q):
            if c["photo_id"] in seen or c["photo_id"] in used:
                continue
            seen.add(c["photo_id"])
            cands.append(c)
        if len(cands) >= 6:
            break

    # Download to a temp scoring area, score, keep best two
    tmp = STOCK / ".tmp"
    tmp.mkdir(exist_ok=True)
    scored = []
    for c in cands:
        p = tmp / f"{c['photo_id']}.jpg"
        if _download(c["url"], p):
            scored.append((_score(p), c, p))
    scored.sort(key=lambda x: -x[0])

    result = {}
    roles = [("hero", "hero", "hero_attribution", "hero_inat_id"),
             ("body_image", "body", "body_image_attribution", "body_image_inat_id")]
    for i, (field, short, attr_field, id_field) in enumerate(roles):
        if i < len(scored):
            _, c, src = scored[i]
            dst = STOCK / f"{slug}-{short}.jpg"
            try:
                im = Image.open(src).convert("RGB")
                im.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
                im.save(dst, "JPEG", quality=88)
            except Exception:
                dst.write_bytes(src.read_bytes())
            result[field] = f"/images/source/stock/{slug}-{short}.jpg"
            result[attr_field] = _clean_attr(c["attribution"])
            result[id_field] = c["photo_id"]
        else:
            # not enough unique on-topic photos — placeholder + flag for review
            result[field] = PLACEHOLDER
            result["image_needs_review"] = True

    # cleanup temp
    for f in tmp.glob("*.jpg"):
        f.unlink()
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("usage: source_images.py <section> <slug> <genus> [title...]")
        raise SystemExit(2)
    section, slug, genus = sys.argv[1], sys.argv[2], sys.argv[3]
    title = " ".join(sys.argv[4:]) or genus
    out = source_for_article(section, slug, genus, title)
    print(json.dumps(out, indent=2))
