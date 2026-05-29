#!/usr/bin/env python3
"""Source two on-topic, visually-distinct, globally-unique photos for an article.

Source priority:
  1. Wikimedia Commons  — RELIABLE (no aggressive anon throttling), has the rare
     species (it's where Openverse's good specimens come from anyway).
  2. Openverse          — best-effort secondary (aggregates Flickr etc.), but its
     anonymous tier 401s intermittently, so it's a bonus not a dependency.
  3. iNaturalist        — last resort, gated behind LP_ALLOW_INAT=1.

Pipeline: derive query from genus+species in the title → gather CC candidates
(commercial-OK: CC0 / PDM / CC-BY / CC-BY-SA, never NC/ND) → drop any whose
source-id is already used site-wide → download, score by colorfulness x
resolution → hero = best; body = best that's perceptually distinct from hero.
Save to /images/source/stock/<slug>-hero|body.jpg.

Fewer than two usable unique photos → image_needs_review=true + placeholder, so
/review catches it.
"""

import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import common

SITE = common.SITE_ROOT
STOCK = SITE / "images" / "source" / "stock"
PLACEHOLDER = "/images/source/p50.jpg"
UA = "leafpeople-img-sourcing/1.0 (hello@percentearth.co)"

ALLOWED_OV = {"cc0", "pdm", "by", "by-sa"}
# Wikimedia titles that are scans/illustrations/specimens, not live plant photos
NOISE = ("chronicle", "catalogue", "catalog", "illustration", "plate", "book",
         "herbarium", "drawing", "engraving", "lithograph", "map", "label",
         "scan", "botanical art", "iconographia")


def used_source_ids() -> set:
    used = set()
    for section in ("the-leaf", "field-guide"):
        for d in (SITE / section).glob("*/_data.json"):
            try:
                dat = json.loads(d.read_text(encoding="utf-8"))
            except Exception:
                continue
            for k in ("hero_source_id", "body_image_source_id",
                      "hero_inat_id", "body_image_inat_id"):
                if dat.get(k):
                    used.add(str(dat[k]))
    return used


def derive_subject(genus: str, title: str) -> tuple:
    genus = (genus or "").strip()
    species_q = genus
    if genus and title:
        m = re.search(rf"{re.escape(genus)}\s+([a-z][a-z\-]+)", title)
        if m:
            species_q = f"{genus} {m.group(1)}"
    return species_q or title, genus or title


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _wikimedia(subject: str, limit: int = 15) -> list:
    """Search Commons File namespace; return live-photo candidates with license."""
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json"
           "&generator=search&gsrnamespace=6"
           f"&gsrsearch={urllib.parse.quote(subject)}&gsrlimit={limit}"
           "&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=1600")
    try:
        data = _get(url)
    except Exception:
        return []
    pages = (data.get("query") or {}).get("pages") or {}
    # Require the genus token in the FILE TITLE — Commons keyword search matches
    # descriptions/categories too, pulling in mislabeled neighbors (e.g. an Aechmea
    # from the same garden batch). Correctly-named plant photos carry the genus in
    # the filename ("Anthurium_regale_1zz.jpg").
    genus_tok = subject.split()[0].lower()
    out = []
    for pid, p in pages.items():
        title = (p.get("title") or "").lower()
        if genus_tok and genus_tok not in title:
            continue
        if any(n in title for n in NOISE):
            continue
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii:
            continue
        thumb = ii.get("thumburl") or ii.get("url") or ""
        if not thumb.split("?")[0].lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        em = ii.get("extmetadata", {}) or {}
        lic = ((em.get("LicenseShortName", {}) or {}).get("value", "") or "")
        ll = lic.lower()
        ok = ("cc0" in ll or "public domain" in ll or "no restrictions" in ll
              or ("cc by" in ll and "nc" not in ll and "nd" not in ll))
        if not ok:
            continue
        artist = re.sub("<[^>]+>", "", (em.get("Artist", {}) or {}).get("value", "") or "").strip()
        artist = (artist or "Wikimedia Commons")[:40]
        out.append({
            "id": f"wmc-{pid}", "url": thumb, "source": "wikimedia",
            "attribution": f"{artist} / Wikimedia Commons ({lic or 'CC'})",
        })
    return out


