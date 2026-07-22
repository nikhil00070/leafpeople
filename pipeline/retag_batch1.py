import json
import common
from render import render
MAN = common.SITE_ROOT / "the-leaf" / "manifest.json"
CAT = {
 "rainforest-western-amazon":"Rainforest (Neotropics)","rainforest-choco":"Rainforest (Neotropics)",
 "rainforest-atlantic-forest":"Rainforest (Neotropics)","rainforest-darien":"Rainforest (Neotropics)",
 "rainforest-ecuadorian-cloud-forest":"Rainforest (Neotropics)","rainforest-borneo":"Rainforest (Paleotropics)",
}
man=json.load(open(MAN))
for slug,cat in CAT.items():
    ddir=common.SITE_ROOT/"the-leaf"/slug
    art=json.load(open(ddir/"_data.json")); art["category"]=cat
    content={k:v for k,v in art.items() if k not in ("hero","body_image","status","hero_attribution","body_image_attribution","slug","og_image")}
    rk=dict(hero=art["hero"],og_image=art["hero"],body_image=art["body_image"],slug=slug,hero_attribution=art.get("hero_attribution",""),body_image_attribution=art.get("body_image_attribution",""),**content)
    (ddir/"index.html").write_text(render("leaf-canonical.html",gated=False,**rk),encoding="utf-8")
    (ddir/"preview.html").write_text(render("leaf-canonical.html",gated=True,**rk),encoding="utf-8")
    (ddir/"_data.json").write_text(json.dumps(art,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    for e in man:
        if e["slug"]==slug: e["category"]=cat
    print(f"  {slug} -> {cat}")
json.dump(man,open(MAN,"w"),indent=2,ensure_ascii=False)
print("retag done")
