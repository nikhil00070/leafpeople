"""Read/append helpers for the section manifest JSON files that drive the
index pages (/the-leaf/manifest.json, /field-guide/manifest.json)."""

import json
from pathlib import Path


def load(path: Path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def upsert(path: Path, entry: dict) -> None:
    """Insert or replace an entry (matched by slug) and persist, newest-first."""
    items = load(path)
    items = [i for i in items if i.get("slug") != entry["slug"]]
    items.append(entry)
    items.sort(key=lambda i: i.get("date", ""), reverse=True)
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
