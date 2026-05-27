#!/usr/bin/env python3
"""One-time bulk backfill — generate the queued archive with back-dated stamps.

Why this exists: before we kick off Instagram, the site should look like it has
a real editorial history. This script processes both queues end-to-end, back-
dating each article so the archive page reads as a 6-week run rather than a
bulk dump. Cron stays on Sonnet at normal cadence; this script bumps to
Opus 4.7 (override via LP_MODEL env var) because quality compounds at launch.

Usage:
    ANTHROPIC_API_KEY=... LP_MODEL=claude-opus-4-7 python bulk_backfill.py

Failures are logged and the loop continues — re-run later with the affected
queue items still 'queued' to pick up where it stopped.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Back-dates run oldest-first so the first item in each queue gets the OLDEST
# date. Existing manually-published items keep their dates; backfill slots in
# before them.
#
# Understory: 17 dates at Mon/Wed/Fri cadence, Apr 15 → May 22, 2026.
LEAF_DATES = [
    "2026-04-15", "2026-04-17", "2026-04-20", "2026-04-22", "2026-04-24",
    "2026-04-27", "2026-04-29", "2026-05-01", "2026-05-04", "2026-05-06",
    "2026-05-08", "2026-05-11", "2026-05-13", "2026-05-15", "2026-05-18",
    "2026-05-20", "2026-05-22",
]
# Field Guide: 17 dates at weekday cadence, Apr 30 → May 22, 2026.
GUIDE_DATES = [
    "2026-04-30", "2026-05-01", "2026-05-04", "2026-05-05", "2026-05-06",
    "2026-05-07", "2026-05-08", "2026-05-11", "2026-05-12", "2026-05-13",
    "2026-05-14", "2026-05-15", "2026-05-18", "2026-05-19", "2026-05-20",
    "2026-05-21", "2026-05-22",
]


def run_one(script: str, date: str) -> int:
    env = {**os.environ, "LP_DATE": date}
    print(f"\n--- {script}  LP_DATE={date} ---")
    r = subprocess.run(
        [sys.executable, str(ROOT / script)],
        env=env,
        cwd=str(ROOT),
    )
    return r.returncode


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        return 2

    failures = []

    print(f"\n=== UNDERSTORY: {len(LEAF_DATES)} articles ===")
    for d in LEAF_DATES:
        rc = run_one("generate_leaf.py", d)
        if rc != 0:
            failures.append(("leaf", d, rc))

    print(f"\n=== FIELD GUIDE: {len(GUIDE_DATES)} articles ===")
    for d in GUIDE_DATES:
        rc = run_one("generate_guide.py", d)
        if rc != 0:
            failures.append(("guide", d, rc))

    total = len(LEAF_DATES) + len(GUIDE_DATES)
    print(f"\n=== Done. {total - len(failures)}/{total} succeeded. ===")
    for f in failures:
        print(f"  FAILED: section={f[0]} date={f[1]} exit={f[2]}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
