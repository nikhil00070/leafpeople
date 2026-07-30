#!/usr/bin/env python3
"""Batch three: two more Rainforest place-articles filling real gaps — the Daintree (Australia)
and the Congo Basin (Central Africa). Both Paleotropics. Pending in /review, placeholder heroes.

    ANTHROPIC_API_KEY=... python gen_rainforest3.py [slug]
"""
import sys, json, datetime as dt
import common, manifest_helpers, slop_repair
from render import render
from generate_leaf import SCHEMA

MANIFEST = common.SITE_ROOT / "the-leaf" / "manifest.json"
HERO = "/images/hero.jpg"; BODY = "/images/cta.jpg"   # placeholders, swapped after
P = "Rainforest (Paleotropics)"
DATE = "2026-07-21"   # sit with the rest of the rainforest cohort on date-sorted surfaces

ARTICLES = [
 {"slug":"rainforest-daintree","cat":P,
  "title":"Rainforest: The Daintree, Australia — The Oldest Rainforest on Earth",
  "angle":"The Daintree, in Far North Queensland, is part of the Wet Tropics of Queensland (a UNESCO World Heritage Area listed in 1988) and is widely described as the oldest continuously surviving tropical rainforest on Earth — on the order of 135-180 million years old, older than the Amazon, a surviving fragment of the forests that covered Gondwana. Its signature is ANTIQUITY: it holds an extraordinary concentration of primitive flowering-plant lineages (a large share of the world's most ancient angiosperm families occur here), including Idiospermum australiense, the 'idiot fruit', a living-fossil flowering plant famously rediscovered in the 1970s. Feature the Licuala ramsayi fan-palm groves near Cape Tribulation, the giant king ferns (Angiopteris), and — for collectors — the native climbing aroids (Rhaphidophora australasica, Pothos longipes, Epipremnum) and the native Hoya (Hoya australis), plus the epiphytic bird's-nest and staghorn/elkhorn ferns. Explain why a stable, wet, ancient forest became a refuge that PRESERVED primitive plant lineages long after they vanished elsewhere. Note the cassowary as the keystone seed-disperser, and the singular fact that at Cape Tribulation two World Heritage areas meet — the rainforest runs right down to the Great Barrier Reef. The draw: the closest thing to walking through the deep past of flowering plants, where the forest 'remembers' its own origins and meets the sea."},
 {"slug":"rainforest-congo-basin","cat":P,
  "title":"Rainforest: The Congo Basin, Central Africa — The Second Lung of the Planet",
  "angle":"The Congo Basin is the world's second-largest tropical rainforest after the Amazon, spanning the Democratic Republic of the Congo, the Republic of the Congo, Gabon, Cameroon, the Central African Republic and Equatorial Guinea — often called the planet's 'second lung' and one of Earth's most important carbon stores (the Cuvette Centrale peatlands beneath it hold vast amounts of carbon). It is the great rainforest that collectors and the wider world know LEAST, yet it is the botanical home of plants they grow: this is the native range of Anubias — the tough, slow-growing aroid genus that is a staple of planted aquariums worldwide — along with Cercestis (including the velvet-leaved Cercestis mirabilis, the 'African embossed' aroid prized by collectors), Nephthytis, Culcasia and African Amorphophallus, plus Raphia palms and a wealth of African begonias. Explain how the basin's rivers and deep shade shaped the emergent, semi-aquatic Anubias and the light-trapping velvet juveniles of Cercestis, and why African aroids are under-represented in the hobby relative to their diversity. Touch the megafauna that engineer the forest — forest elephants, lowland gorillas, bonobos (found only here), and okapi — and the pressures of logging. The draw: the least-known of the great rainforests, the source of the aroid in your fish tank and the velvet African climbers, and a forest the planet cannot afford to lose."},
]

def build_prompt(a):
    return ("Write one article for Understory (long-form editorial, 1100-1600 words) — the depth and "
     "texture of a great magazine feature, not a blog post. A PLACE story: a world rainforest told as "
     "a rounded narrative that lands on the plants our readers grow (aroids, Hoyas, epiphytes).\n"
     f"Angle / brief (treat all facts here as accurate anchors): {a['angle']}\n"
     f"Category label to use: {a['cat']}\n"
     "CRITICAL — AUTHENTICITY: build ONLY on well-established, real facts. Do NOT invent statistics, "
     "dates, dimensions, species counts, or quotations; if unsure of a precise number, describe it "
     "qualitatively. Never fabricate.\n"
     "Open with `intro`: 1-2 vivid scene-setting paragraphs before the first heading. Then 5-7 sections "
     "(heading + 2-4 substantial paragraphs) plus one pull quote. Weave named species in naturally with "
     "real botanical names and explain WHY the forest's conditions produced their traits. Concrete: real "
     "species, places, geography. End on the draw.\n"
     "meta_title = bare headline only, no brand suffix. `body_image_caption` = 4-9 words for an inset of a "
     "SIGNATURE on-theme plant (aroid/Hoya/palm/fern), only what's reliably true. `faqs` = 3-4 real search "
     "questions with direct 2-4 sentence answers. Return JSON only.")

def one(a):
    art=common.generate(common.voice(), build_prompt(a), SCHEMA)
    art["title"]=a["title"]; art["category"]=a["cat"]
    art["meta_title"]=common.strip_emphasis(common.clean_meta_title(art["meta_title"]))
    texts=[art["title"],art["deck"],art["pull_quote"],art.get("body_image_caption","")]+art.get("intro",[])
    for f in art.get("faqs",[]): texts+=[f["q"],f["a"]]
    for s in art["sections"]: texts+=[s["heading"],*s["paragraphs"]]
    h=slop_repair.check_article(texts)
    if h: print(f"  [slop warn] {a['slug']}: {h}")
    rk=dict(hero=HERO,og_image=HERO,body_image=BODY,slug=a["slug"],hero_attribution="",body_image_attribution="",**art)
    out=common.SITE_ROOT/"the-leaf"/a["slug"]; out.mkdir(parents=True,exist_ok=True)
    (out/"index.html").write_text(render("leaf-canonical.html",gated=False,**rk),encoding="utf-8")
    (out/"preview.html").write_text(render("leaf-canonical.html",gated=True,**rk),encoding="utf-8")
    (out/"_data.json").write_text(json.dumps({**art,"slug":a["slug"],"hero":HERO,"body_image":BODY,"status":"pending"},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    manifest_helpers.upsert(MANIFEST,{"slug":a["slug"],"title":a["title"],"category":a["cat"],"description":art["meta_description"],"url":f"/the-leaf/{a['slug']}","date":DATE,"thumb":HERO,"status":"pending"})
    print(f"  wrote {a['slug']} ({len(art['sections'])} sec)")

def main():
    want=sys.argv[1] if len(sys.argv)>1 else None
    for a in ARTICLES:
        if want and a["slug"]!=want: continue
        print(f"- {a['title']}"); one(a)
    print("done"); return 0

if __name__=="__main__": raise SystemExit(main())
