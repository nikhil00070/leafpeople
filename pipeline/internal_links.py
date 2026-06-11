#!/usr/bin/env python3
"""Auto internal-linking: link the first mention of a plant in each article to that
plant's own page. Internal links concentrate ranking signal on the canonical page for
each species (the SEO point the slug-level mentions can't achieve on their own).

Targets = PUBLISHED articles whose slug is a binomial (genus-species). Each target's
linkable term is derived from the article's OWN text (genus from the slug + the species
word it actually uses), so slug typos like 'crystalanium' resolve to the real
'Anthurium crystallinum'. In every other published article, the FIRST occurrence of that
term (italicised, per botanical convention) becomes a link to the target page. Capped per
article so it reads naturally; never self-links; idempotent (skips already-linked targets).

    python3 pipeline/internal_links.py            # dry run — report only
    python3 pipeline/internal_links.py --apply    # write _data.json, then run rebuild.py
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERA = {
    "anthurium", "philodendron", "monstera", "alocasia", "begonia", "hoya", "syngonium",
    "aglaonema", "calathea", "amydrium", "amorphophallus", "caladium", "colocasia",
    "epipremnum", "rhaphidophora", "scindapsus", "stromanthe", "spathiphyllum",
    "dieffenbachia", "homalomena", "schismatoglottis", "cercestis", "thaumatophyllum",
}
CAP_PER_ARTICLE = 8


def published():
    d = json.loads((ROOT / "feed.json").read_text(encoding="utf-8"))
    items = d if isinstance(d, list) else (d.get("items") or next(v for v in d.values() if isinstance(v, list)))
    out = []
    for it in items:
        p = ROOT / it["section"] / it["slug"] / "_data.json"
        if p.exists():
            out.append({"slug": it["slug"], "section": it["section"],
                        "path": "/" + it["section"] + "/" + it["slug"], "data": json.loads(p.read_text(encoding="utf-8")), "file": p})
    return out


def para_refs(data):
    """Mutable references to every body paragraph (and intro) as (container, key)."""
    refs = []
    if isinstance(data.get("intro"), str):
        refs.append((data, "intro"))
    for key in ("sections", "body_sections"):
        for s in data.get(key) or []:
            ps = s.get("paragraphs")
            if isinstance(ps, list):
                refs.extend((ps, j) for j in range(len(ps)))
    return refs


def all_text(data):
    return " ".join(obj[key] for obj, key in para_refs(data)) + " " + (data.get("title") or "") + " " + (data.get("deck") or "")


def canonical_term(art):
    """The binomial term for a binomial-slug article = 'Genus species' from the slug.
    Slugs are unique, so terms are unique (no collisions, no mis-linking). Correctly
    spelled slugs match the body text; the rare typo slug just gets no inbound links."""
    genus, species = art["slug"].split("-")[:2]
    return genus.capitalize() + " " + species


def link_first(refs, term, path):
    # Match the term optionally wrapped in italic underscores; the lookarounds use the
    # OUTER boundary (not \b, since _ is a word char) and exclude an existing '[' link.
    pat = re.compile(r"(?<![\w\[])(_?)" + re.escape(term) + r"(_?)(?![\w])")
    for obj, key in refs:
        t = obj[key]
        m = pat.search(t)
        if not m:
            continue
        if t[m.end():m.end() + 2] == "](":  # already a link
            continue
        obj[key] = t[:m.start()] + "[_" + term + "_](" + path + ")" + t[m.end():]
        return (t[max(0, m.start() - 45):m.start()] + "⟦" + term + "⟧" + t[m.end():m.end() + 35]).strip()
    return None


def main(apply):
    arts = published()
    targets = []
    for a in arts:
        if len(a["slug"].split("-")) == 2 and a["slug"].split("-")[0] in GENERA:
            targets.append({"term": canonical_term(a), "path": a["path"], "slug": a["slug"]})
    targets.sort(key=lambda t: len(t["term"]), reverse=True)  # longest first

    total, hosts_hit, samples = 0, 0, []
    per_target = Counter()
    for host in arts:
        data = host["data"]
        refs = para_refs(data)
        blob = all_text(data)
        added = 0
        for tg in targets:
            if added >= CAP_PER_ARTICLE:
                break
            if tg["slug"] == host["slug"]:
                continue
            if tg["path"] + ")" in blob:  # already linked somewhere
                continue
            ex = link_first(refs, tg["term"], tg["path"])
            if ex:
                added += 1
                total += 1
                per_target[tg["term"]] += 1
                blob = all_text(data)
                if len(samples) < 6:
                    samples.append(f"{host['slug']}: …{ex}…")
        if added:
            hosts_hit += 1
            if apply:
                host["file"].write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{'APPLIED' if apply else 'DRY RUN'}: {total} internal links across {hosts_hit} articles "
          f"({len(targets)} plant pages are link targets)")
    print("\nMost-linked plant pages:")
    for term, n in per_target.most_common(10):
        print(f"  {n:>3}× → {term}")
    print("\nSample links (⟦…⟧ = becomes the link):")
    for s in samples:
        print("  " + s)
    if not apply:
        print("\n(dry run — nothing written. Re-run with --apply, then python3 pipeline/rebuild.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--apply" in sys.argv))
