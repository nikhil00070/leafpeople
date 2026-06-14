#!/usr/bin/env python3
"""Weave the 10 lifestyle 'model holding a rare plant' reels into the live IG calendar.

Inserts the reels at sprinkled day positions (mixed parity), pushing existing future posts
forward — nothing is overwritten, the calendar just grows by 10. Reflow-safe: every future
post is first PINNED to its current cover/video via explicit `img_ready` / `video` fields, so
renumbering days never re-points a post at someone else's day-keyed asset.

  * Frozen: day <= FREEZE (posted / imminent) — untouched.
  * The model reels carry their own `video` (videos/instagram/model-NN.mp4, hook+music burned in)
    and `img_ready` cover (images/instagram/model-NN-cover.jpg), and reel:true.

Run once. Guarded against double-insert. Writes a .bak first.
"""
import datetime as dt
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "instagram" / "posts.json"
START = dt.date(2026, 6, 7)          # publish_config start_date; date(day) = START + (day-1)
FREEZE = 9                           # days 1..9 are posted/imminent — never touch
POSITIONS = [10, 13, 16, 19, 22, 25, 28, 31, 34, 37]   # new day numbers for the 10 reels (mixed parity)

CTA = "Leaf People — the rare-plant ID & care app, free to try. Link in bio \U0001F33F"
HASHTAGS = ["#leafpeopleapp", "#rareplants", "#aroidsofinstagram", "#rarearoids",
            "#plantsofinstagram", "#urbanjungle", "#plantmom", "#houseplant", "#plantsmakepeoplehappy"]

# (title, hook[already burned], caption) in reel order 1..10
REELS = [
    ("Morning green", "Some mornings you just need to see something green.",
     "The world's on fire and I'm fully invested in whether this one pushed a new root overnight. If a quiet 7am plant check is the only calm you get all day — you're our people. \U0001F33F"),
    ("7am check", "The 7am plant check. Before I've spoken to a soul.",
     "Coffee in hand, sunlight on the leaves, before I've said a word to anyone. Try explaining that kind of peace to someone who's never needed it. \U0001F33F"),
    ("Color of life", "Green is the color of life.",
     "Psychology says green is the color of life. Some mornings it's the only peace I get — and honestly, that's enough. \U0001F33F"),
    ("Chaos vs green", "The world feels chaotic. Green doesn't.",
     "200 unread emails, 6 missed calls, and ten quiet minutes with something alive and growing before any of it. The world feels chaotic. This doesn't. \U0001F33F"),
    ("Don't need much", "Coffee, quiet, a new leaf. I don't need much else.",
     "The older I get, the more I realize I don't need much. Coffee, quiet, and a brand-new leaf unfurling — that's the whole morning. \U0001F33F"),
    ("No words before coffee", "No words before coffee. Just me and the plants.",
     "Some of us just need a few quiet minutes with something green before the day starts taking. No words before coffee. If you get it, you get it. \U0001F33F"),
    ("The part I want", "This is the part I actually want.",
     "The older I get, the more I realize — this is the part I actually want. Not the noise. This. \U0001F33F"),
    ("New leaf priorities", "200 unread emails. Me: is that a new leaf?",
     "200 unread emails, 6 missed calls, 3 'you up?' texts… and me, fully locked in on whether a new leaf unfurled overnight. Priorities. \U0001F33F"),
    ("The reset", "Just need to see something green and alive.",
     "On the loud days, this is the reset — something green, something alive, something that asks nothing of me. \U0001F33F"),
    ("More than most people", "More joy in plants than in most people.",
     "I find more joy in plants than in most people. Made my peace with that a while ago, honestly. If you did too — welcome home. \U0001F33F"),
]


def date_for(day):
    return (START + dt.timedelta(days=day - 1)).isoformat()


def model_post(i, title, hook, caption):
    n = f"{i:02d}"
    return {
        "id": f"model-{n}", "day": None, "date": None,
        "phase": "lifestyle", "branch": "model-reels", "status": "draft",
        "title": title,
        "image": f"/images/instagram/model-{n}-cover.jpg",
        "img_ready": f"/images/instagram/model-{n}-cover.jpg",
        "video": f"/videos/instagram/model-{n}.mp4",
        "reel": True,
        "caption": caption,
        "hashtags": list(HASHTAGS),
        "cta": CTA,
        "hook": hook,
        "metrics": {"likes": 0, "comments": 0, "saves": 0, "follows": 0, "reach": 0},
    }


def main():
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    if any(str(p.get("id", "")).startswith("model-") for p in posts):
        raise SystemExit("model reels already inserted — aborting to avoid a double-insert.")

    frozen = [p for p in posts if p["day"] <= FREEZE]
    future = sorted((p for p in posts if p["day"] > FREEZE), key=lambda p: p["day"])

    # pin each future post to its CURRENT day-keyed assets before days change
    for p in future:
        d = p["day"]
        ig = ROOT / "images" / "ig_ready" / f"d{d:02d}.jpg"
        p["img_ready"] = f"/images/ig_ready/d{d:02d}.jpg" if ig.exists() else p["image"]
        if p.get("reel"):
            vid = ROOT / "videos" / "instagram" / f"d{d:02d}.mp4"
            if vid.exists():
                p["video"] = f"/videos/instagram/d{d:02d}.mp4"

    models = [model_post(i + 1, *REELS[i]) for i in range(len(REELS))]

    # interleave: walk new_day upward; drop a model reel at each POSITION, else the next future post
    out_future, fi, mi, new_day = [], 0, 0, FREEZE + 1
    while fi < len(future) or mi < len(models):
        if mi < len(models) and new_day == POSITIONS[mi]:
            p = models[mi]; mi += 1
        else:
            p = future[fi]; fi += 1
        p["day"] = new_day
        p["date"] = date_for(new_day)
        out_future.append(p)
        new_day += 1

    new_posts = frozen + out_future

    # sanity: contiguous days, +10 count, no dupes
    days = [p["day"] for p in new_posts]
    assert days == list(range(1, len(new_posts) + 1)), "days not contiguous 1..N"
    assert len(new_posts) == len(posts) + 10, "expected +10 posts"

    shutil.copy(POSTS, POSTS.with_suffix(".json.bak"))
    POSTS.write_text(json.dumps(new_posts, indent=2) + "\n", encoding="utf-8")

    print(f"inserted 10 model reels. total {len(posts)} -> {len(new_posts)} posts.")
    for m in models:
        print(f"  day {m['day']:>3}  {m['date']}  model-{m['id'][-2:]}  \"{m['hook']}\"")


if __name__ == "__main__":
    main()
