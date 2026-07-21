import json, shutil
from pathlib import Path
import common
from render import render
SC = Path("/private/tmp/claude-501/-Users-nikhilamin/6459fc46-84ca-4a81-a86e-c83880bafe74/scratchpad")
MAN = common.SITE_ROOT / "the-leaf" / "manifest.json"
cand = json.load(open(SC/"cand_meta.json")); choco = json.load(open(SC/"choco2_meta.json"))
def A(c): return f"{c['artist']} / {c['license']} · Wikimedia Commons"
# slug -> (hero_src or None=keep, hero_attr, body_src or None=hero, body_attr)
PLAN = {
 "rainforest-choco": (SC/"choco2_1.jpg", A(choco[1]), SC/"choco2_0.jpg", A(choco[0])),
 "rainforest-darien": (SC/"cand_darien_0.jpg", A(cand['darien'][0]), None, None),
 "rainforest-ecuadorian-cloud-forest": (SC/"cand_ecuador_0.jpg", A(cand['ecuador'][0]), None, None),
 "rainforest-atlantic-forest": (None, None, None, None),
 "rainforest-western-amazon": (None, None, None, None),
 "rainforest-borneo": (None, None, None, None),
}
for slug,(hf,ha,bf,ba) in PLAN.items():
    ddir = common.SITE_ROOT/"the-leaf"/slug
    art = json.load(open(ddir/"_data.json"))
    hero_rel = art["hero"]; hero_attr = art.get("hero_attribution","")
    if hf:
        hero_rel = f"/images/source/stock/{slug}-hero.jpg"
        shutil.copy(hf, common.SITE_ROOT/hero_rel.lstrip("/")); hero_attr = ha
    if bf:
        body_rel = f"/images/source/stock/{slug}-body.jpg"
        shutil.copy(bf, common.SITE_ROOT/body_rel.lstrip("/")); body_attr = ba
    else:
        body_rel, body_attr = hero_rel, hero_attr
    art["hero"]=hero_rel; art["body_image"]=body_rel; art["hero_attribution"]=hero_attr; art["body_image_attribution"]=body_attr
    content = {k:v for k,v in art.items() if k not in ("hero","body_image","status","hero_attribution","body_image_attribution","slug","og_image")}
    rk = dict(hero=hero_rel,og_image=hero_rel,body_image=body_rel,slug=slug,hero_attribution=hero_attr,body_image_attribution=body_attr,**content)
    (ddir/"index.html").write_text(render("leaf-canonical.html",gated=False,**rk),encoding="utf-8")
    (ddir/"preview.html").write_text(render("leaf-canonical.html",gated=True,**rk),encoding="utf-8")
    (ddir/"_data.json").write_text(json.dumps(art,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    m=json.load(open(MAN))
    for e in m:
        if e["slug"]==slug: e["thumb"]=hero_rel
    json.dump(m,open(MAN,"w"),indent=2,ensure_ascii=False)
    print(f"  {slug}: hero={hero_rel.split('/')[-1]} body={body_rel.split('/')[-1]}")
print("done")
