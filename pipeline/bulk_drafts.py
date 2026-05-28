#!/usr/bin/env python3
"""One-shot: generate N articles per bucket as PENDING drafts for review.

Unlike bulk_backfill.py (which back-dated + was meant to auto-publish an
archive), this leaves everything pending — the generators set status="pending",
so nothing reaches readers until the human approves it on /review. Dates are
"today" (no LP_DATE override). Images come from Openverse via source_images.py.

Guide and Leaf runs are interleaved with a sleep between each so Openverse's
anonymous rate limit isn't tripped across 40 articles.

    ANTHROPIC_API_KEY=... LP_MODEL=claude-opus-4-7 LP_BULK_N=20 python bulk_drafts.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SLEEP_BETWEEN = int(os.environ.get("LP_BULK_SLEEP", "8"))  # seconds, rate-limit cushion


def run(script: str) -> int:
    print(f"\n----- {script} -----", flush=True)
    r = subprocess.run([sys.executable, str(ROOT / script)], env={**os.environ}, cwd=str(ROOT))
    return r.returncode


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2
    n = int(os.environ.get("LP_BULK_N", "20"))
    failures = []
    made = 0
    for i in range(n):
        for script in ("generate_guide.py", "generate_leaf.py"):
            rc = run(script)
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
