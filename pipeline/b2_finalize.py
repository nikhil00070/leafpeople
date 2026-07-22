import json, shutil
from pathlib import Path
import common, manifest_helpers
from render import render
SC = Path("/private/tmp/claude-501/-Users-nikhilamin/6459fc46-84ca-4a81-a86e-c83880bafe74/scratchpad")
ST = common.SITE_ROOT/"images/source/stock"; MAN=common.SITE_ROOT/"the-leaf"/"manifest.json"
meta = json.load(open(SC/"b2_meta.json"))
def A(key,i):
    c=meta[key][i]; return f"{c['artist']} / {c['license']} · Wikimedia Commons"
# slug-suffix -> (hero_idx, body_idx or None=hero). None hero_idx => keep placeholder (needs Unsplash)
PLAN = {
 "guiana-shield": (2, None),
 "monteverde-costa-rica": (0, 1),
 "northwest-amazon": (0, 1),
 "sumatra": (0, None),
 "new-guinea": (0, 1),
 "philippines": (0, None),
 "western-ghats": (2, None),
 "madagascar": (None, None),   # no good Commons — leave placeholder, flag for Unsplash
}
man=json.load(open(MAN))
for key,(hi,bi) in PLAN.items():
    slug=f"rainforest-{key}"; ddir=common.SITE_ROOT/"the-leaf"/slug
    art=json.load(open(ddir/"_data.json"))
    if hi is not None:
        hero_rel=f"/images/source/stock/{slug}-hero.jpg"
        shutil.copy(SC/f"b2_{key}_{hi}.jpg", ST/f"{slug}-hero.jpg")
        art["hero"]=hero_rel; art["hero_attribution"]=A(key,hi)
    hero_rel=art["hero"]; hero_attr=art.get("hero_attribution","")
    if bi is not None:
        body_rel=f"/images/source/stock/{slug}-body.jpg"
        shutil.copy(SC/f"b2_{key}_{bi}.jpg", ST/f"{slug}-body.jpg")
        art["body_image"]=body_rel; art["body_image_attribution"]=A(key,bi)
    else:
        art["body_image"]=hero_rel; art["body_image_attribution"]=hero_attr
    content={k:v for k,v in art.items() if k not in ("hero","body_image","status","hero_attribution","body_image_attribution","slug","og_image")}
    rk=dict(hero=art["hero"],og_image=art["hero"],body_image=art["body_image"],slug=slug,hero_attribution=art.get("hero_attribution",""),body_image_attribution=art.get("body_image_attribution",""),**content)
    (ddir/"index.html").write_text(render("leaf-canonical.html",gated=False,**rk),encoding="utf-8")
    (ddir/"preview.html").write_text(render("leaf-canonical.html",gated=True,**rk),encoding="utf-8")
    (ddir/"_data.json").write_text(json.dumps(art,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    for e in man:
        if e["slug"]==slug: e["thumb"]=art["hero"]
    print(f"  {slug}: hero={'PLACEHOLDER (swap w/ Unsplash)' if hi is None else art['hero'].split('/')[-1]}")
json.dump(man,open(MAN,"w"),indent=2,ensure_ascii=False)
print("done")
