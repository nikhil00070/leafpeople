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
import os
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
        "body_image_caption": {"type": "string"},
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
        # AEO: Q&A pairs rendered visibly + as FAQPage JSON-LD
        "faqs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "q": {"type": "string"},
                    "a": {"type": "string"},
                },
                "required": ["q", "a"],
            },
        },
    },
    "required": ["meta_title", "meta_description", "category", "title", "deck",
                 "intro", "pull_quote", "sections", "body_image_caption", "faqs"],
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
        "Also write `body_image_caption`: one short editorial-feeling caption "
        "(5-10 words) for an inset photo placed mid-article.\n"
        "Write `faqs`: 3-4 genuine questions a reader would search for on this topic, "
        "each with a direct, factual 2-4 sentence answer that stands on its own. Answer "
        "in the first sentence, then add detail. No fluff, no restating the question.\n"
        "Return JSON only, matching the schema."
    )


def main() -> int:
    queue = common.load_queue(QUEUE)
    idx, item = common.next_queued(queue)
    if item is None:
        print("[leaf] queue empty — nothing to publish.")
        return 4  # distinct code: queue exhausted

    # IMAGE-FIRST QUALITY GATE (see generate_guide.py). Source BEFORE Claude.
    # Plant stories that pin their own app photo as the hero are curated and
    # always pass. Pure editorial pieces (no species to verify) only pass if iNat
    # supplies species-exact hero+body — otherwise skip rather than ship a
    # wrong/generic image. (User directive: don't write it if the image isn't good.)
    import source_images
    _cat = (item.get("category") or "").strip()
    _genus_hint = _cat if _cat in source_images.AROID_GENERA else "Anthurium"
    imgs = source_images.source_for_article(
        "the-leaf", item["slug"], _genus_hint, item.get("title_hint", item["slug"]))

    # Plant-story app-photo overrides (curated, count as good images).
    has_app_hero = bool(item.get("hero"))
    if has_app_hero:
        imgs["hero"] = item["hero"]
        imgs["hero_attribution"] = item.get("hero_attribution", "Leaf People")
        imgs.pop("hero_source_id", None)
    if imgs.get("image_needs_review") and item.get("body_fallback"):
        imgs["body_image"] = item["body_fallback"]
        imgs["body_image_attribution"] = item.get("body_image_attribution", "Leaf People")
        imgs.pop("body_image_source_id", None)
        if has_app_hero:
            imgs["image_needs_review"] = False  # app hero + app body fallback = two real images

    if not (has_app_hero or imgs.get("image_ok")):
        print(f"[leaf] SKIP {item['slug']} — image gate: {'; '.join(imgs.get('image_reasons', []))}")
        for f in (common.SITE_ROOT / "images" / "source" / "stock").glob(f"{item['slug']}-*.jpg"):
            f.unlink()
        queue[idx]["status"] = "skipped_no_image"
        common.save_queue(QUEUE, queue)
        return 3  # distinct code: skipped on image quality

    print(f"[leaf] generating: {item['slug']}")
    article = common.generate(common.voice(), build_prompt(item), SCHEMA)
    article["meta_title"] = common.strip_emphasis(common.clean_meta_title(article["meta_title"]))
    article["meta_title"] = common.ensure_keyword_title(article["meta_title"], slug=item["slug"])
    article["title"] = common.strip_emphasis(article["title"])

    # Slop gate
    texts = [article["title"], article["deck"], article["pull_quote"], article.get("body_image_caption", ""), *article.get("intro", [])]
    for f in article.get("faqs", []):
        texts.extend([f["q"], f["a"]])
    for s in article["sections"]:
        texts.append(s["heading"])
        texts.extend(s["paragraphs"])
    hits = slop_repair.check_article(texts)
    if hits:
        print(f"[leaf] SLOP DETECTED, not publishing: {hits}")
        return 1

    hero = imgs["hero"]
    body_image = imgs["body_image"]
    html = render("leaf-canonical.html", hero=hero, og_image=hero, body_image=body_image,
                  slug=item["slug"],  # drives canonical + JSON-LD URLs
                  hero_attribution=imgs.get("hero_attribution", ""),
                  body_image_attribution=imgs.get("body_image_attribution", ""), **article)
    out_dir = common.SITE_ROOT / "the-leaf" / item["slug"]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "_data.json").write_text(
        json.dumps({**article, "slug": item["slug"], **imgs}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"[leaf] wrote {out_dir / 'index.html'}")

    # Manifest — LP_DATE env var allows back-dating during bulk backfill.
    # New articles enter with status="pending" — they live on disk but DON'T
    # appear in the public listing until a human reviews and approves via
    # pipeline/publish.py (or the /review page's publish workflow).
    today = os.environ.get("LP_DATE") or dt.date.today().isoformat()
    manifest_helpers.upsert(MANIFEST, {
        "slug": item["slug"],
        "title": article["title"],
        "category": article["category"],
        "description": article["meta_description"],
        "url": f"/the-leaf/{item['slug']}",
        "date": today,
        "thumb": hero,
        "status": "pending",
    })

    # Mark in queue as pending_review (not yet published to readers)
    queue[idx]["status"] = "pending_review"
    queue[idx]["published_at"] = today
    common.save_queue(QUEUE, queue)
    print(f"[leaf] published {item['slug']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
