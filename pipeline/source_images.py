#!/usr/bin/env python3
"""Source two on-topic, visually-distinct, globally-unique photos for a new article.

Primary source is Openverse (api.openverse.org), which aggregates CC-licensed
images from Wikimedia Commons, Flickr, iNaturalist, the Smithsonian and more.
For cultivated collector plants this beats iNaturalist-only by a wide margin
(e.g. "Anthurium clarinervium": Openverse has ~19 real specimens, iNat has 4
that are mostly misIDed or show flowers). iNat is kept as a fallback.

Pipeline:
  1. Derive the query from genus + species parsed from the title.
  2. Pull Openverse candidates (commercial-use licenses: CC0 / BY / BY-SA),
     species query first then genus.
  3. Drop any whose source-id is already used anywhere on the site.
  4. Download, score by colorfulness x resolution, pick the best as hero; pick
     the best-scoring BODY that is also perceptually distinct from the hero
     (so hero/body aren't the same plant from one angle).
  5. Save to /images/source/stock/<slug>-hero|body.jpg, return fields for
     _data.json including attribution + a stable source-id for future dedup.

If fewer than two usable unique photos turn up, sets image_needs_review=true +
a placeholder so the human catches it on /review.
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

# Allowed licenses (commercial-OK). Lower rank = cleaner, but we optimize for
# photo QUALITY first since all of these are acceptable for editorial display.
ALLOWED = {"cc0", "pdm", "by", "by-sa"}
SOURCE_LABEL = {
    "wikimedia": "Wikimedia Commons", "flickr": "Flickr", "inaturalist": "iNaturalist",
    "smithsonian_national_museum_of_natural_history": "Smithsonian", "rawpixel": "Rawpixel",
}


def used_source_ids() -> set:
    """Every image source-id already deployed (Openverse ids + legacy iNat ids)."""
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
    """('Anthurium clarinervium: ...', genus='Anthurium') → ('Anthurium clarinervium', 'Anthurium')."""
    genus = (genus or "").strip()
    species_q = genus
    if genus and title:
        m = re.search(rf"{re.escape(genus)}\s+([a-z][a-z\-]+)", title)
        if m:
            species_q = f"{genus} {m.group(1)}"
    return species_q or title, genus or title


def _openverse(subject: str, page_size: int = 30, retries: int = 4) -> list:
    """Query Openverse. Anonymous access has a tight burst limit, so retry on
    429 with backoff before giving up (and falling through to iNat)."""
    url = ("https://api.openverse.org/v1/images/"
           f"?q={urllib.parse.quote(subject)}&license_type=commercial&page_size={page_size}")
    data = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "leafpeople-img-sourcing"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(2 + 2 * attempt)  # 2s, 4s, 6s
                continue
            return []
        except Exception:
            return []
    if data is None:
        return []
    out = []
    for r in data.get("results", []):
        lic = (r.get("license") or "").lower()
        if lic not in ALLOWED:
            continue
        if not r.get("url") or not r.get("id"):
            continue
        out.append({
            "id": r["id"], "url": r["url"], "license": lic,
            "version": r.get("license_version", ""),
            "creator": r.get("creator") or "Unknown",
            "source": r.get("source") or "",
        })
    return out


def _inat_fallback(subject: str) -> list:
    """iNat CC-BY/CC0, used only if Openverse comes up short."""
    url = ("https://api.inaturalist.org/v1/observations"
           f"?taxon_name={urllib.parse.quote(subject)}&photo_license=cc0,cc-by"
           "&order=desc&order_by=votes&per_page=20")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "leafpeople-img-sourcing"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
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
                out.append({"id": f"inat-{pid}", "url": u, "license": "by",
                            "version": "4.0", "creator": (ph.get("attribution") or "").replace("(c) ", "").split(",")[0],
                            "source": "inaturalist"})
    return out


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 leafpeople-img-sourcing"})
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


def _attr(c: dict) -> str:
    label = SOURCE_LABEL.get(c["source"], (c["source"] or "source").replace("_", " ").title())
    lic = c["license"].upper()
    ver = (" " + c["version"]) if c["version"] else ""
    return f"{c['creator']} / {label} (CC {lic}{ver})".strip()


def source_for_article(section: str, slug: str, genus: str, title: str) -> dict:
    from PIL import Image

    STOCK.mkdir(parents=True, exist_ok=True)
    used = used_source_ids()
    species_q, genus_q = derive_subject(genus, title)

    # Gather candidates: Openverse species → Openverse genus → iNat fallback
    cands, seen = [], set()
    # Openverse only (per project decision — iNat gave too many misID'd/flower
    # shots). _inat_fallback is kept in the module but intentionally unused; set
    # LP_ALLOW_INAT=1 to re-enable it as a last resort.
    fetchers = [lambda: _openverse(species_q), lambda: _openverse(genus_q)]
    import os as _os
    if _os.environ.get("LP_ALLOW_INAT") == "1":
        fetchers += [lambda: _inat_fallback(species_q), lambda: _inat_fallback(genus_q)]
    for i, fetch in enumerate(fetchers):
        if i:
            time.sleep(1.5)  # space calls so Openverse doesn't 429
        for c in fetch():
            if c["id"] in seen or str(c["id"]) in used:
                continue
            seen.add(c["id"]); cands.append(c)
        if len(cands) >= 10:
            break

    # Download + score
    tmp = STOCK / ".tmp"
    tmp.mkdir(exist_ok=True)
    scored = []
    for c in cands[:12]:
        p = tmp / f"cand-{abs(hash(c['id']))}.jpg"
        if _download(c["url"], p):
            scored.append((_score(p), c, p))
    scored.sort(key=lambda x: -x[0])  # quality first

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
        result[attr_field] = _attr(c)
        result[id_field] = c["id"]

    if scored:
        hero = scored[0]
        place("hero", "hero", "hero_attribution", "hero_source_id", hero)
        # body: best-scoring candidate perceptually DISTINCT from hero
        hero_ph = _phash(hero[2])
        body = None
        for cand in scored[1:]:
            if _hamming(hero_ph, _phash(cand[2])) > 20:  # visually different
                body = cand; break
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
    section, slug, genus = sys.argv[1], sys.argv[2], sys.argv[3]
    title = " ".join(sys.argv[4:]) or genus
    print(json.dumps(source_for_article(section, slug, genus, title), indent=2))
