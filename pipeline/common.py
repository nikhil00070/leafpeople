"""Shared helpers for the Leaf People content pipeline."""

import json
import re
from pathlib import Path

import anthropic

# Sonnet 4.6 — strong cost/quality balance for article generation.
MODEL = "claude-sonnet-4-6"

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
