"""Shared helpers for the Leaf People content pipeline."""

import hashlib
import json
import os
import re
from pathlib import Path

import anthropic

# Sonnet 4.6 — strong cost/quality balance for article generation. Override
# with LP_MODEL=claude-opus-4-7 for one-off bulk runs where quality compounds.
MODEL = os.environ.get("LP_MODEL", "claude-sonnet-4-6")

ROOT = Path(__file__).resolve().parent
SITE_ROOT = ROOT.parent

# Lazily-created client so modules that only render/build (e.g. sitemap) can
# import this without an ANTHROPIC_API_KEY set.
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    return _client


def voice() -> str:
    """The static editorial voice + rules — the cached system prefix."""
    return (ROOT / "voice.md").read_text(encoding="utf-8")


def generate(system_text: str, user_prompt: str, schema: dict, max_tokens: int = 16000) -> dict:
    """Call Claude with a cached system prompt and a JSON-schema-constrained response.

    The large, identical `system_text` is sent as a cached block so repeated runs
    only pay full price for it once per cache window.
    """
    resp = _get_client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user_prompt}],
    )

    u = resp.usage
    cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
    print(f"[tokens] input={u.input_tokens} cache_read={cache_read} "
          f"cache_write={cache_write} output={u.output_tokens}")

    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


# --- lightweight markdown for paragraph strings --------------------------------

def inline_md(text: str) -> str:
    """Convert the limited inline markdown we allow (**bold**, _italic_) to HTML,
    escaping everything else."""
    out = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"_(.+?)_", r"<em>\1</em>", out)
    return out


# Strip any trailing brand suffix the model bakes into meta_title — the page
# templates already append " — <Section> | Leaf People", so without this the
# brand doubles up in the <title>.
_BRAND_SUFFIX = re.compile(
    r"\s*[|–—-]\s*(understory|the leaf|field guide|leaf people)\s*$", re.IGNORECASE
)


def clean_meta_title(s: str) -> str:
    s = s.strip()
    prev = None
    while prev != s:
        prev = s
        s = _BRAND_SUFFIX.sub("", s).strip()
    return s


def load_queue(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


def save_queue(path: Path, queue: list) -> None:
    path.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def next_queued(queue: list):
    """Return (index, item) of the first item with status 'queued', else (None, None)."""
    for i, item in enumerate(queue):
        if item.get("status", "queued") == "queued":
            return i, item
    return None, None


# --- per-article hero / card imagery (committed plant photos) ------------------
# One photo per genus (Field Guide) and per editorial category (Understory); the
# same image is used for the header band, the inline hero, and the index card.

_PLANTS = "/images/plants"

GUIDE_HERO = {
    "Philodendron": f"{_PLANTS}/philodendron.jpg",
    "Anthurium": f"{_PLANTS}/anthurium.jpg",
    "Monstera": f"{_PLANTS}/monstera.jpg",
    "Begonia": f"{_PLANTS}/begonia.jpg",
    "Hoya": f"{_PLANTS}/hoya.jpg",
}
GUIDE_HERO_DEFAULT = f"{_PLANTS}/aroid.jpg"

LEAF_HERO = {
    "Collector Culture": f"{_PLANTS}/collector-culture.jpg",
    "Field Skills": f"{_PLANTS}/field-skills.jpg",
}
LEAF_HERO_DEFAULT = f"{_PLANTS}/the-leaf.jpg"


def guide_hero(genus: str) -> str:
    return GUIDE_HERO.get((genus or "").strip(), GUIDE_HERO_DEFAULT)


def leaf_hero(category: str) -> str:
    return LEAF_HERO.get((category or "").strip(), LEAF_HERO_DEFAULT)


# --- unique hero assignment: no two articles (either section) share an image ---

_GENUS_FILES = set(GUIDE_HERO.values())


def used_images() -> set:
    """Every hero AND body image already assigned across both sections — for uniqueness."""
    used = set()
    for section in ("the-leaf", "field-guide"):
        path = SITE_ROOT / section / "manifest.json"
        if path.exists():
            for item in json.loads(path.read_text(encoding="utf-8")):
                if item.get("thumb"):
                    used.add(item["thumb"])
        for d in (SITE_ROOT / section).glob("*/_data.json"):
            try:
                data = json.loads(d.read_text(encoding="utf-8"))
                for k in ("hero", "body_image"):
                    v = data.get(k)
                    if v:
                        used.add(v)
            except Exception:
                pass
    return used


def assign_hero(slug: str, used=None, genus: str = None) -> str:
    """Pick a hero image unique across all articles. Field Guide prefers its genus
    photo while it's still free; otherwise draw a distinct one from the general
    pool (deterministic per slug, so re-runs are stable)."""
    used = set(used or ())
    if genus:
        g = GUIDE_HERO.get((genus or "").strip())
        if g and g not in used:
            return g
    pool = sorted(f"/images/plants/{p.name}" for p in (SITE_ROOT / "images" / "plants").glob("*.jpg"))
    general = [p for p in pool if p not in _GENUS_FILES] or pool
    unused = [p for p in general if p not in used] or general
    return unused[int(hashlib.md5(slug.encode("utf-8")).hexdigest(), 16) % len(unused)]
