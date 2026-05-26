#!/usr/bin/env python3
"""Regenerate already-published posts at the CURRENT prompt depth, in place.

Reads each <slug>/_data.json for the topic (its title becomes the angle), calls
Claude with the same schema/prompt the live generators use, and overwrites the
article HTML, _data.json, and manifest entry. Slug and publish date are kept, so
URLs and ordering don't change. Needs ANTHROPIC_API_KEY.

    python regenerate.py              # all sections
    python regenerate.py the-leaf     # one section (the-leaf | field-guide)
"""

import datetime as dt
import json
import sys
from pathlib import Path

import common
import manifest_helpers
import slop_repair
from render import render
import generate_leaf as L
import generate_guide as G

TODAY = dt.date.today().isoformat()


def _keep_date(manifest_path: Path, slug: str) -> str:
    for it in manifest_helpers.load(manifest_path):
        if it.get("slug") == slug:
            return it.get("date", TODAY)
    return TODAY


def _write(post: Path, article: dict, hero: str, body_image: str = None):
    article["meta_title"] = common.clean_meta_title(article["meta_title"])
    extras = {"hero": hero, "og_image": hero}
    if body_image:
        extras["body_image"] = body_image
    html = render(
        "leaf-canonical.html" if post.parent.name == "the-leaf" else "guide-canonical.html",
        **extras, **article,
    )
    (post / "index.html").write_text(html, encoding="utf-8")
    payload = {**article, "slug": post.name, "hero": hero}
    if body_image:
        payload["body_image"] = body_image
    (post / "_data.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def regen_leaf(post: Path):
    data = json.loads((post / "_data.json").read_text(encoding="utf-8"))
    item = {"slug": post.name, "title_hint": data["title"], "category": data.get("category", "Understory")}
    print(f"[regen] the-leaf/{post.name}")
    article = common.generate(common.voice(), L.build_prompt(item), L.SCHEMA)
    texts = [article["title"], article["deck"], article["pull_quote"], *article.get("intro", [])]
    for s in article["sections"]:
        texts.append(s["heading"]); texts.extend(s["paragraphs"])
    if slop_repair.check_article(texts):
        print("  slop detected — keeping existing version"); return
    used = common.used_images()
    hero = data.get("hero") or common.assign_hero(post.name, used)
    body_image = data.get("body_image") or common.assign_hero(post.name + "-body", used | {hero})
    _write(post, article, hero, body_image)
    manifest = common.SITE_ROOT / "the-leaf" / "manifest.json"
    manifest_helpers.upsert(manifest, {
        "slug": post.name, "title": article["title"], "category": article["category"],
        "description": article["meta_description"], "url": f"/the-leaf/{post.name}",
        "date": _keep_date(manifest, post.name), "thumb": hero,
    })


def regen_guide(post: Path):
    data = json.loads((post / "_data.json").read_text(encoding="utf-8"))
    item = {"slug": post.name, "genus": data["genus"], "title_hint": data["title"]}
    print(f"[regen] field-guide/{post.name}")
    article = common.generate(common.voice(), G.build_prompt(item), G.SCHEMA)
    texts = [article["title"], article["deck"], article["stat_label"]]
    for p in article["picks"]:
        texts.extend([p["description"], p["tag"]])
    for s in article["body_sections"]:
        texts.append(s["heading"]); texts.extend(s["paragraphs"])
    if slop_repair.check_article(texts):
        print("  slop detected — keeping existing version"); return
    used = common.used_images()
    hero = data.get("hero") or common.assign_hero(post.name, used, genus=article["genus"])
    body_image = data.get("body_image") or common.assign_hero(post.name + "-body", used | {hero})
    _write(post, article, hero, body_image)
    manifest = common.SITE_ROOT / "field-guide" / "manifest.json"
    manifest_helpers.upsert(manifest, {
        "slug": post.name, "title": article["title"], "category": article["genus"],
        "description": article["meta_description"], "url": f"/field-guide/{post.name}",
        "date": _keep_date(manifest, post.name), "thumb": hero,
    })


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else "all"
    if only in ("all", "the-leaf"):
        for post in sorted(p for p in (common.SITE_ROOT / "the-leaf").iterdir() if p.is_dir()):
            if (post / "_data.json").exists():
                regen_leaf(post)
    if only in ("all", "field-guide"):
        for post in sorted(p for p in (common.SITE_ROOT / "field-guide").iterdir() if p.is_dir()):
            if (post / "_data.json").exists():
                regen_guide(post)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
