#!/usr/bin/env python3
"""First-pass hero + body images for the Botanical Tour series from Wikimedia Commons (freely licensed).

Hero = a photo of the actual conservatory/glasshouse. Body = the on-theme plant named in each
article's body_image_caption. Downloads, sets attribution, rewrites _data.json + index/preview,
updates the manifest thumb. The user overwrites any pick with a better one during review.

    python source_conservatory_images.py [slug ...]     # default: all
"""
import sys, json, re, urllib.parse, urllib.request
import common
from render import render

STOCK = common.SITE_ROOT / "images" / "source" / "stock"
MANIFEST = common.SITE_ROOT / "the-leaf" / "manifest.json"
UA = {"User-Agent": "LeafPeople/1.0 (https://leafpeople.app; contact@leafpeople.app)"}

# per-slug: hero query (the building) + body query (the plant from the caption) + whether hero must be landscape
JOBS = {
 "conservatory-kew":                 ("Palm House Kew Gardens interior",          "Amorphophallus titanum inflorescence"),
 "conservatory-eden-project":        ("Eden Project Cornwall biome",              "Monstera deliciosa plant"),
 "conservatory-berlin-tropenhaus":   ("Grosses Tropenhaus Botanischer Garten Berlin", "Monstera deliciosa greenhouse"),
 "conservatory-cloud-forest-singapore":("Cloud Forest Gardens by the Bay waterfall","Nepenthes pitcher plant"),
 "conservatory-amazon-spheres":      ("Amazon Spheres Seattle",                   "epiphyte orchid branch"),
 "conservatory-marie-selby":         ("Marie Selby Botanical Gardens",            "Tillandsia epiphyte"),
 "conservatory-climatron":           ("Climatron Missouri Botanical Garden",      "Anthurium leaves"),
 "conservatory-haupt-nybg":          ("Enid Haupt Conservatory New York Botanical Garden", "Monstera deliciosa leaves"),
 "conservatory-flowers-sf":          ("Conservatory of Flowers San Francisco",    "Philodendron plant"),
 "conservatory-ntbg-kauai":          ("Allerton Garden Kauai",                    "Anthurium plant leaf"),
 "conservatory-hawaii-tropical":     ("Hawaii Tropical Botanical Garden Onomea",  "Anthurium plant"),
 "conservatory-nong-nooch":          ("Nong Nooch Tropical Garden",               "Platycerium staghorn fern"),
 "conservatory-rio-de-janeiro":      ("Jardim Botanico Rio de Janeiro palm avenue","Roystonea royal palm avenue"),
 "conservatory-adelaide":            ("Bicentennial Conservatory Adelaide",       "Monstera deliciosa plant"),
 "conservatory-copenhagen":          ("Palm House Botanical Garden Copenhagen",   "Livistona palm fronds"),
 "conservatory-bogor":               ("Kebun Raya Bogor botanical garden",        "Amorphophallus titanum bloom"),
}

BAD = re.compile(r"\bmap\b|diagram|logo|plan of|floorplan|satellite|chart|poster|ticket|graph|sign\b", re.I)

def search(q, n=15, need_landscape=True, min_w=1200):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action":"query","generator":"search","gsrsearch":q,"gsrnamespace":"6","gsrlimit":str(n),
        "prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":"1600","format":"json"})
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))
    except Exception as e:
        print("   search error:", e); return []
    pages = ((d.get("query") or {}).get("pages") or {}).values()
    cands = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        u = ii.get("url",""); t = p.get("title","")
        if not u.lower().endswith((".jpg",".jpeg")): continue
        if BAD.search(t): continue
        w,h = ii.get("width",0), ii.get("height",0)
        if w < min_w: continue
        if need_landscape and w <= h: continue
        meta = ii.get("extmetadata") or {}
        artist = re.sub(r"<[^>]+>","", (meta.get("Artist") or {}).get("value","")).strip() or "Wikimedia Commons"
        lic = (meta.get("LicenseShortName") or {}).get("value","")
        score = (1 if w >= 2400 else 0)
        cands.append({"title":t,"thumb":ii.get("thumburl") or u,"w":w,"artist":artist[:60],"license":lic,"score":score})
    cands.sort(key=lambda c: -c["score"])
    return cands

def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        path.write_bytes(r.read())

def wire(slug, hero_q, body_q):
    hero = (search(hero_q, need_landscape=True) or search(hero_q, need_landscape=False))
    body = (search(body_q, need_landscape=False) or search(body_q, need_landscape=False, min_w=800))
    if not hero or not body:
        print(f"  ! {slug}: hero={len(hero)} body={len(body)} candidates — skipping"); return False
    hero, body = hero[0], body[0]
    hero_rel = f"/images/source/stock/{slug}-hero.jpg"; body_rel = f"/images/source/stock/{slug}-body.jpg"
    download(hero["thumb"], common.SITE_ROOT / hero_rel.lstrip("/"))
    download(body["thumb"], common.SITE_ROOT / body_rel.lstrip("/"))
    ddir = common.SITE_ROOT / "the-leaf" / slug
    art = json.load(open(ddir / "_data.json"))
    hero_attr = f"{hero['artist']} / {hero['license']} · Wikimedia Commons"
    body_attr = f"{body['artist']} / {body['license']} · Wikimedia Commons"
    art["hero"]=hero_rel; art["body_image"]=body_rel; art["hero_attribution"]=hero_attr; art["body_image_attribution"]=body_attr
    content = {k:v for k,v in art.items() if k not in ("hero","body_image","status","hero_attribution","body_image_attribution","slug","og_image")}
    rk = dict(hero=hero_rel, og_image=hero_rel, body_image=body_rel, slug=slug,
              hero_attribution=hero_attr, body_image_attribution=body_attr, **content)
    (ddir/"index.html").write_text(render("leaf-canonical.html", gated=False, **rk), encoding="utf-8")
    (ddir/"preview.html").write_text(render("leaf-canonical.html", gated=True, **rk), encoding="utf-8")
    (ddir/"_data.json").write_text(json.dumps(art, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    m = json.load(open(MANIFEST))
    for e in m:
        if e["slug"]==slug: e["thumb"]=hero_rel
    json.dump(m, open(MANIFEST,"w"), indent=2, ensure_ascii=False); open(MANIFEST,"a").write("\n")
    print(f"  {slug}:\n     HERO <{hero['title'][:55]}>\n     BODY <{body['title'][:55]}>")
    return True

if __name__ == "__main__":
    slugs = sys.argv[1:] or list(JOBS.keys())
    for s in slugs:
        wire(s, *JOBS[s])
    print("done.")
