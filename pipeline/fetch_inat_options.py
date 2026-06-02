#!/usr/bin/env python3
"""Fetch iNaturalist photo OPTIONS per species for the article body-image picker.

For each true species (cultivars/hybrids are skipped — iNat only has wild taxa), query iNat
for commercially-usable CC photos (CC0 / CC-BY / CC-BY-SA) and write the-leaf/inat-options.json
  { "<slug>": [ {"src": <full photo url>, "label": <photographer>, "license": <code>}, ... ] }
The picker hotlinks these as options; on Finalize the chosen one is downloaded locally + attributed.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PER = 12  # max options per species

# app-slug -> iNat scientific name (true species only; misspellings fixed; cultivars omitted)
SPECIES = {
    "anthurium-warocqueanum": "Anthurium warocqueanum", "anthurium-veitchii": "Anthurium veitchii",
    "anthurium-crystalanium": "Anthurium crystallinum", "anthurium-papillilaminum": "Anthurium papillilaminum",
    "anthurium-dressleri": "Anthurium dressleri", "anthurium-forgetii": "Anthurium forgetii",
    "anthurium-cutucuence": "Anthurium cutucuense", "anthurium-corrugatum": "Anthurium corrugatum",
    "anthurium-vittariifolium": "Anthurium vittariifolium", "anthurium-wendlingeri": "Anthurium wendlingeri",
    "anthurium-morona": "Anthurium morona", "anthurium-kunayalense": "Anthurium kunayalense",
    "anthurium-antolakii": "Anthurium antolakii", "anthurium-cupulispathum": "Anthurium cupulispathum",
    "philodendron-gloriosum": "Philodendron gloriosum", "philodendron-melanochrysum": "Philodendron melanochrysum",
    "philodendron-gigas": "Philodendron gigas", "philodendron-verrucosum": "Philodendron verrucosum",
    "philodendron-billietiae": "Philodendron billietiae", "philodendron-squamiferum": "Philodendron squamiferum",
    "philodendron-tortum": "Philodendron tortum", "philodendron-spiritus-sancti": "Philodendron spiritus-sancti",
    "philodendron-lynnhannoniae": "Philodendron lynnhannoniae", "philodendron-heartleaf": "Philodendron hederaceum",
    "monstera-obliqua": "Monstera obliqua", "monstera-dubia": "Monstera dubia",
    "monstera-siltepecana": "Monstera siltepecana", "monstera-pinnatipartita": "Monstera pinnatipartita",
    "monstera-standleyana-variegata": "Monstera standleyana", "monstera-adansonii-variegata": "Monstera adansonii",
    "hoya-callistophylla": "Hoya callistophylla", "hoya-kerrii": "Hoya kerrii",
    "hoya-linearis": "Hoya linearis", "hoya-obovata": "Hoya obovata", "hoya-pubicalyx": "Hoya pubicalyx",
    "hoya-australis-lisa": "Hoya australis", "hoya-kentiana-variegata": "Hoya kentiana",
    "begonia-ferox": "Begonia ferox", "begonia-listada": "Begonia listada",
    "begonia-paulensis": "Begonia paulensis", "begonia-venosa": "Begonia venosa", "begonia-maculata": "Begonia maculata",
}


# Include CC-BY-NC (non-commercial): user's editorial-use decision — every photo is credited
# and we honor takedown requests. taxon_id is far more reliable than taxon_name.
LICENSES = "cc0,cc-by,cc-by-sa,cc-by-nc,cc-by-nc-sa"


def resolve_taxon(name):
    q = urllib.parse.urlencode({"q": name, "rank": "species"})
    req = urllib.request.Request(f"https://api.inaturalist.org/v1/taxa?{q}",
                                 headers={"User-Agent": "leafpeople-curation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read()).get("results", [])
    return res[0]["id"] if res else None


def fetch(name):
    tid = resolve_taxon(name)
    if not tid:
        return []
    q = urllib.parse.urlencode({
        "taxon_id": tid, "photos": "true", "photo_license": LICENSES,
        "per_page": 40, "order_by": "votes", "order": "desc",
    })
    url = f"https://api.inaturalist.org/v1/observations?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "leafpeople-curation"})
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.loads(r.read())
    out, seen = [], set()
    for obs in data.get("results", []):
        for p in obs.get("photos", [])[:1]:  # first photo per observation, for variety
            pid = p.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            full = p["url"].replace("square", "large")
            attr = p.get("attribution") or ""
            m = re.match(r"^\(c\)\s*(.+?),", attr)            # "(c) Name, some rights..." -> Name
            name = (m.group(1) if m else attr.split(",")[0]).strip()
            if not name or "rights reserved" in name.lower():
                name = "iNaturalist"
            out.append({"src": full, "label": name, "license": p.get("license_code", "")})
            if len(out) >= PER:
                return out
    return out


def main():
    result = {}
    for slug, name in SPECIES.items():
        try:
            opts = fetch(name)
        except Exception as e:
            print(f"  ! {slug} ({name}): {e}")
            opts = []
        result[slug] = opts
        print(f"  {slug:34s} {len(opts):2d}  ({name})")
        time.sleep(1.0)  # be polite to the iNat API
    out = os.path.join(ROOT, "the-leaf", "inat-options.json")
    json.dump(result, open(out, "w"), indent=2)
    total = sum(len(v) for v in result.values())
    print(f"\nwrote {out} — {total} options across {len(result)} species "
          f"(avg {total/len(result):.1f}; {sum(1 for v in result.values() if not v)} empty)")


if __name__ == "__main__":
    main()
