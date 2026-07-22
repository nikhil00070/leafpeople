import json
import common
from render import render
MAN = common.SITE_ROOT / "the-leaf" / "manifest.json"
NEW = {
 "rainforest-choco": "Rainforest: The Chocó, Colombia — The Wettest Forest on Earth",
 "rainforest-atlantic-forest": "Rainforest: The Atlantic Forest, Brazil — The 7% That's Left",
 "rainforest-darien": "Rainforest: The Darién, Panama — Where the Black Velvets Begin",
 "rainforest-ecuadorian-cloud-forest": "Rainforest: The Cloud Forest, Ecuador — The Species Still Being Named",
 "rainforest-western-amazon": "Rainforest: The Western Amazon, Peru — Pink-Leaf Country",
 "rainforest-borneo": "Rainforest: Borneo, Malaysia & Indonesia — The Island That Grows Its Own Rules",
}
man = json.load(open(MAN))
for slug, title in NEW.items():
    ddir = common.SITE_ROOT/"the-leaf"/slug
    art = json.load(open(ddir/"_data.json"))
    art["title"] = title
    hero_rel=art["hero"]; body_rel=art["body_image"]
    content={k:v for k,v in art.items() if k not in ("hero","body_image","status","hero_attribution","body_image_attribution","slug","og_image")}
    rk=dict(hero=hero_rel,og_image=hero_rel,body_image=body_rel,slug=slug,
            hero_attribution=art.get("hero_attribution",""),body_image_attribution=art.get("body_image_attribution",""),**content)
    (ddir/"index.html").write_text(render("leaf-canonical.html",gated=False,**rk),encoding="utf-8")
    (ddir/"preview.html").write_text(render("leaf-canonical.html",gated=True,**rk),encoding="utf-8")
    (ddir/"_data.json").write_text(json.dumps(art,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    for e in man:
        if e["slug"]==slug: e["title"]=title
    print("  "+title)
json.dump(man, open(MAN,"w"), indent=2, ensure_ascii=False)
print("done")
