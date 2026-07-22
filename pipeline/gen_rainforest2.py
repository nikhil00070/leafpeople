#!/usr/bin/env python3
"""Batch two: 8 more Rainforest place-articles into /review as PENDING.
Neotropics + Paleotropics. Placeholder heroes (swapped with real Commons images after).
    ANTHROPIC_API_KEY=... python gen_rainforest2.py [slug]
"""
import sys, json, datetime as dt
import common, manifest_helpers, slop_repair
from render import render
from generate_leaf import SCHEMA
MANIFEST = common.SITE_ROOT / "the-leaf" / "manifest.json"
HERO = "/images/hero.jpg"; BODY = "/images/cta.jpg"   # placeholders, swapped after
N="Rainforest (Neotropics)"; P="Rainforest (Paleotropics)"
ARTICLES = [
 {"slug":"rainforest-guiana-shield","cat":N,
  "title":"Rainforest: The Guiana Shield (Venezuela & the Guianas) — The Lost World of the Tepuis",
  "angle":"The Guiana Shield — a two-billion-year-old block of Precambrian sandstone spanning Venezuela, Guyana, Suriname, French Guiana, and northern Brazil, from which rise the tepuis: sheer-walled tabletop mountains (Roraima, Auyán-tepui, source of Angel Falls) that stood isolated for millions of years like sky-islands. Feature Philodendron billietiae (orange petioles) and Philodendron atabapoense from the shield's rivers and forests, and explain how the ancient, brutally nutrient-poor white-sand and quartzite soils plus isolation on the tepui summits bred bizarre endemics — carnivorous plants, sundews, and species found on a single mountaintop and nowhere else. Note it inspired Conan Doyle's The Lost World. The draw: forests older than almost anywhere, crowned by flat-topped mountains that evolution treated as separate planets."},
 {"slug":"rainforest-monteverde-costa-rica","cat":N,
  "title":"Rainforest: Monteverde, Costa Rica — The Cloud Forest You Can Actually Visit",
  "angle":"Monteverde, on Costa Rica's continental divide, is the accessible cloud forest — perpetually wreathed in mist blown up from the Caribbean, dripping with epiphytes, and set up for visitors on hanging bridges and canopy walkways. Feature Anthurium wendlingeri (pendant velvet straps, corkscrew spadix) and Anthurium friedrichsthalii (naturally fenestrated), plus the trees so loaded with bromeliads, orchids, mosses and aroids that the branches are gardens. Touch the resplendent quetzal and the ecotourism story. Explain how constant cloud immersion and elevation make every branch an epiphyte niche. The draw: the rainforest you can book a flight to and walk into next month — turning reading into a trip."},
 {"slug":"rainforest-northwest-amazon","cat":N,
  "title":"Rainforest: The Northwest Amazon (Colombia & Peru) — Blackwater Country",
  "angle":"The blackwater Amazon — the Rio Negro and the tea-black, acidic, nutrient-starved rivers of the northwest Amazon in Colombia and Peru, where the water is stained dark by tannins leached from white-sand forests. Contrast blackwater (igapó, campina, white-sand caatinga) with the muddy whitewater floodplains, and explain how extreme nutrient poverty and seasonal flooding produce specialized, slow-growing, often carnivorous or myrmecophilous plants, and forests on pure quartz sand. Weave in the aroids and epiphytes that ride the flooded forests. Keep it DISTINCT from the western-Amazon-foothills story — this is about water chemistry and white sand, not the Andes. The draw: a version of the Amazon almost no one pictures — rivers like black glass, forests growing on beach sand."},
 {"slug":"rainforest-sumatra","cat":P,
  "title":"Rainforest: Sumatra, Indonesia — Giants and Corpse Flowers",
  "angle":"Sumatra — vast lowland dipterocarp and peat-swamp rainforest that produces botanical giants: Amorphophallus titanum, the titan arum or 'corpse flower' with the largest unbranched inflorescence on Earth, and Rafflesia arnoldii, the largest single flower, a parasite with no leaves or stem. Feature the aroids (Alocasia), the Hoyas, and the pitcher plants, and explain how Sundaland's stable, ancient, hyper-competitive lowland forest rewarded gigantism and extreme strategies. Note the orangutans and tigers, and the palm-oil threat erasing it fast. The draw: the forest of superlatives — the biggest flower, the tallest bloom, and a race against the chainsaw."},
 {"slug":"rainforest-new-guinea","cat":P,
  "title":"Rainforest: New Guinea (Indonesia & PNG) — The Last Unmapped Forest",
  "angle":"New Guinea — the most floristically rich island on Earth (over 13,000 plant species, most found nowhere else) and one of the least botanically explored, split between Indonesia's Papua and independent Papua New Guinea, its interior a wall of rugged, cloud-drowned mountains. Feature the extraordinary Hoya diversity (the island is a Hoya epicentre), the aroids, and the birds of paradise as an aside. Explain how tectonic collision, steep elevation gradients, and sheer inaccessibility produced staggering endemism and a constant stream of undescribed species. The draw: the frontier — a rainforest where science genuinely hasn't finished the inventory, and the next new plant is still out there."},
 {"slug":"rainforest-philippines","cat":P,
  "title":"Rainforest: The Philippines — 7,000 Islands, 7,000 Experiments",
  "angle":"The Philippines — an archipelago of more than 7,000 islands, each a separate evolutionary experiment, making it one of the planet's hottest biodiversity hotspots (and one of its most threatened). Feature Hoya pubicalyx and the splash Hoyas, Medinilla (the spectacular M. magnifica), and Alocasia (A. sanderiana, A. zebrina) — many endemic to a single island or mountain. Explain how island-hopping isolation drove speciation island by island, and how little forest remains. The draw: a place where crossing a narrow strait lands you among plants that exist on that island and no other."},
 {"slug":"rainforest-western-ghats","cat":P,
  "title":"Rainforest: The Western Ghats, India — The Monsoon Mountains",
  "angle":"The Western Ghats — a 1,600-kilometre mountain chain running down India's west coast, older than the Himalaya, that catches the full force of the southwest monsoon and wrings it into some of the wettest forest in Asia. Feature the endemic Hoyas, the Impatiens explosion, the Myristica freshwater swamp forests, and the aroids of the wet evergreen sholas. Explain how the monsoon's violent seasonal rhythm plus long isolation on a peninsula bred a flora found nowhere else, and why it's a UNESCO-listed hotspot under intense pressure. The draw: a rainforest ruled by a single season — bone-dry, then drowned — and the specialists that time their whole lives to the rain."},
 {"slug":"rainforest-madagascar","cat":P,
  "title":"Rainforest: Madagascar — Evolution's Island Laboratory",
  "angle":"Madagascar — adrift off Africa for around 88 million years, long enough that roughly 90 percent of its wildlife exists nowhere else. Its eastern rainforest is a laboratory of isolation: lemurs, the traveller's palm, the octopus-armed baobabs nearby, Nepenthes pitcher plants, and Darwin's star orchid (Angraecum sesquipedale), whose foot-long nectar spur made Darwin predict a moth with a matching tongue — found decades later. Lean the piece on UNIQUENESS and isolation — how a marooned Gondwanan ark evolved its own rules — rather than on collector houseplants (it's light on the aroids and Hoyas readers grow). Touch the deforestation crisis. The draw: the closest thing on Earth to visiting another planet's evolution."},
]
def build_prompt(a):
    return ("Write one article for Understory (long-form editorial, 1100-1600 words) — a great magazine "
     "feature, not a blog post. A PLACE story: a world rainforest as a rounded narrative.\n"
     f"Angle / brief: {a['angle']}\n"
     f"Category label to use: {a['cat']}\n"
     "Open with `intro`: 1-2 vivid scene-setting paragraphs before the first heading. Then 5-7 sections "
     "(heading + 2-4 substantial paragraphs) plus one pull quote. Weave named species in naturally with "
     "real botanical names and explain WHY the forest's conditions produced their traits. Concrete: real "
     "species, places, numbers, geography. End on the draw.\n"
     "meta_title = bare headline only, no brand suffix. `body_image_caption` = 4-9 words, only what's "
     "reliably true. `faqs` = 3-4 real search questions with direct 2-4 sentence answers. JSON only.")
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
    today=dt.date.today().isoformat()
    manifest_helpers.upsert(MANIFEST,{"slug":a["slug"],"title":a["title"],"category":a["cat"],"description":art["meta_description"],"url":f"/the-leaf/{a['slug']}","date":today,"thumb":HERO,"status":"pending"})
    print(f"  wrote {a['slug']} ({len(art['sections'])} sec)")
def main():
    want=sys.argv[1] if len(sys.argv)>1 else None
    for a in ARTICLES:
        if want and a["slug"]!=want: continue
        print(f"- {a['title']}"); one(a)
    print("done"); return 0
if __name__=="__main__": raise SystemExit(main())
