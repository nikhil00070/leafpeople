#!/usr/bin/env python3
"""Source two on-topic, visually-distinct, globally-unique photos for an article.

Source priority (tuned for rare aroids — Anthurium / Philodendron):
  1. iNaturalist        — PRIMARY for true species. Its `taxon_name` query is
     taxonomically exact (an Anthurium pedatoradiatum query returns actual
     pedatoradiatum observations, vote-ranked = the best collector photos).
     Wikimedia has almost no good photos of rare aroids, so for species we lead
     with iNat. On by default; set LP_ALLOW_INAT=0 to disable.
  2. Wikimedia Commons  — fallback, and the lead source for *cultivars* (e.g.
     Philodendron 'Pink Princess') that iNat does not carry as taxa.
  3. Openverse          — best-effort tertiary (aggregates Flickr etc.); its
     anonymous tier 401s intermittently, so it's a bonus not a dependency.

Pipeline: derive an iNat taxon + a keyword subject from genus+species/cultivar in
the title → gather CC candidates (commercial-OK: CC0 / PDM / CC-BY / CC-BY-SA,
never NC/ND) → drop any whose source-id is already used site-wide → download,
score by colorfulness x resolution → rank species-tier above genus-tier, and
species-exact iNat above keyword matches → hero = best; body = best that's
perceptually distinct from hero. Save to /images/source/stock/<slug>-hero|body.jpg.

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


AROID_GENERA = ("Anthurium", "Philodendron", "Monstera", "Hoya", "Begonia",
                "Alocasia", "Scindapsus", "Epipremnum", "Syngonium",
                "Rhaphidophora", "Caladium", "Aglaonema", "Homalomena", "Amydrium")
# Lowercase words that can follow a genus token but are NOT species epithets.
_NOT_EPITHET = {"care", "and", "the", "for", "versus", "hybrid", "velvet", "giant",
                "true", "dark", "silver", "id", "aff", "sp", "complex", "family",
                "section", "real", "care.", "care,", "vs", "vs.", "or", "x"}


def derive_subject(genus: str, title: str) -> dict:
    """Return {inat, search, genus}:
      inat   = exact 'Genus species' for iNat taxon_name, or None (cultivar / unknown)
      search = best keyword string for Wikimedia/Openverse (includes cultivar name)
      genus  = resolved genus token (from the TITLE first — the-leaf passes a
               hard-coded genus that is often wrong for Philodendron pieces).
    """
    title = title or ""
    genusset = "|".join(AROID_GENERA)
    # 1) explicit binomial in the title -> species-exact (best case)
    m = re.search(rf"\b({genusset})\s+(?:x\s+)?([a-z][a-z\-]{{3,}})\b", title)
    if m and m.group(2) not in _NOT_EPITHET:
        g, sp = m.group(1), m.group(2)
        return {"inat": f"{g} {sp}", "search": f"{g} {sp}", "genus": g}
    # 2) quoted cultivar -> keyword search only (iNat has no cultivar taxa)
    m = re.search(rf"\b({genusset})\s+['‘]([^'’]+)['’]", title)
    if m:
        g, cv = m.group(1), m.group(2).strip()
        return {"inat": None, "search": f"{g} {cv}", "genus": g}
    # 3) capitalised cultivar token (unquoted) -> keyword search only
    m = re.search(rf"\b({genusset})\s+([A-Z][A-Za-z\-]+)", title)
    if m and m.group(2).lower() not in _NOT_EPITHET:
        return {"inat": None, "search": f"{m.group(1)} {m.group(2)}", "genus": m.group(1)}
    # 4) genus only — prefer a genus actually named in the title over passed-in
    g = next((x for x in AROID_GENERA if x.lower() in title.lower()), (genus or "").strip())
    return {"inat": g or None, "search": g or title, "genus": g or (genus or "").strip()}


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
    """Taxon-exact, vote-ranked observations. One photo per observation maximises
    visual diversity (different plants/angles) for distinct hero vs body picks."""
    url = ("https://api.inaturalist.org/v1/observations"
           f"?taxon_name={urllib.parse.quote(subject)}&photo_license=cc0,cc-by"
           "&order=desc&order_by=votes&per_page=30")
    try:
        data = _get(url)
    except Exception:
        return []
    out, seen = [], set()
    for obs in data.get("results", []):
        photos = obs.get("photos") or []
        if not photos:
            continue
        ph = photos[0]                      # lead photo of each observation only
        pid = ph.get("id")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        # square -> large (≈1024px); falls back gracefully if size token differs
        u = (ph.get("url") or "").replace("square", "large")
        if not u:
            continue
        who = (ph.get("attribution") or "").replace("(c) ", "").split(",")[0]
        lic = "CC0" if "cc0" in (ph.get("license_code") or "").lower() else "CC BY 4.0"
        out.append({"id": f"inat-{pid}", "url": u, "source": "inaturalist",
                    "attribution": f"{who} / iNaturalist ({lic})"})
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
    subj = derive_subject(genus, title)
    # iNat on by default for these aroid articles; LP_ALLOW_INAT=0 disables.
    inat_ok = os.environ.get("LP_ALLOW_INAT", "1") != "0"

    # Tier 0 = species/cultivar query, tier 1 = genus fallback. Species-tier
    # candidates ALWAYS beat genus-tier, and within a tier species-EXACT iNat
    # photos beat keyword (Wikimedia/Openverse) matches — a pedatoradiatum
    # article must show pedatoradiatum, not a vivid generic Anthurium.
    cands, seen = [], set()

    def gather(search_q, inat_taxon, tier):
        srcs = []
        if inat_ok and inat_taxon:
            srcs.append(lambda: _inat(inat_taxon))        # FIRST: taxon-exact
        srcs += [lambda: _wikimedia(search_q), lambda: _openverse(search_q)]
        for j, fn in enumerate(srcs):
            if j:
                time.sleep(0.8)
            for c in fn():
                if c["id"] in seen or str(c["id"]) in used:
                    continue
                c["_tier"] = tier
                seen.add(c["id"]); cands.append(c)

    gather(subj["search"], subj["inat"], 0)
    genus_q = subj["genus"]
    if genus_q and genus_q != subj["search"]:
        time.sleep(0.8)
        # genus fallback: iNat taxon = bare genus only when the subject was a true
        # species (so cultivars don't pull generic genus shots into the species tier)
        gather(genus_q, genus_q if subj["inat"] else None, 1)

    tmp = STOCK / ".tmp"
    tmp.mkdir(exist_ok=True)
    scored = []
    for c in cands[:14]:
        p = tmp / f"cand-{abs(hash(c['id']))}.jpg"
        if _download(c["url"], p):
            scored.append((_score(p), c, p))
    # (tier, source) then score: species-tier (0) > genus-tier (1); within a tier,
    # species-exact iNat (src 0) > keyword matches (src 1); then most colorful/hi-res.
    def _rank(x):
        c = x[1]
        src = 0 if c.get("source") == "inaturalist" else 1
        return (c.get("_tier", 0), src, -x[0])
    scored.sort(key=_rank)

    result = {}
    # had_species: a true 'Genus species' binomial was queryable (not a bare genus
    # or cultivar). Required for the quality gate — only species-exact iNat photos
    # are provably the right plant.
    had_species = bool(subj["inat"]) and len(subj["inat"].split()) >= 2

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
        result[f"{field}_src"] = c.get("source")
        result[f"{field}_tier"] = c.get("_tier", 0)

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

    # ---- Quality gate -------------------------------------------------------
    # GOOD only if BOTH hero & body are iNaturalist species-exact (tier 0), real
    # photos of the proven-correct plant, at a decent size and not washed-out.
    # Editorial/genus-only (no species) and Wikimedia keyword scrapes fail here —
    # the caller skips the article entirely rather than ship a wrong/weak image.
    hsat, hshort = 0.0, 0
    if result.get("hero", "").startswith("/images/"):
        try:
            from PIL import Image as _I
            _im = _I.open(STOCK / f"{slug}-hero.jpg").convert("RGB")
            hshort = min(_im.size)
            _s = _im.resize((96, 96)).convert("HSV").split()[1].getdata()
            hsat = sum(_s) / len(_s)
        except Exception:
            pass
    result["hero_sat"] = round(hsat, 1)
    result["hero_short"] = hshort
    reasons = []
    if result.get("image_needs_review"):
        reasons.append("missing/placeholder image")
    if not had_species:
        reasons.append("no species to verify (editorial/genus-only/cultivar)")
    if not (str(result.get("hero_source_id", "")).startswith("inat")
            and str(result.get("body_image_source_id", "")).startswith("inat")):
        reasons.append("hero/body not both iNaturalist")
    if result.get("hero_tier", 1) != 0 or result.get("body_image_tier", 1) != 0:
        reasons.append("fell back to genus-tier")
    if hshort and hshort < 640:
        reasons.append(f"hero too small ({hshort}px)")
    if hsat and hsat < 35:
        reasons.append(f"hero washed-out (sat {hsat:.0f})")
    result["image_ok"] = not reasons
    result["image_reasons"] = reasons

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
