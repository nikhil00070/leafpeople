#!/usr/bin/env python3
"""Publish a pending article: flip status to "published", refresh derived files.

Usage:
    python publish.py <section>/<slug>           # publish one article
    python publish.py <section>/<slug> --reject  # delete the pending article entirely

Called by the /review page via .github/workflows/publish.yml, or directly from
the command line for local testing.

Pending articles live on disk at {section}/{slug}/ with manifest status=pending.
The public listing pages filter those out (status != "published" hidden), so
"publishing" is just a status flip + a sitemap/feed refresh.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE_ROOT = ROOT.parent
SECTIONS = {"the-leaf", "field-guide"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("article", help="<section>/<slug>, e.g. the-leaf/petiole-tells-the-truth")
    parser.add_argument("--reject", action="store_true", help="Delete the pending article instead of publishing")
    args = parser.parse_args()

    if "/" not in args.article:
        print(f"ERROR: expected <section>/<slug>, got {args.article!r}", file=sys.stderr)
        return 2

    section, slug = args.article.split("/", 1)
    if section not in SECTIONS:
        print(f"ERROR: section must be one of {SECTIONS}, got {section!r}", file=sys.stderr)
        return 2

    manifest_path = SITE_ROOT / section / "manifest.json"
    article_dir = SITE_ROOT / section / slug
    if not article_dir.exists():
        print(f"ERROR: article directory not found: {article_dir}", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next((e for e in manifest if e.get("slug") == slug), None)
    if not entry:
        print(f"ERROR: manifest entry for {slug} not found", file=sys.stderr)
        return 2

    if args.reject:
        manifest = [e for e in manifest if e.get("slug") != slug]
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        shutil.rmtree(article_dir)
        print(f"[publish] REJECTED + deleted: {section}/{slug}")
    else:
        if entry.get("status") == "published":
            print(f"[publish] already published, nothing to do: {section}/{slug}")
            return 0
        entry["status"] = "published"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"[publish] published: {section}/{slug}")

    # Regenerate derived files so the new article shows in sitemap/feed
    subprocess.run([sys.executable, str(ROOT / "generate_sitemap.py")], check=False)
    subprocess.run([sys.executable, str(ROOT / "generate_feed.py")], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
