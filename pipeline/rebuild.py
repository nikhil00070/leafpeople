#!/usr/bin/env python3
"""Re-render every existing The Leaf / Field Guide post with the CURRENT templates.

For each post directory:
  - if `_data.json` exists, render from it;
  - otherwise extract the article data from the existing index.html (old template
    output), save `_data.json`, then render.

This lets a template/CSS redesign roll out to already-published posts with no API
calls. Idempotent — safe to run repeatedly. Run from the `pipeline/` dir:

    python rebuild.py
"""

import html as _html
import json
import re

import common
from render import render


def _derender(s: str) -> str:
    """Reverse the templates' inline_md + Jinja autoescape back to source text."""
    s = re.sub(r"</?strong>", "**", s)
    s = re.sub(r"</?em>", "_", s)
    return _html.unescape(s).strip()


def _split_prose(block: str):
    """Return (intro_paras, sections, pull_quote) from a prose HTML block.
    intro = paragraphs before the first <h2>; sections = [{heading, paragraphs}]."""
    intro, sections, pull, cur = [], [], "", None
    for m in re.finditer(
        r'<h2[^>]*>(.*?)</h2>|<p(\s+class="pull-quote")?[^>]*>(.*?)</p>', block, re.S
    ):
        if m.group(1) is not None:
            cur = {"heading": _derender(m.group(1)), "paragraphs": []}
            sections.append(cur)
            continue
        text = _derender(m.group(3))
        if not text:
            continue
        if m.group(2):
            pull = text
        elif cur is None:
            intro.append(text)
        else:
            cur["paragraphs"].append(text)
    return intro, sections, pull


def _one(html_text, pat):
    return re.search(pat, html_text, re.S).group(1)


def extract_leaf(h: str) -> dict:
    intro, sections, pull = _split_prose(_one(h, r'<article class="prose">(.*?)</article>'))
    return {
        "meta_title": _derender(_one(h, r"<title>(.*?) — (?:Understory|The Leaf) \| Leaf People</title>")),
        "meta_description": _derender(_one(h, r'<meta name="description" content="(.*?)">')),
        "category": _derender(_one(h, r'<span class="eyebrow">(.*?)</span>')),
        "title": _derender(_one(h, r"<h1[^>]*>(.*?)</h1>")),
        "deck": _derender(_one(h, r'<p class="deck">(.*?)</p>')),
        "intro": intro,
        "sections": sections,
        "pull_quote": pull,
    }


def extract_guide(h: str) -> dict:
    picks = [
        {
            "name": _derender(m.group(1)),
            "location": _derender(m.group(2)),
            "description": _derender(m.group(3)),
            "tag": _derender(m.group(4)),
        }
        for m in re.finditer(
            r'<div class="pick"[^>]*>.*?<h3>(.*?)</h3>\s*<div class="loc">(.*?)</div>'
            r'\s*<p>(.*?)</p>\s*<span class="tag">(.*?)</span>',
            h, re.S,
        )
    ]
    _, sections, _ = _split_prose(_one(h, r'<div class="body prose"[^>]*>(.*?)</div>\s*<div class="news">'))
    return {
        "meta_title": _derender(_one(h, r"<title>(.*?) — Field Guide \| Leaf People</title>")),
        "meta_description": _derender(_one(h, r'<meta name="description" content="(.*?)">')),
        "genus": _derender(_one(h, r'<span class="eyebrow">Field Guide · (.*?)</span>')),
        "title": _derender(_one(h, r"<h1[^>]*>(.*?)</h1>")),
        "deck": _derender(_one(h, r'<p class="deck">(.*?)</p>')),
        "stat_number": _derender(_one(h, r'<span class="n">(.*?)</span>')),
        "stat_label": _derender(_one(h, r'<span class="l">(.*?)</span>')),
        "picks": picks,
        "body_sections": sections,
    }


SECTIONS = {
    "the-leaf": ("leaf-canonical.html", extract_leaf, lambda d: common.leaf_hero(d["category"])),
    "field-guide": ("guide-canonical.html", extract_guide, lambda d: common.guide_hero(d["genus"])),
}


def main() -> int:
    for section, (template, extract, hero_of) in SECTIONS.items():
        base = common.SITE_ROOT / section
        for post in sorted(p for p in base.iterdir() if p.is_dir()):
            index = post / "index.html"
            if not index.exists():
                continue
            data_path = post / "_data.json"
            if data_path.exists():
                data = json.loads(data_path.read_text(encoding="utf-8"))
            else:
                data = extract(index.read_text(encoding="utf-8"))
                data["slug"] = post.name
                data_path.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            hero = data.get("hero") or hero_of(data)
            ctx = {k: v for k, v in data.items() if k not in ("slug", "hero")}
            index.write_text(render(template, hero=hero, og_image=hero, **ctx), encoding="utf-8")
            print(f"[rebuild] {section}/{post.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
