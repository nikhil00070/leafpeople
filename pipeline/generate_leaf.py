#!/usr/bin/env python3
"""Generate the next queued 'Understory' editorial article and write it to the site.

Usage:
    ANTHROPIC_API_KEY=... python generate_leaf.py

Picks the next item with status 'queued' from leaf_queue.json, calls Claude with the
cached editorial voice + a JSON schema, runs the slop gate, renders the article HTML,
updates the manifest, and marks the queue item published.
"""

import datetime as dt
import json
from pathlib import Path

import common
import manifest_helpers
import slop_repair
from render import render

QUEUE = common.ROOT / "leaf_queue.json"
MANIFEST = common.SITE_ROOT / "the-leaf" / "manifest.json"
DEFAULT_THUMB = "/images/app/shot-03.png"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "meta_title": {"type": "string"},
        "meta_description": {"type": "string"},
        "category": {"type": "string"},
        "title": {"type": "string"},
        "deck": {"type": "string"},
        "intro": {"type": "array", "items": {"type": "string"}},
        "pull_quote": {"type": "string"},
        "sections": {
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
    "required": ["meta_title", "meta_description", "category", "title", "deck",
                 "intro", "pull_quote", "sections"],
}


def build_prompt(item: dict) -> str:
    return (
        "Write one article for Understory (long-form editorial, 1100-1600 words) — the depth "
        "and texture of a great magazine feature, not a blog post.\n"
        f"Working title / angle: {item['title_hint']}\n"
        f"Category label to use: {item.get('category', 'Understory')}\n"
        "Open with `intro`: 1-2 scene-setting paragraphs before the first heading. Then 5-7 "
        "sections, each with a heading and 2-4 substantial paragraphs, plus one pull quote. "
        "Be concrete: name real species, cultivars, places, and techniques.\n"
        "Write meta_title as the bare headline only — do not append 'Understory', "
        "'Leaf People', or any brand/site name; the template adds branding.\n"
        "Return JSON only, matching the schema."
    )


def main() -> int:
    queue = common.load_queue(QUEUE)
    idx, item = common.next_queued(queue)
    if item is None:
        print("[leaf] queue empty — nothing to publish.")
        return 0

    print(f"[leaf] generating: {item['slug']}")
    article = common.generate(common.voice(), build_prompt(item), SCHEMA)
    article["meta_title"] = common.clean_meta_title(article["meta_title"])

    # Slop gate
    texts = [article["title"], article["deck"], article["pull_quote"], *article.get("intro", [])]
    for s in article["sections"]:
        texts.append(s["heading"])
        texts.extend(s["paragraphs"])
    hits = slop_repair.check_article(texts)
    if hits:
        print(f"[leaf] SLOP DETECTED, not publishing: {hits}")
        return 1

    # Render
    hero = common.assign_hero(item["slug"], common.used_heroes())
    html = render("leaf-canonical.html", hero=hero, og_image=hero, **article)
    out_dir = common.SITE_ROOT / "the-leaf" / item["slug"]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "_data.json").write_text(
        json.dumps({**article, "slug": item["slug"], "hero": hero}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"[leaf] wrote {out_dir / 'index.html'}")

    # Manifest
    today = dt.date.today().isoformat()
    manifest_helpers.upsert(MANIFEST, {
        "slug": item["slug"],
        "title": article["title"],
        "category": article["category"],
        "description": article["meta_description"],
        "url": f"/the-leaf/{item['slug']}",
        "date": today,
        "thumb": hero,
    })

    # Mark published
    queue[idx]["status"] = "published"
    queue[idx]["published_at"] = today
    common.save_queue(QUEUE, queue)
    print(f"[leaf] published {item['slug']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
