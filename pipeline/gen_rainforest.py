#!/usr/bin/env python3
"""One-off: generate the 6 'Rainforest' Understory place-articles into /review as PENDING.

Drives the normal pipeline (cached voice + schema + render), but LOCKS the human-approved
titles (Claude writes its own otherwise) and supplies PLACEHOLDER heroes so the iNat image
gate doesn't skip these editorial place-pieces. The user swaps real forest heroes in /review.

    ANTHROPIC_API_KEY=... python gen_rainforest.py            # all 6
    ANTHROPIC_API_KEY=... python gen_rainforest.py <slug>     # just one (proof run)
"""
import sys, json, datetime as dt
import common, manifest_helpers, slop_repair
from render import render
from generate_leaf import SCHEMA   # reuse the exact article schema

MANIFEST = common.SITE_ROOT / "the-leaf" / "manifest.json"
HERO = "/images/hero.jpg"   # PLACEHOLDER — swap a real forest hero during review
BODY = "/images/cta.jpg"    # PLACEHOLDER

ARTICLES = [
 {"slug":"rainforest-western-amazon",
  "title":"Rainforest: The Western Amazon — Pink-Leaf Country",
  "angle":"The Amazon is not one forest. The plants collectors chase don't come from the flat, steaming lowland everyone pictures — they come from the western edge, where the Andes crumble into the basin across Peru and eastern Ecuador (the Rio Napo, the San Martin foothills, blackwater tributaries). That transition zone is the real diversity engine. Feature: Philodendron lynamii (electric-pink new leaves, San Martin, Peru), Philodendron atabapoense (deep maroon undersides, named for the Rio Atabapo), Anthurium vittariifolium (metre-long ribbon leaves and strings of pink berries), and Philodendron tortum (skeletal, twisting leaves from Amazonas, Brazil). Explain why nutrient-poor soils and relentless competition pushed plants UP off the ground into the canopy as epiphytes and climbers, and how the elevation gradient off the Andes creates a new microclimate every few hundred metres. Note the blackwater rivers — tea-coloured, acidic, nutrient-starved — and how they shape what grows on their banks. The draw: everyone's heard of the Amazon; almost no one knows WHERE in it the best plants actually live, or that the 'river' is really a thousand rivers."},
 {"slug":"rainforest-choco",
  "title":"Rainforest: The Chocó — The Wettest Forest on Earth",
  "angle":"The Choco, on the Pacific slope of the Colombian Andes, is the wettest forest on Earth — up to 13 metres of rain a year, permanent cloud, almost no dry season. It is the velvet-anthurium heartland. Feature: Anthurium veitchii (the King, pendant corrugated straps over a metre long), Anthurium warocqueanum (the Queen, arm-length black velvet veined in silver), Anthurium crystallinum, Philodendron gloriosum (the crawling chalk-veined velvet) and Philodendron melanochrysum (the black-gold climber). Explain why constant moisture + cool mountain air + deep understory shade produced velvet, light-trapping leaves that would scorch or crisp anywhere drier — and why so many are pendant or crawling. Touch the Choco's staggering endemism and how little of it botanists have surveyed. The draw: the single richest place on Earth for the plants collectors chase, and one of the least visited — roadless, rain-soaked, and largely unexplored."},
 {"slug":"rainforest-atlantic-forest",
  "title":"Rainforest: The Atlantic Forest — The 7% That's Left",
  "angle":"Brazil's Mata Atlantica once ran the length of the coast, as vast as the Amazon — now it's shredded to roughly 7% in fragments, which is exactly why it is so staggeringly endemic. Feature: Philodendron spiritus-sancti (the holy grail, known from only a handful of wild plants in Espirito Santo, effectively extinct in habitat), Philodendron billietiae (orange petioles), and the Brazilian begonias — Begonia listada (velvet herringbone stripe), venosa (felted silver leaves from drier coastal scrub), paulensis (deeply quilted netted leaves). Explain how isolation on a long, mountainous coast bred plants found on a single hillside and nowhere else, and how fragmentation both threatens them and concentrates the rarest. The draw: the poignant one — the most-wanted plant in the entire hobby comes from a forest that is nearly gone, a story of rarity, loss, and conservation all at once."},
 {"slug":"rainforest-darien",
  "title":"Rainforest: The Darién — Where the Black Velvets Begin",
  "angle":"The Darien Gap — the wild, roadless break in the Pan-American Highway between Panama and Colombia — and Panama's humid cloud forests are where the dark-velvet Anthuriums originate. Feature the WILD PARENTS behind the hybrids people grow at home: Anthurium dressleri (blocky near-black velvet from a tiny slice of Panama), Anthurium papillilaminum (the foundational velvet parent behind countless named crosses), Anthurium carlablackiae (described only in 2022), and Anthurium kunayalense (from the Guna Yala / Kuna Yala comarca). Explain that the 'Ace of Spades' and dozens of black-leaf hybrids on collectors' shelves trace back to these forests, and why cool, undisturbed, perpetually humid Panamanian understory produced such deep, matte, light-absorbing velvet. The draw: the origin story — the wild source of the plants people grow at home, from one of the least-accessible forests in the Americas."},
 {"slug":"rainforest-ecuadorian-cloud-forest",
  "title":"Rainforest: The Ecuadorian Cloud Forest — The Species Still Being Named",
  "angle":"Ecuador's Andean cloud forests — Mindo on the western slope, the Cordillera del Condor and Cutucu ranges in the southeast — are a frontier where new aroids are described almost every year. Feature: Anthurium cutucuense (dramatically lobed, from the Cordillera de Cutucu), Philodendron patriciae (very long, heavily rippled pendant leaves), Philodendron lynnhannoniae (elegant elongated pendants), and Anthurium wendlingeri (pendant velvet straps with a corkscrew spadix). Explain how steep elevation gradients stack a different climate — and a different flora — on every few hundred metres of hillside, producing narrow endemics and a constant stream of undescribed species. Touch how growers and taxonomists both chase these ridges. The draw: the frontier — plants science literally hasn't finished cataloguing, and the sense that the next grail is still out there on a fog-soaked ridge."},
 {"slug":"rainforest-borneo",
  "title":"Rainforest: Borneo — The Island That Grows Its Own Rules",
  "angle":"Borneo holds one of the oldest rainforests on Earth — well over 100 million years — draped over strange geology: limestone karst towers and nutrient-poor ultramafic (serpentine) soils that force plants to specialise. Feature: Hoya callistophylla (bold dark-veined leaves), Bornean begonias (rheophytes clinging to stream rocks, rock-hugging specialists), and Alocasia — with the island's carnivorous pitcher plants next door as a vivid aside. Explain how soil chemistry and deep island isolation drove bizarre, hyper-local specialists found on a single mountain or river, and how the same forces made Borneo a global hotspot. The draw: alien-looking flora shaped by rock and time — one of the planet's oldest, weirdest, and most biodiverse forests, where the plants look engineered for places nothing else can grow."},
]

