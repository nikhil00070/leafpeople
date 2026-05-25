#!/usr/bin/env python3
"""Generate the next queued Field Guide article and write it to the site.

Usage:
    ANTHROPIC_API_KEY=... python generate_guide.py

Picks the next 'queued' item from guide_queue.json, generates a genus care guide
(JSON-schema constrained), runs the slop gate, renders HTML, updates the manifest,
and marks the item published.
"""

import datetime as dt
import json

import common
import manifest_helpers
import slop_repair
from render import render

QUEUE = common.ROOT / "guide_queue.json"
MANIFEST = common.SITE_ROOT / "field-guide" / "manifest.json"

# A representative app shot per genus for the card thumbnail.
GENUS_THUMB = {
    "Philodendron": "/images/app/shot-02.png",
    "Anthurium": "/images/app/shot-08.png",
    "Monstera": "/images/app/shot-04.png",
    "Begonia": "/images/app/shot-05.png",
    "Hoya": "/images/app/shot-07.png",
}
DEFAULT_THUMB = "/images/app/shot-01.png"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "meta_title": {"type": "string"},
        "meta_description": {"type": "string"},
        "genus": {"type": "string"},
        "title": {"type": "string"},
        "deck": {"type": "string"},
        "stat_number": {"type": "string"},
        "stat_label": {"type": "string"},
        "picks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "location": {"type": "string"},
                    "description": {"type": "string"},
                    "tag": {"type": "string"},
                },
                "required": ["name", "location", "description", "tag"],
            },
        },
        "body_sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "heading": {"type": "string"},
                    "paragraphs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["heading", "paragraphs"],
            },
        },
    },
    "required": ["meta_title", "meta_description", "genus", "title", "deck",
                 "stat_number", "stat_label", "picks", "body_sections"],
}


def build_prompt(item: dict) -> str:
    return (
        "Write one Field Guide article (900-1300 words) for the genus "
        f"{item['genus']}.\n"
        f"Working title / angle: {item['title_hint']}\n"
        "Include 3-5 ranked picks (real, well-known species/cultivars in this genus, each with a "
        "short location/habit note, a 3-4 sentence description, and a 1-3 word tag), plus 2-3 body "
        "sections of specific care guidance (substrate, light, water & humidity, common mistakes).\n"
        "If the title names a count (e.g. 'Five ...'), the number of picks MUST match it.\n"
        "The `location` field is the plant's habit/type (e.g. 'Climber · velvet leaf'), not a place.\n"
        "Write meta_title as the bare headline only — do not append 'Field Guide', "
        "'Leaf People', or any brand/site name; the template adds branding.\n"
        "Return JSON only, matching the schema."
    )


def main() -> int:
    queue = common.load_queue(QUEUE)
    idx, item = common.next_queued(queue)
    if item is None:
        print("[guide] queue empty — nothing to publish.")
        return 0

    print(f"[guide] generating: {item['slug']}")
    article = common.generate(common.voice(), build_prompt(item), SCHEMA)
    article["meta_title"] = common.clean_meta_title(article["meta_title"])

    # Slop gate
    texts = [article["title"], article["deck"], article["stat_label"]]
    for p in article["picks"]:
        texts.extend([p["description"], p["tag"]])
    for s in article["body_sections"]:
        texts.append(s["heading"])
        texts.extend(s["paragraphs"])
    hits = slop_repair.check_article(texts)
    if hits:
        print(f"[guide] SLOP DETECTED, not publishing: {hits}")
        return 1

    hero = common.guide_hero(article["genus"])
    html = render("guide-canonical.html", hero=hero, og_image=hero, **article)

    out_dir = common.SITE_ROOT / "field-guide" / item["slug"]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "_data.json").write_text(
        json.dumps({**article, "slug": item["slug"], "hero": hero}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"[guide] wrote {out_dir / 'index.html'}")

    today = dt.date.today().isoformat()
    manifest_helpers.upsert(MANIFEST, {
        "slug": item["slug"],
        "title": article["title"],
        "category": article["genus"],
        "description": article["meta_description"],
        "url": f"/field-guide/{item['slug']}",
        "date": today,
        "thumb": hero,
    })

    queue[idx]["status"] = "published"
    queue[idx]["published_at"] = today
    common.save_queue(QUEUE, queue)
    print(f"[guide] published {item['slug']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
