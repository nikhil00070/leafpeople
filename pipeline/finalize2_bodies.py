import json, shutil, re, urllib.parse, urllib.request
from pathlib import Path
import common
from render import render
SC = Path("/private/tmp/claude-501/-Users-nikhilamin/6459fc46-84ca-4a81-a86e-c83880bafe74/scratchpad")
MAN = common.SITE_ROOT / "the-leaf" / "manifest.json"
UA={"User-Agent":"LeafPeople/1.0 (contact@leafpeople.app)"}
cand=json.load(open(SC/"cand_meta.json")); choco=json.load(open(SC/"choco2_meta.json")); atl=json.load(open(SC/"atl_meta.json"))
def A(c): return f"{c['artist']} / {c['license']} · Wikimedia Commons"
def commons_attr(title):
    url="https://commons.wikimedia.org/w/api.php?"+urllib.parse.urlencode({"action":"query","titles":"File:"+title,"prop":"imageinfo","iiprop":"extmetadata","format":"json"})
    d=json.load(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=30))
    for p in ((d.get("query") or {}).get("pages") or {}).values():
        m=((p.get("imageinfo") or [{}])[0].get("extmetadata") or {})
        art=re.sub(r"<[^>]+>","",(m.get("Artist") or {}).get("value","")).strip()[:50] or "Wikimedia"
        lic=(m.get("LicenseShortName") or {}).get("value","")
        return f"{art} / {lic} · Wikimedia Commons"
    return "Wikimedia Commons"
# copy the two bad bodies (darien willet, atlantic deforestation) -> good distinct images
shutil.copy(SC/"cand_darien_1.jpg", common.SITE_ROOT/"images/source/stock/rainforest-darien-body.jpg")
shutil.copy(SC/"atl_2.jpg", common.SITE_ROOT/"images/source/stock/rainforest-atlantic-forest-body.jpg")
# body attribution per slug
BODY_ATTR = {
 "rainforest-western-amazon": commons_attr("Forest around MLC.jpg"),
 "rainforest-choco": A(choco[0]),
 "rainforest-atlantic-forest": A(atl[2]),
 "rainforest-darien": A(cand["darien"][1]),
 "rainforest-ecuadorian-cloud-forest": commons_attr("Mindo-Cloud-Forest-03.jpg"),
 "rainforest-borneo": commons_attr("Primary Rainforest (10623380025).jpg"),
}
for slug, battr in BODY_ATTR.items():
    ddir=common.SITE_ROOT/"the-leaf"/slug
    art=json.load(open(ddir/"_data.json"))
    body_rel=f"/images/source/stock/{slug}-body.jpg"
    art["body_image"]=body_rel; art["body_image_attribution"]=battr
    hero_rel=art["hero"]; hero_attr=art.get("hero_attribution","")
    content={k:v for k,v in art.items() if k not in ("hero","body_image","status","hero_attribution","body_image_attribution","slug","og_image")}
    rk=dict(hero=hero_rel,og_image=hero_rel,body_image=body_rel,slug=slug,hero_attribution=hero_attr,body_image_attribution=battr,**content)
    (ddir/"index.html").write_text(render("leaf-canonical.html",gated=False,**rk),encoding="utf-8")
    (ddir/"preview.html").write_text(render("leaf-canonical.html",gated=True,**rk),encoding="utf-8")
    (ddir/"_data.json").write_text(json.dumps(art,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"  {slug}: body={body_rel.split('/')[-1]}  [{battr[:40]}]")
print("done")