def _openverse(subject: str, page_size: int = 30) -> list:
    """Best-effort secondary. Anonymous tier 401s a lot — one try, no retry storm."""
    url = ("https://api.openverse.org/v1/images/"
           f"?q={urllib.parse.quote(subject)}&license_type=commercial&page_size={page_size}")
    try:
        data = _get(url)
    except Exception:
        return []
    out = []
    for r in data.get("results", []):
        lic = (r.get("license") or "").lower()
        if lic not in ALLOWED_OV or not r.get("url") or not r.get("id"):
            continue
        src = r.get("source") or "openverse"
        label = {"wikimedia": "Wikimedia Commons", "flickr": "Flickr",
                 "inaturalist": "iNaturalist"}.get(src, src.title())
        ver = (" " + r.get("license_version", "")) if r.get("license_version") else ""
        out.append({
            "id": r["id"], "url": r["url"], "source": src,
            "attribution": f"{r.get('creator') or 'Unknown'} / {label} (CC {lic.upper()}{ver})",
        })
    return out


def _inat(subject: str) -> list:
    url = ("https://api.inaturalist.org/v1/observations"
           f"?taxon_name={urllib.parse.quote(subject)}&photo_license=cc0,cc-by"
           "&order=desc&order_by=votes&per_page=20")
    try:
        data = _get(url)
    except Exception:
        return []
    out, seen = [], set()
    for obs in data.get("results", []):
        for ph in obs.get("photos", []):
            pid = ph.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            u = (ph.get("url") or "").replace("square", "large")
            if u:
                who = (ph.get("attribution") or "").replace("(c) ", "").split(",")[0]
                out.append({"id": f"inat-{pid}", "url": u, "source": "inaturalist",
                            "attribution": f"{who} / iNaturalist (CC BY 4.0)"})
    return out


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            dest.write_bytes(r.read())
        return dest.stat().st_size > 1000
    except Exception:
        return False


def _phash(path, size=12):
    from PIL import Image
    im = Image.open(path).convert("L").resize((size, size), Image.Resampling.LANCZOS)
    px = list(im.getdata()); avg = sum(px) / len(px)
    return [1 if p > avg else 0 for p in px]


def _hamming(a, b):
    return sum(x != y for x, y in zip(a, b))


def _score(path: Path) -> float:
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        w, h = im.size
        sat = im.resize((96, 96)).convert("HSV").split()[1].getdata()
        return sum(sat) / len(sat) * math.sqrt(w * h)
    except Exception:
        return 0.0


def source_for_article(section: str, slug: str, genus: str, title: str) -> dict:
    import os
    from PIL import Image

    STOCK.mkdir(parents=True, exist_ok=True)
    used = used_source_ids()
    species_q, genus_q = derive_subject(genus, title)

    fetchers = [
        lambda: _wikimedia(species_q), lambda: _wikimedia(genus_q),
        lambda: _openverse(species_q), lambda: _openverse(genus_q),
    ]
    if os.environ.get("LP_ALLOW_INAT") == "1":
        fetchers += [lambda: _inat(species_q), lambda: _inat(genus_q)]

    cands, seen = [], set()
    for i, fetch in enumerate(fetchers):
        if i:
            time.sleep(1.0)
        for c in fetch():
            if c["id"] in seen or str(c["id"]) in used:
                continue
            seen.add(c["id"]); cands.append(c)
        if len(cands) >= 8:
            break

    tmp = STOCK / ".tmp"
    tmp.mkdir(exist_ok=True)
    scored = []
    for c in cands[:10]:
        p = tmp / f"cand-{abs(hash(c['id']))}.jpg"
        if _download(c["url"], p):
            scored.append((_score(p), c, p))
    scored.sort(key=lambda x: -x[0])

    result = {}

    def place(field, short, attr_field, id_field, pick):
        _, c, src = pick
        dst = STOCK / f"{slug}-{short}.jpg"
        try:
            im = Image.open(src).convert("RGB")
            im.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
            im.save(dst, "JPEG", quality=88)
        except Exception:
            dst.write_bytes(src.read_bytes())
        result[field] = f"/images/source/stock/{slug}-{short}.jpg"
        result[attr_field] = c["attribution"]
        result[id_field] = c["id"]

    if scored:
        hero = scored[0]
        place("hero", "hero", "hero_attribution", "hero_source_id", hero)
        hero_ph = _phash(hero[2])
        body = next((c for c in scored[1:] if _hamming(hero_ph, _phash(c[2])) > 20), None)
        body = body or (scored[1] if len(scored) > 1 else None)
        if body:
            place("body_image", "body", "body_image_attribution", "body_image_source_id", body)
        else:
            result["body_image"] = PLACEHOLDER
            result["image_needs_review"] = True
    else:
        result.update({"hero": PLACEHOLDER, "body_image": PLACEHOLDER, "image_needs_review": True})

    for f in tmp.glob("*.jpg"):
        f.unlink()
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("usage: source_images.py <section> <slug> <genus> [title...]")
        raise SystemExit(2)
    print(json.dumps(source_for_article(sys.argv[1], sys.argv[2], sys.argv[3],
                                         " ".join(sys.argv[4:]) or sys.argv[3]), indent=2))
