#!/usr/bin/env python3
"""One-shot: generate N articles per bucket as PENDING drafts for review.

Unlike bulk_backfill.py (which was meant to auto-publish an archive), this
leaves everything pending — the generators set status="pending", so nothing
reaches readers until the human approves it on /review. Images come from
Openverse via source_images.py.

Dates are back-dated with the same cadence the cron uses (MWF for Understory,
weekdays for Field Guide) so the bulk doesn't stamp every article with today.
Walks backward from today, one slot per cadence position.

Guide and Leaf runs are interleaved with a sleep between each so Openverse's
anonymous rate limit isn't tripped across 40 articles.

    ANTHROPIC_API_KEY=... LP_MODEL=claude-opus-4-7 LP_BULK_N=20 python bulk_drafts.py
"""

import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SLEEP_BETWEEN = int(os.environ.get("LP_BULK_SLEEP", "8"))  # seconds, rate-limit cushion

# Mirror the cron cadences in .github/workflows/{leaf-publisher,guide-generator}.yml
LEAF_WEEKDAYS = {0, 2, 4}         # Mon/Wed/Fri
GUIDE_WEEKDAYS = {0, 1, 2, 3, 4}  # weekdays


def back_dated(n: int, weekdays: set) -> list:
    """N ISO dates walking backward from today, only on cadence weekdays.
    Newest first (index 0 = most recent), so iteration order matches manifest sort."""
    out = []
    d = dt.date.today()
    while len(out) < n:
        if d.weekday() in weekdays:
            out.append(d.isoformat())
        d -= dt.timedelta(days=1)
    return out


def run(script: str, date: str) -> int:
    env = {**os.environ, "LP_DATE": date}
    print(f"\n----- {script}  LP_DATE={date} -----", flush=True)
    r = subprocess.run([sys.executable, str(ROOT / script)], env=env, cwd=str(ROOT))
    return r.returncode


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2
    n = int(os.environ.get("LP_BULK_N", "20"))
    leaf_dates = back_dated(n, LEAF_WEEKDAYS)
    guide_dates = back_dated(n, GUIDE_WEEKDAYS)
    failures = []
    made = 0
    for i in range(n):
        for script, dates in (("generate_guide.py", guide_dates), ("generate_leaf.py", leaf_dates)):
            rc = run(script, dates[i])
            if rc == 0:
                made += 1
            else:
                failures.append((script, i, rc))
            time.sleep(SLEEP_BETWEEN)
    print(f"\n=== bulk drafts done: {made} generated, {len(failures)} failed ===")
    for f in failures:
        print(f"  FAILED: {f[0]} iter={f[1]} exit={f[2]}")
    # Non-zero only if NOTHING generated (a few slop-gate skips are fine)
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
