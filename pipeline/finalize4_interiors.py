import json, shutil
from pathlib import Path
import common
from render import render
SC = Path("/private/tmp/claude-501/-Users-nikhilamin/6459fc46-84ca-4a81-a86e-c83880bafe74/scratchpad")
ST = common.SITE_ROOT / "images/source/stock"
i2 = json.load(open(SC/"i2_meta.json")); choco = json.load(open(SC/"choco2_meta.json")); atl = json.load(open(SC/"atl_meta.json"))
def A(c): return f"{c['artist']} / {c['license']} · Wikimedia Commons"

def rerender(slug, hero_rel, hero_attr, body_rel, body_attr):
    ddir = common.SITE_ROOT/"the-leaf"/slug
    art = json.load(open(ddir/"_data.json"))
    art["hero"]=hero_rel; art["hero_attribution"]=hero_attr; art["body_image"]=body_rel; art["body_image_attribution"]=body_attr
    content={k:v for k,v in art.items() if k not in ("hero","body_image","status","hero_attribution","body_image_attribution","slug","og_image")}
    rk=dict(hero=hero_rel,og_image=hero_rel,body_image=body_rel,slug=slug,hero_attribution=hero_attr,body_image_attribution=body_attr,**content)
    (ddir/"index.html").write_text(render("leaf-canonical.html",gated=False,**rk),encoding="utf-8")
    (ddir/"preview.html").write_text(render("leaf-canonical.html",gated=True,**rk),encoding="utf-8")
    (ddir/"_data.json").write_text(json.dumps(art,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

# AMAZON: hero -> looking-up interior; body stays ("Forest around MLC")
shutil.copy(SC/"i2_amazon_0.jpg", ST/"rainforest-western-amazon-hero.jpg")
a=json.load(open(common.SITE_ROOT/"the-leaf/rainforest-western-amazon/_data.json"))
rerender("rainforest-western-amazon","/images/source/stock/rainforest-western-amazon-hero.jpg",A(i2["amazon"][0]),a["body_image"],a["body_image_attribution"])
print("amazon: hero=looking-up interior")

# CHOCO: swap -> hero=moss interior, body=cloud peaks
shutil.copy(SC/"choco2_0.jpg", ST/"rainforest-choco-hero.jpg")
shutil.copy(SC/"choco2_1.jpg", ST/"rainforest-choco-body.jpg")
rerender("rainforest-choco","/images/source/stock/rainforest-choco-hero.jpg",A(choco[0]),"/images/source/stock/rainforest-choco-body.jpg",A(choco[1]))
print("choco: hero=moss interior, body=peaks")

# ATLANTIC: move flowering hero -> body, put forest-stream interior -> hero
atl_data=json.load(open(common.SITE_ROOT/"the-leaf/rainforest-atlantic-forest/_data.json"))
flower_attr=atl_data["hero_attribution"]
shutil.copy(ST/"rainforest-atlantic-forest-hero.jpg", ST/"rainforest-atlantic-forest-body.jpg")  # flowering -> body
shutil.copy(SC/"atl_2.jpg", ST/"rainforest-atlantic-forest-hero.jpg")                              # stream -> hero
rerender("rainforest-atlantic-forest","/images/source/stock/rainforest-atlantic-forest-hero.jpg",A(atl[2]),"/images/source/stock/rainforest-atlantic-forest-body.jpg",flower_attr)
print("atlantic: hero=forest stream interior, body=flowering canopy")
print("done (darién already interior; ecuador/borneo kept iconic)")
