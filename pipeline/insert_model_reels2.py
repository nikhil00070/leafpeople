#!/usr/bin/env python3
"""Batch 2 — weave the 6 funny "plant-person confession" reels into the IG calendar.

Same reflow-safe approach as insert_model_reels.py: pin any un-pinned future post to its
current asset, then interleave the new reels at sprinkled day positions and renumber. Idempotent
re-pin (only pins posts that lack an explicit img_ready), so batch-1's pins are untouched.

Run once. Guarded against double-insert. Writes a .bak first.
"""
import datetime as dt
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "instagram" / "posts.json"
START = dt.date(2026, 6, 7)
FREEZE = 12                                  # leave the imminent days alone
POSITIONS = [14, 22, 30, 38, 46, 54]         # sprinkled, interleaved with batch-1 reels (Jun20 → Jul30)
PREFIX = "b2-"

CTA = "Leaf People — name it, care for it, keep it alive. Link in bio \U0001F33F"
HASHTAGS = ["#leafpeopleapp", "#plantsofinstagram", "#houseplants", "#plantmom",
            "#rareplants", "#urbanjungle", "#plantaddict", "#aroidsofinstagram"]

# (title, hook[burned in], caption) in reel order 1..6
REELS = [
    ("Went in for one", "POV: you went in for ONE plant.",
     "'Just one,' they said. The car says otherwise. Zero regrets. \U0001F33F"),
    ("Room for more", "The plants heard there was room for more.",
     "They just keep arriving. And honestly — who am I to say no? \U0001F33F"),
    ("Just looking", "Me: I'm just looking.",
     "I told the staff I was 'just browsing.' I lied. \U0001F33F"),
    ("One small plant", "When you said you'd get 'one small plant.'",
     "Define 'small.' I'll wait. \U0001F33F"),
    ("No room for guests", "There's still room for guests. (There is not.)",
     "Pull up a— …actually, there's nowhere to sit. Sorry. \U0001F33F"),
    ("Unboxing day", "Unboxing day > my birthday.",
     "Heat pack, bubble wrap, a brand-new leaf. Better than my birthday. \U0001F33F"),
]


def date_for(day):
    return (START + dt.timedelta(days=day - 1)).isoformat()


def reel_post(i, title, hook, caption):
    n = f"{i:02d}"
    return {
        "id": f"{PREFIX}{n}", "day": None, "date": None,
        "phase": "lifestyle", "branch": "model-reels", "status": "draft",
        "title": title,
        "image": f"/images/instagram/{PREFIX}{n}-cover.jpg",
        "img_ready": f"/images/instagram/{PREFIX}{n}-cover.jpg",
        "video": f"/videos/instagram/{PREFIX}{n}.mp4",
        "reel": True,
        "caption": caption,
        "hashtags": list(HASHTAGS),
        "cta": CTA,
        "hook": hook,
        "metrics": {"likes": 0, "comments": 0, "saves": 0, "follows": 0, "reach": 0},
    }


def main():
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    if any(str(p.get("id", "")).startswith(PREFIX) for p in posts):
        raise SystemExit("batch-2 reels already inserted — aborting.")

    frozen = [p for p in posts if p["day"] <= FREEZE]
    future = sorted((p for p in posts if p["day"] > FREEZE), key=lambda p: p["day"])

    # pin only posts that aren't already pinned (batch-1 pinned most future posts)
    for p in future:
        if "img_ready" not in p:
            d = p["day"]
            ig = ROOT / "images" / "ig_ready" / f"d{d:02d}.jpg"
            p["img_ready"] = f"/images/ig_ready/d{d:02d}.jpg" if ig.exists() else p["image"]
        if p.get("reel") and "video" not in p:
            vid = ROOT / "videos" / "instagram" / f"d{p['day']:02d}.mp4"
            if vid.exists():
                p["video"] = f"/videos/instagram/d{p['day']:02d}.mp4"

    reels = [reel_post(i + 1, *REELS[i]) for i in range(len(REELS))]

    out, fi, mi, new_day = [], 0, 0, FREEZE + 1
    while fi < len(future) or mi < len(reels):
        if mi < len(reels) and new_day == POSITIONS[mi]:
            p = reels[mi]; mi += 1
        else:
            p = future[fi]; fi += 1
        p["day"] = new_day
        p["date"] = date_for(new_day)
        out.append(p)
        new_day += 1

    new_posts = frozen + out
    days = [p["day"] for p in new_posts]
    assert days == list(range(1, len(new_posts) + 1)), "days not contiguous"
    assert len(new_posts) == len(posts) + 6, "expected +6 posts"

    shutil.copy(POSTS, POSTS.with_suffix(".json.bak"))
    POSTS.write_text(json.dumps(new_posts, indent=2) + "\n", encoding="utf-8")
    print(f"inserted 6 batch-2 reels. {len(posts)} -> {len(new_posts)} posts.")
    for m in reels:
        print(f"  day {m['day']:>3}  {m['date']}  {m['id']}  \"{m['hook']}\"")


if __name__ == "__main__":
    main()
