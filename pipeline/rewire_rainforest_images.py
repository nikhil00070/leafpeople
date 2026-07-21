#!/usr/bin/env python3
"""Replace the placeholder heroes on the 6 Rainforest articles with real, distinct,
freely-licensed forest photos from Wikimedia Commons — then re-render each article.

Downloads a hero + body image per forest, sets proper attribution, rewrites _data.json,
re-renders index.html + preview.html, and updates the manifest thumb. Idempotent.
"""
import json, re, urllib.parse, urllib.request, datetime as dt
import common, manifest_helpers
from render import render

STOCK = common.SITE_ROOT / "images" / "source" / "stock"
MANIFEST = common.SITE_ROOT / "the-leaf" / "manifest.json"
UA = {"User-Agent": "LeafPeople/1.0 (https://leafpeople.app; contact@leafpeople.app)"}

# per-forest search queries (ground-level forest landscapes)
QUERIES = {
 "rainforest-western-amazon": ["Tambopata rainforest Peru", "Peruvian Amazon rainforest canopy", "Manú National Park forest"],
 "rainforest-choco": ["Chocó rainforest Colombia", "Nuquí Chocó landscape", "Chocó forest Colombia"],
 "rainforest-atlantic-forest": ["Mata Atlântica Brazil forest", "Atlantic Forest Serra do Mar", "Mata Atlântica landscape"],
 "rainforest-darien": ["Darién Panama rainforest", "Darién National Park forest", "Darién Gap jungle"],
 "rainforest-ecuadorian-cloud-forest": ["Mindo cloud forest Ecuador", "cloud forest Ecuador Andes", "Bellavista cloud forest Ecuador"],
 "rainforest-borneo": ["Danum Valley Borneo rainforest", "Borneo rainforest canopy", "Bornean rainforest forest"],
}
GOOD = re.compile(r"forest|rainforest|selva|mata|jungle|valley|canopy|landscape|national park|reserve|cloud|bosque|floresta", re.I)
BAD  = re.compile(r"modis|esa|satellite|map|diagram|chart|deforestation|fire|burn|logging|road|graph|\bbird\b|frog|snake|monkey|insect|flower close", re.I)

def search(q, n=12):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action":"query","generator":"search","gsrsearch":q,"gsrnamespace":"6","gsrlimit":str(n),
        "prop":"imageinfo","iiprop":"url|size|extmetadata","iiurlwidth":"1600","format":"json"})
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))
    pages = ((d.get("query") or {}).get("pages") or {}).values()
    cands = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        u = ii.get("url",""); t = p.get("title","")
        if not u.lower().endswith((".jpg",".jpeg")): continue
        w,h = ii.get("width",0), ii.get("height",0)
        if w < 1400 or w <= h: continue                 # landscape, decent res
        if BAD.search(t): continue
        meta = ii.get("extmetadata") or {}
        artist = re.sub(r"<[^>]+>","", (meta.get("Artist") or {}).get("value","")).strip() or "Wikimedia Commons"
        lic = (meta.get("LicenseShortName") or {}).get("value","")
        score = (2 if GOOD.search(t) else 0) + (1 if w >= 3000 else 0)
        cands.append({"title":t,"thumb":ii.get("thumburl") or u,"w":w,"artist":artist[:60],"license":lic,"score":score})
    cands.sort(key=lambda c: -c["score"])
    return cands

def pick_two(slug):
    seen=set(); out=[]
    for q in QUERIES[slug]:
        for c in search(q):
            key=c["title"].rsplit(" - ",1)[0][:30]
            if key in seen: continue
            seen.add(key); out.append(c)
            if len(out) >= 2: return out
    return out

def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        path.write_bytes(r.read())

def rewire(slug):
    picks = pick_two(slug)
    if len(picks) < 2:
        print(f"  ! {slug}: only {len(picks)} candidates"); return False
    hero, body = picks[0], picks[1]
    hero_rel = f"/images/source/stock/{slug}-hero.jpg"
    body_rel = f"/images/source/stock/{slug}-body.jpg"
    download(hero["thumb"], common.SITE_ROOT / hero_rel.lstrip("/"))
    download(body["thumb"], common.SITE_ROOT / body_rel.lstrip("/"))
    ddir = common.SITE_ROOT / "the-leaf" / slug
    art = json.load(open(ddir / "_data.json"))
    hero_attr = f"{hero['artist']} / {hero['license']} · Wikimedia Commons"
    body_attr = f"{body['artist']} / {body['license']} · Wikimedia Commons"
    art["hero"] = hero_rel; art["body_image"] = body_rel
    art["hero_attribution"] = hero_attr; art["body_image_attribution"] = body_attr
    # re-render: strip image/status keys from the content splat, pass explicit
    content = {k:v for k,v in art.items() if k not in ("hero","body_image","status","hero_attribution","body_image_attribution","slug","og_image")}
    rk = dict(hero=hero_rel, og_image=hero_rel, body_image=body_rel, slug=slug,
              hero_attribution=hero_attr, body_image_attribution=body_attr, **content)
    (ddir/"index.html").write_text(render("leaf-canonical.html", gated=False, **rk), encoding="utf-8")
    (ddir/"preview.html").write_text(render("leaf-canonical.html", gated=True, **rk), encoding="utf-8")
    (ddir/"_data.json").write_text(json.dumps(art, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    m = json.load(open(MANIFEST))
    for e in m:
        if e["slug"] == slug: e["thumb"] = hero_rel
    json.dump(m, open(MANIFEST,"w"), indent=2, ensure_ascii=False)
    print(f"  {slug}: hero=<{hero['title'][:45]}> body=<{body['title'][:45]}>")
    return True

if __name__ == "__main__":
    import sys
    slugs = sys.argv[1:] or list(QUERIES.keys())
    for s in slugs:
        rewire(s)
    print("done.")