def build_prompt(a: dict) -> str:
    return (
        "Write one article for Understory (long-form editorial, 1100-1600 words) — the depth "
        "and texture of a great magazine feature, not a blog post. This is a PLACE story: a "
        "world rainforest, told as a rounded narrative that lands on the plants readers can grow.\n"
        f"Angle / brief: {a['angle']}\n"
        "Category label to use: Rainforest\n"
        "Open with `intro`: 1-2 vivid scene-setting paragraphs before the first heading. Then 5-7 "
        "sections, each a heading + 2-4 substantial paragraphs, plus one pull quote. Weave the named "
        "species in naturally (use their real botanical names) and explain WHY the forest's conditions "
        "produced their traits. Be concrete: real species, places, numbers, geography. End on the draw — "
        "why a reader would want to see this forest AND grow its plants.\n"
        "Write meta_title as the bare headline only — no 'Understory'/'Leaf People'/brand suffix.\n"
        "Write `body_image_caption`: a short 4-9 word caption for an inset photo; describe only what is "
        "reliably true (no lighting/pots/actions you can't see).\n"
        "Write `faqs`: 3-4 real questions a reader would search on this forest/its plants, each a direct "
        "factual 2-4 sentence answer. Return JSON only, matching the schema."
    )

def one(a: dict) -> None:
    article = common.generate(common.voice(), build_prompt(a), SCHEMA)
    article["title"] = a["title"]                 # LOCK the approved title
    article["category"] = "Rainforest"
    article["meta_title"] = common.strip_emphasis(common.clean_meta_title(article["meta_title"]))
    # slop check — warn, don't block a review draft
    texts = [article["title"], article["deck"], article["pull_quote"], article.get("body_image_caption","")]
    texts += article.get("intro", [])
    for f in article.get("faqs", []): texts += [f["q"], f["a"]]
    for s in article["sections"]: texts += [s["heading"], *s["paragraphs"]]
    hits = slop_repair.check_article(texts)
    if hits: print(f"  [slop warn] {a['slug']}: {hits}")
    rk = dict(hero=HERO, og_image=HERO, body_image=BODY, slug=a["slug"],
              hero_attribution="", body_image_attribution="", **article)
    out = common.SITE_ROOT / "the-leaf" / a["slug"]; out.mkdir(parents=True, exist_ok=True)
    (out/"index.html").write_text(render("leaf-canonical.html", gated=False, **rk), encoding="utf-8")
    (out/"preview.html").write_text(render("leaf-canonical.html", gated=True, **rk), encoding="utf-8")
    (out/"_data.json").write_text(json.dumps({**article,"slug":a["slug"],"hero":HERO,"body_image":BODY,"status":"pending"}, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    today = dt.date.today().isoformat()
    manifest_helpers.upsert(MANIFEST, {"slug":a["slug"],"title":a["title"],"category":"Rainforest",
        "description":article["meta_description"],"url":f"/the-leaf/{a['slug']}","date":today,
        "thumb":HERO,"status":"pending"})
    print(f"  wrote {a['slug']}  ({len(article['sections'])} sections, {len(article.get('faqs',[]))} faqs)")

def main() -> int:
    want = sys.argv[1] if len(sys.argv) > 1 else None
    todo = [a for a in ARTICLES if (not want or a["slug"] == want)]
    print(f"generating {len(todo)} rainforest article(s)...")
    for a in todo:
        print(f"- {a['title']}")
        one(a)
    print("done.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
