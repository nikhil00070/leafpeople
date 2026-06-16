"""SEO/AEO enrichment for articles (no network):

1. build_link_map() — {normalized species/cultivar name -> ("Display Name", "/section/slug")},
   derived from every article slug. Field Guide is preferred as the link target.
2. linkify_html(html, self_url, link_map) — wrap the FIRST in-body mention of each known
   species `<em>…</em>` in an internal <a> (skips self, repeats, and already-linked spans).
   Returns (html, [(name, url), ...] of what got linked) — those become JSON-LD `mentions`.
3. article_entities(slug, section, data, link_map) — (keywords, about, mentions) for JSON-LD.

Bad/topic-slug map entries are inert: they only ever produce a link if their exact binomial
appears as an italic mention, which topic phrases never do — so precision stays high.
"""
import glob
import os
import re
from pathlib import Path

from common import SCI_GENERA, SCI_NAME_FIX

ROOT = Path(__file__).resolve().parent.parent


def _binomial_from_slug(slug: str) -> str:
    """'Genus species' for a species/cultivar slug; '' for topic/genus pages."""
    if slug in SCI_NAME_FIX:
        return SCI_NAME_FIX[slug]
    parts = slug.split("-")
    if len(parts) >= 2 and parts[0] in SCI_GENERA and parts[1].isalpha() and len(parts[1]) >= 4:
        return parts[0].capitalize() + " " + parts[1]
    return ""


def _norm(s: str) -> str:
    """Normalize for matching: unescape entities, straighten quotes, lowercase, collapse spaces."""
    s = (s.replace("&#39;", "'").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
           .replace("’", "'").replace("‘", "'"))
    return re.sub(r"\s+", " ", s).strip().lower()


def build_link_map() -> dict:
    m = {}
    # the-leaf first, field-guide second so the reference page wins as the link target.
    for sec, base in (("the-leaf", "/the-leaf"), ("field-guide", "/field-guide")):
        for dp in sorted(glob.glob(str(ROOT / sec / "*" / "_data.json"))):
            slug = os.path.basename(os.path.dirname(dp))
            name = _binomial_from_slug(slug)
            if name:
                m[_norm(name)] = (name, f"{base}/{slug}")
    return m


def linkify_html(html: str, self_url: str, link_map: dict):
    """Link first-mention species <em> spans. Returns (new_html, linked[(name,url)])."""
    anchors = [(m.start(), m.end()) for m in re.finditer(r"<a\b.*?</a>", html, re.S)]
    in_anchor = lambda p: any(s <= p < e for s, e in anchors)
    seen, linked, out, last = set(), [], [], 0
    # pre-pass: any species already linked by hand (inside an <a>) is off-limits to auto-linking,
    # wherever it sits relative to a plain mention — so we never create a second, conflicting link.
    for m in re.finditer(r"<em>(.*?)</em>", html, re.S):
        if in_anchor(m.start()):
            seen.add(_norm(m.group(1)))
    for m in re.finditer(r"<em>(.*?)</em>", html, re.S):
        if in_anchor(m.start()):
            continue
        key = _norm(m.group(1))
        hit = link_map.get(key)
        if not hit:
            continue
        # don't linkify the hero subtitle — keep links in-prose, where anchor text counts
        if "hero-sci" in html[max(0, m.start() - 40):m.start()]:
            continue
        name, url = hit
        if url == self_url or key in seen:
            continue
        seen.add(key)
        linked.append((name, url))
        out.append(html[last:m.start()])
        out.append(f'<a href="{url}">{m.group(0)}</a>')
        last = m.end()
    out.append(html[last:])
    return "".join(out), linked


def _body_text(data: dict) -> str:
    parts = [data.get("deck", ""), data.get("pull_quote", "")]
    parts += data.get("intro", []) or []
    for sec in data.get("sections", []) or []:
        parts.append(sec.get("heading", ""))
        parts += sec.get("paragraphs", []) or []
    return "\n".join(p for p in parts if p)


def article_entities(slug: str, section: str, data: dict, link_map: dict):
    """(keywords:list, about:dict, mentions:list[dict]) for the Article JSON-LD."""
    self_url = f"/{section}/{slug}"
    text_norm = _norm(_body_text(data))
    mentions, mnames = [], []
    for key, (name, url) in link_map.items():
        if url == self_url:
            continue
        if key in text_norm:  # the species is named in the body
            mentions.append({"@type": "Thing", "name": name, "url": "https://leafpeople.app" + url})
            mnames.append(name)
    own = _binomial_from_slug(slug)
    genus = data.get("category") or data.get("genus") or ""
    about = {"@type": "Thing", "name": own or genus or data.get("title", ""),
             "url": "https://leafpeople.app" + self_url}
    keywords = []
    for k in ([genus, own] + mnames):
        if k and k not in keywords:
            keywords.append(k)
    return keywords, about, mentions
